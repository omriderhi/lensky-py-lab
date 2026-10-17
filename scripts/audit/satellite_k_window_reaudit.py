"""Sensitivity of the satellite outlier filter to window and k on the current series.

Closes two open items of the cleaning audit: k was never varied on the regenerated S2 series, and the
L8 filter was not re-audited after L8 was re-extracted (Collection 2). For MODIS, S2 and L8 it runs the
observation-window filter over window x k (at each source's configured floor) and reports how many points
are removed and how far the phenology markers move from the configured setting (window 7, k 3). For L8 it
also sweeps the floor. Reuses the pipeline of satellite_cleaning_audit.py.
Writes to data/results/satellite_k_window_reaudit/ (gitignored).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import pandas as pd
import satellite_cleaning_audit as a
from lensky_py_lab import SourceConfig
from lensky_py_lab.constants import NDVI_CLEAN_FIELD, NDVI_FILTERED_FIELD
from lensky_py_lab.pipeline.cleaner import filter_outliers_sliding_window

OUT = a.REPO / "data" / "results" / "satellite_k_window_reaudit"
OUT.mkdir(parents=True, exist_ok=True)
FLOOR = {"MODIS": 0.02, "S2": 0.08, "L8": 0.10}   # as configured in scripts/run_rh_ndvi.py
WINDOWS = [5, 7, 11, 15]
KS = [2.5, 3.0, 4.0]
L8_FLOORS = [0.02, 0.05, 0.10, 0.15]


def clean(df, window=7, k=3.0, floor=0.02, **_):
    c = SourceConfig(outlier_window=window, outlier_k=k, outlier_min_threshold=floor)
    return filter_outliers_sliding_window(df, c)[NDVI_CLEAN_FIELD]


def metrics(sat, df, filt_n):
    ph, t4, dr = a.evaluate(sat, a.SAT_CFG[sat], df)
    kept = int(df[NDVI_CLEAN_FIELD].count())
    row = dict(n_removed=filt_n - kept, rmse_vs_nsrs=dr.get("rmse"), r_vs_nsrs=dr.get("r"))
    for _, r in ph.iterrows():
        y = int(r.year)
        row[f"PoS_value_{y}"] = round(float(r.PoS_value), 3)
        row[f"PoS_doy_{y}"] = int(r.PoS_doy)
        row[f"SoS_doy_{y}"] = int(r.SoS_doy)
        row[f"EoS_doy_{y}"] = int(r.EoS_doy) if pd.notna(r.EoS_doy) else np.nan
    return row


rows = []
for sat in ("MODIS", "S2", "L8"):
    base = a.run_source(sat, a.SAT_CFG[sat], a.clean_none, {})
    filt_n = int(pd.to_numeric(base[NDVI_FILTERED_FIELD], errors="coerce").count())
    combos = [(w, k, FLOOR[sat]) for w in WINDOWS for k in KS]
    if sat == "L8":
        combos += [(7, 3.0, f) for f in L8_FLOORS if f != FLOOR[sat]]
    rows.append(dict(source=sat, window="none", k=np.nan, floor=np.nan, **metrics(sat, base, filt_n)))
    for w, k, f in combos:
        df = a.run_source(sat, a.SAT_CFG[sat], clean, dict(window=w, k=k, floor=f))
        rows.append(dict(source=sat, window=w, k=k, floor=f, **metrics(sat, df, filt_n)))
res = pd.DataFrame(rows)
res.to_csv(OUT / "k_window_grid.csv", index=False)

pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 200)
for sat in ("MODIS", "S2", "L8"):
    g = res[res.source == sat]
    ref = g[(g.window == 7) & (g.k == 3.0) & (g.floor == FLOOR[sat])].iloc[0]
    pos_cols = [c for c in g.columns if c.startswith("PoS_value_")]
    doy_cols = [c for c in g.columns if c.startswith(("PoS_doy_", "EoS_doy_"))]
    sub = g[g.window != "none"].copy()
    sub["max_dPoS_value"] = sub[pos_cols].sub(ref[pos_cols].astype(float)).abs().max(axis=1).round(3)
    sub["max_dDOY_PoS_EoS"] = sub[doy_cols].sub(ref[doy_cols].astype(float)).abs().max(axis=1)
    print(f"\n== {sat}: reference window 7, k 3, floor {FLOOR[sat]}; no-filter row first")
    cols = ["window", "k", "floor", "n_removed", "rmse_vs_nsrs", "max_dPoS_value", "max_dDOY_PoS_EoS"]
    nofilt = g[g.window == "none"].assign(max_dPoS_value=lambda d: d[pos_cols].sub(ref[pos_cols].astype(float)).abs().max(axis=1).round(3),
                                          max_dDOY_PoS_EoS=lambda d: d[doy_cols].sub(ref[doy_cols].astype(float)).abs().max(axis=1))
    print(pd.concat([nofilt, sub])[cols].round(3).to_string(index=False))
print("\nwritten to", OUT)
