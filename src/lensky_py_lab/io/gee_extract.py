"""Extract the research satellite series from Google Earth Engine into the data CSVs.

Which sources to re-extract is chosen per run; every other source keeps using the local
CSV. An extraction overwrites ``<data_dir>/<SOURCE>.csv`` and records how the file was made
in ``<data_dir>/gee_extraction_log.json``. Nothing is written unless every selected source
was fetched and passed the checks, so a failed run never leaves a half-updated folder.

Only MODIS, S2 and L8 are GEE products. The NSRS ground sensors come from the loggers;
VENuS and PLANET have no client support.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from lensky_py_lab.constants import DATE_FIELD, NDVI_RAW_FIELD, SatelliteSource
from lensky_py_lab.io.csv_loader import average_same_date, load_source_csv

#: Research site (Ramat Hanadiv), the point used by the research GEE script.
RH_LON, RH_LAT = 34.946667, 32.555806

PROVENANCE_FILE = "gee_extraction_log.json"

#: Header of the value column in the repo's source CSVs (the loader maps it to ``NDVI_RAW_FIELD``).
CSV_VALUE_COLUMN = "NDVI_RAW"

#: MODIS collections: 006 reproduces the published MODIS.csv exactly (deprecated asset);
#: 061 is the current reprocessing and differs on about half the dates.
MODIS_COLLECTIONS = {"006": "MODIS/006/MOD09GQ", "061": "MODIS/061/MOD09GQ"}


@dataclass(frozen=True)
class ExtractionSpec:
    """What to pull for one source: GEE source and date window (end exclusive)."""

    source: SatelliteSource
    start: str
    end: str


#: Per-source windows. MODIS: the research script's window. S2 / L8: from 2019-01-01 to one
#: month after the last NSRS date (2021-11-04), i.e. aligned to the NSRS record.
EXTRACTION_SPECS: Dict[str, ExtractionSpec] = {
    "MODIS": ExtractionSpec(SatelliteSource.MODIS, "2018-01-01", "2022-09-01"),
    "S2": ExtractionSpec(SatelliteSource.SENTINEL2, "2019-01-01", "2021-12-05"),
    "L8": ExtractionSpec(SatelliteSource.LANDSAT8, "2019-01-01", "2021-12-05"),
}


def parse_sources(arg: Union[str, Sequence[str], None]) -> List[str]:
    """``None`` / ``"none"`` -> []; ``"all"`` -> every GEE source; else a comma list."""
    if arg is None:
        return []
    names = [t.strip() for t in (arg.split(",") if isinstance(arg, str) else arg) if t.strip()]
    if not names or [n.lower() for n in names] == ["none"]:
        return []
    if [n.lower() for n in names] == ["all"]:
        return list(EXTRACTION_SPECS)
    lookup = {k.lower(): k for k in EXTRACTION_SPECS}
    out = []
    for n in names:
        if n.lower() not in lookup:
            raise ValueError(
                f"Cannot extract {n!r} from GEE; choose from {list(EXTRACTION_SPECS)}, 'all' or 'none'. "
                "NSRS comes from the loggers; VENuS and PLANET have no client support."
            )
        out.append(lookup[n.lower()])
    return list(dict.fromkeys(out))


def _by_date(frame: pd.DataFrame, column: str) -> pd.Series:
    dates = pd.to_datetime(frame.index, unit="s").normalize()
    return pd.to_numeric(frame[column], errors="coerce").groupby(dates).mean()


def compare_with_existing(existing_csv: Path, new: pd.DataFrame, tol: float = 0.0015) -> Dict[str, Any]:
    """Date-wise comparison of a fresh extraction with the CSV it would replace."""
    if not existing_csv.exists():
        return {"previous_file": False}
    # Compare on calendar dates. The existing file's dates come from its DATE column (the loader's
    # index is local-time midnight, i.e. 21:00/22:00 UTC the day before); GEE timestamps are UTC.
    prev = average_same_date(load_source_csv(existing_csv))
    old = pd.to_numeric(prev[NDVI_RAW_FIELD], errors="coerce").groupby(
        pd.to_datetime(prev[DATE_FIELD]).dt.normalize()).mean()
    cur = _by_date(new, NDVI_RAW_FIELD)
    both = pd.concat([old.rename("old"), cur.rename("new")], axis=1).dropna()
    diff = both["new"] - both["old"]
    return {
        "previous_file": True,
        "previous_dates_with_value": int(old.notna().sum()),
        "new_dates_with_value": int(cur.notna().sum()),
        "shared_dates": int(len(both)),
        "shared_dates_identical": int((diff.abs() < tol).sum()),
        "max_abs_diff": round(float(diff.abs().max()), 4) if len(both) else None,
        "rmse": round(float(np.sqrt((diff ** 2).mean())), 4) if len(both) else None,
        "bias_new_minus_old": round(float(diff.mean()), 4) if len(both) else None,
        "only_in_previous": int((old.notna() & ~old.index.isin(cur.dropna().index)).sum()),
        "only_in_new": int((cur.notna() & ~cur.index.isin(old.dropna().index)).sum()),
    }


def write_source_csv(df: pd.DataFrame, path: Path) -> None:
    """Write in the loader's format: ``DATE`` as ``"Mon d, YYYY"`` and ``NDVI_RAW``."""
    dates = pd.to_datetime(df.index, unit="s")
    pd.DataFrame({
        DATE_FIELD: [f"{d.strftime('%b')} {d.day}, {d.year}" for d in dates],
        CSV_VALUE_COLUMN: pd.to_numeric(df[NDVI_RAW_FIELD]).round(3).values,
    }).to_csv(path, index=False)


def _commit() -> Optional[str]:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True, cwd=Path(__file__).parent).stdout.strip()
    except Exception:  # noqa: BLE001 - provenance only, never fatal
        return None


def extract_sources(
    names: Iterable[str],
    data_dir: Union[str, Path],
    client: Any,
    modis_collection: str = "006",
    specs: Optional[Dict[str, ExtractionSpec]] = None,
    force: bool = False,
    min_keep_fraction: float = 0.5,
) -> Dict[str, Dict[str, Any]]:
    """Pull *names* from GEE and overwrite ``<data_dir>/<name>.csv``.

    Each source is fetched with ``client.get_ndvi_timeseries`` (never the
    ``..._all`` helper, which swallows errors into empty frames). All sources are fetched
    and checked before any file is written. A result is refused when it is empty or has
    fewer than ``min_keep_fraction`` of the dates the existing file has, unless ``force``.

    Returns one summary per source (also stored in the provenance log).
    """
    names = list(names)
    if not names:
        return {}
    specs = specs or EXTRACTION_SPECS
    if modis_collection not in MODIS_COLLECTIONS:
        raise ValueError(f"modis_collection must be one of {list(MODIS_COLLECTIONS)}, got {modis_collection!r}")
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    geometry = client.point_geometry(RH_LON, RH_LAT)

    fetched: Dict[str, pd.DataFrame] = {}
    summaries: Dict[str, Dict[str, Any]] = {}
    for name in names:
        spec = specs[name]
        asset = MODIS_COLLECTIONS[modis_collection] if name == "MODIS" else None
        df = client.get_ndvi_timeseries(geometry, spec.start, spec.end, spec.source, collection=asset)
        target = data_dir / f"{name}.csv"
        if df is None or len(df) == 0 or df[NDVI_RAW_FIELD].notna().sum() == 0:
            raise RuntimeError(f"GEE returned no data for {name}; nothing was written.")
        cmp = compare_with_existing(target, df)
        if cmp.get("previous_file") and not force:
            kept = cmp["new_dates_with_value"] / max(cmp["previous_dates_with_value"], 1)
            if kept < min_keep_fraction:
                raise RuntimeError(
                    f"{name}: new extraction has {cmp['new_dates_with_value']} dates vs "
                    f"{cmp['previous_dates_with_value']} in {target.name}; refusing to overwrite "
                    f"(pass force to override). Nothing was written."
                )
        fetched[name] = df
        summaries[name] = {
            "file": target.name,
            "gee_source": spec.source.value,
            "collection": asset or "client default (see gee_client._COLLECTIONS)",
            "window": [spec.start, spec.end],
            "point_lon_lat": [RH_LON, RH_LAT],
            "rows": int(len(df)),
            "extracted_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "code_commit": _commit(),
            "comparison_with_previous_file": cmp,
        }

    # A file held open by another program (e.g. Excel) must not leave the folder half-updated.
    for name in fetched:
        target = data_dir / f"{name}.csv"
        if target.exists():
            try:
                with open(target, "ab"):
                    pass
            except OSError as exc:
                raise RuntimeError(
                    f"Cannot write {target} ({exc.strerror}). Close it in any program that has it open; "
                    "nothing was written."
                ) from exc

    for name, df in fetched.items():
        write_source_csv(df, data_dir / f"{name}.csv")

    log_path = data_dir / PROVENANCE_FILE
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {}
    log.update(summaries)
    log_path.write_text(json.dumps(log, indent=2, sort_keys=True), encoding="utf-8")
    return summaries
