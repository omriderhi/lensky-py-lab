"""Observations per sensor per calendar month (supplementary Table S1).

A cell is the number of distinct calendar dates with a kept (non-null) value for the
source in that month, inside the reference window. Calendar dates come from the
``DATE`` column, not from the index: the index is the unix timestamp of a naive local
datetime, so on a machine east of UTC converting it back with ``unit="s"`` gives the
previous day. The index is used only for the window bounds.
"""
from __future__ import annotations

import warnings
from datetime import datetime
from typing import Dict, Iterable, Sequence, Tuple

import pandas as pd

from lensky_py_lab.constants import DATE_FIELD, NDVI_CLEAN_FIELD
from lensky_py_lab.pipeline.processor import merge_processed

DEFAULT_ORDER = ("NSRS_1", "NSRS_2", "NSRS_3", "MODIS", "S2", "L8")


def _kept_dates(df: pd.DataFrame, window: Tuple[int, int], field: str) -> pd.DatetimeIndex:
    """Distinct calendar dates (from DATE) with a non-null ``field`` inside the window."""
    t0, t1 = window
    keep = pd.to_numeric(df[field], errors="coerce").notna() & (df.index >= t0) & (df.index <= t1)
    return pd.DatetimeIndex(pd.to_datetime(df.loc[keep, DATE_FIELD]).dt.normalize().unique())


def observations_per_month(
    sources: Dict[str, "object"],
    window: Tuple[int, int],
    order: Sequence[str] = DEFAULT_ORDER,
    excluded: Iterable[str] = (),
    field: str = NDVI_CLEAN_FIELD,
    peak_season: Tuple[int, int] = (12, 3),
) -> pd.DataFrame:
    """Wide table: one row per calendar month of the window plus Total and peak-season rows,
    one column per source (``_B`` replacement files merged into their primary), integer counts."""
    excluded = set(excluded)
    # the window is a naive-local timestamp; invert it the way the loader built it
    w0, w1 = pd.Timestamp(datetime.fromtimestamp(window[0])), pd.Timestamp(datetime.fromtimestamp(window[1]))
    months = pd.period_range(w0, w1, freq="M")

    dates: Dict[str, pd.DatetimeIndex] = {}
    for name in order:
        if name not in sources:
            warnings.warn(f"observations_per_month: source '{name}' not found, skipped")
            continue
        df = sources[name].processed
        if f"{name}_B" in sources:
            df = merge_processed(df, sources[f"{name}_B"].processed)
        label = f"{name} (excluded)" if name in excluded else name
        dates[label] = _kept_dates(df, window, field)

    rows = {str(m): {c: int((d.to_period("M") == m).sum()) for c, d in dates.items()} for m in months}
    rows["Total"] = {c: len(d) for c, d in dates.items()}

    m0, m1 = peak_season
    for y in range(w0.year - 1, w1.year + 1):
        s0 = pd.Timestamp(y, m0, 1)
        s1 = pd.Timestamp(y + 1, m1, 1) + pd.offsets.MonthEnd(0) + pd.Timedelta(hours=23, minutes=59, seconds=59)
        if s0 >= w0 and s1 <= w1:
            label = f"{s0:%b %Y} – {s1:%b %Y}"
            rows[label] = {c: int(((d >= s0) & (d <= s1)).sum()) for c, d in dates.items()}

    out = pd.DataFrame.from_dict(rows, orient="index", columns=list(dates)).astype(int)
    out.index.name = "month"
    return out.reset_index()
