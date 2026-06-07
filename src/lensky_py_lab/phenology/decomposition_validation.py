"""Validation of NDVI woody/herbaceous decomposition against layer-specific NSRS sensors.

This module quantifies how well the satellite-derived decomposition reproduces the
three near-surface remote-sensing (NSRS) reference sensors installed at the Ramat
Hanadiv study site:

    * full mixed-pixel signal   <-> NSRS_3 (hemispherical, wide-angle / satellite proxy)
    * woody baseline component  <-> NSRS_2 (downward, pine-canopy)
    * herbaceous residual       <-> NSRS_1 (downward, understory)

It reproduces the numbers reported in Table 4 of the manuscript.

Repository: https://github.com/omrid/Lensky-py-lab

Note
----
The herbaceous term produced by the decomposition is a *contribution* to the
mixed-pixel NDVI (a delta-NDVI above the woody baseline), whereas NSRS_1 measures the
understory's own full-cover NDVI. The two are therefore not on the same scale: a large
MAE / bias for the herbaceous comparison reflects a quantity difference, not a model
error. The informative metric for that pair is the Pearson correlation (timing), which
is high (~0.93). See the manuscript discussion (Section 3.2) for the full argument.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Maps each decomposed quantity to the NSRS sensor it is compared against, and the
# column that holds it. "full" is taken from the master table (smoothed satellite NDVI);
# "woody" / "herbaceous" come from the decomposition output.
COMPARISONS = {
    "Full signal": {"source": "master", "nsrs": "NDVI lowess NSRS_3"},
    "Woody":       {"source": "woody",  "nsrs": "NDVI lowess NSRS_2"},
    "Herbaceous":  {"source": "herbaceous", "nsrs": "NDVI lowess NSRS_1"},
}


def _pair_metrics(estimate: pd.Series, reference: pd.Series) -> dict | None:
    """Compute agreement metrics between an estimate and a reference series.

    Both series are aligned on their shared index; only timestamps where *both*
    values are present are used.

    Parameters
    ----------
    estimate : pandas.Series
        Decomposed / satellite quantity, indexed by timestamp.
    reference : pandas.Series
        NSRS reference quantity, indexed by the same timestamp key.

    Returns
    -------
    dict or None
        Keys ``n``, ``mae``, ``rmse``, ``r``, ``bias`` (bias = mean(estimate -
        reference)). Returns ``None`` if fewer than three paired observations exist,
        because correlation is not meaningful below that.
    """
    paired = pd.concat([estimate.rename("est"), reference.rename("ref")], axis=1).dropna()
    if len(paired) < 3:
        return None
    diff = paired["est"] - paired["ref"]
    return {
        "n": int(len(paired)),
        "mae": float(np.mean(np.abs(diff))),
        "rmse": float(np.sqrt(np.mean(diff ** 2))),
        "r": float(np.corrcoef(paired["est"], paired["ref"])[0, 1]),
        "bias": float(np.mean(diff)),
    }


def compute_decomposition_stats(
    satellite: str,
    decomposition: pd.DataFrame,
    master: pd.DataFrame,
    ts_col: str = "TS",
) -> pd.DataFrame:
    """Compare a satellite decomposition against the three layer-specific NSRS sensors.

    Parameters
    ----------
    satellite : str
        Label used both to select the satellite's smoothed NDVI column in ``master``
        (expected column name ``"NDVI lowess {satellite}"``) and to tag the output
        rows, e.g. ``"MODIS"`` or ``"S2"``.
    decomposition : pandas.DataFrame
        Decomposition output with a timestamp column plus ``"woody"`` and
        ``"herbaceous"`` columns (e.g. ``RH_NDVI_MODIS_decomposition.csv``).
    master : pandas.DataFrame
        Master result table with the timestamp column, the satellite's smoothed NDVI
        column, and the NSRS columns ``"NDVI lowess NSRS_1/2/3"``
        (e.g. ``RH_NDVI_final_result.csv``).
    ts_col : str, optional
        Name of the timestamp column shared by both tables. Default ``"TS"``.

    Returns
    -------
    pandas.DataFrame
        One row per comparison (Full signal, Woody, Herbaceous) with columns
        ``satellite``, ``component``, ``reference``, ``n``, ``mae``, ``rmse``, ``r``,
        ``bias``. Comparisons with fewer than three paired dates are skipped.

    Notes
    -----
    All series are reindexed onto the master timestamp axis before pairing, so the
    decomposition and master tables must share the same timestamp convention (they do
    in this project: every decomposition timestamp is also present in the master table).
    """
    dec = decomposition.set_index(ts_col)
    mas = master.set_index(ts_col)

    sat_col = f"NDVI lowess {satellite}"
    if sat_col not in mas.columns:
        raise KeyError(f"expected satellite column {sat_col!r} in master table")

    series = {
        "master": mas[sat_col],
        "woody": dec["woody"].reindex(mas.index),
        "herbaceous": dec["herbaceous"].reindex(mas.index),
    }

    rows = []
    for component, spec in COMPARISONS.items():
        m = _pair_metrics(series[spec["source"]], mas[spec["nsrs"]])
        if m is None:
            continue
        rows.append({
            "satellite": satellite,
            "component": component,
            "reference": spec["nsrs"].replace("NDVI lowess ", ""),
            **m,
        })
    return pd.DataFrame(rows)


def build_table4(
    master_csv: str = "RH_NDVI_final_result.csv",
    modis_csv: str = "RH_NDVI_MODIS_decomposition.csv",
    s2_csv: str = "RH_NDVI_S2_decomposition.csv",
) -> pd.DataFrame:
    """Reproduce the manuscript's Table 4 from the project CSVs.

    Returns
    -------
    pandas.DataFrame
        Stacked MODIS and Sentinel-2 comparison rows, rounded for display.
    """
    master = pd.read_csv(master_csv)
    out = pd.concat([
        compute_decomposition_stats("MODIS", pd.read_csv(modis_csv), master),
        compute_decomposition_stats("S2", pd.read_csv(s2_csv), master),
    ], ignore_index=True)
    return out.round({"mae": 3, "rmse": 3, "r": 3, "bias": 3})


if __name__ == "__main__":
    table4 = build_table4()
    with pd.option_context("display.width", 120, "display.max_columns", None):
        print(table4.to_string(index=False))
