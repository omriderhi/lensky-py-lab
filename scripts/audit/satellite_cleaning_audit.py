"""Satellite cleaning audit (docs/features/satellite-data-cleaning-audit.md).

Compares outlier-filter designs for MODIS / S2 / L8 against raw data and the NSRS
ground sensors.  Reads data/research_results/RH_NDVI/*.csv (never modified) and
writes to data/results_satellite_audit/ (gitignored via the data/results_* pattern).

The pre-v12 "average_window" rule is reconstructed HERE ONLY, for comparison.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

REPO = Path(__file__).parents[2]
sys.path.insert(0, str(REPO / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

from lensky_py_lab import DataSource, Site, SourceConfig
from lensky_py_lab.constants import NDVI_CLEAN_FIELD, NDVI_FILTERED_FIELD, NDVI_LOWESS_FIELD, NDVI_RAW_FIELD
from lensky_py_lab.io.csv_loader import average_same_date, load_source_csv as _load_csv


def load_source_csv(path):
    """Load a source CSV; same-date rows are averaged (L8 adjacent-row duplicates)."""
    return average_same_date(_load_csv(path))

from lensky_py_lab.phenology.decomposition_validation import compute_decomposition_stats
from lensky_py_lab.phenology.phenolopy_integration import decompose_woody_herbaceous, extract_phenology
from lensky_py_lab.pipeline.cleaner import (
    filter_extreme_values, filter_outliers_sliding_window, filter_outliers_time_window,
)
from lensky_py_lab.pipeline.smoother import add_lowess
from lensky_py_lab.sensors.nsrs_calibration import calibrate_nsrs3_sources, clear_active_factor

warnings.filterwarnings("ignore")
DATA = REPO / "data" / "research_results" / "RH_NDVI"
OUT = REPO / "data" / "results_satellite_audit"
(OUT / "figures").mkdir(parents=True, exist_ok=True)

SAT_CFG = {
    "MODIS": dict(min=None, max=0.8, ipm=30, old_w=0.1125),
    "S2": dict(min=0.4, max=None, ipm=5, old_w=0.1005),
    "L8": dict(min=0.4, max=None, ipm=4, old_w=0.1005),
}
NSRS_CFG = dict(min=0.2, max=None, ipm=30)
NSRS_NAMES = ["NSRS_1", "NSRS_2", "NSRS_3", "NSRS_1_B", "NSRS_2_B", "NSRS_3_B"]
DAY = 86400


def cfg(c, window=7, k=3.0):
    return SourceConfig(min_value=c["min"], max_value=c["max"], outlier_window=window,
                        outlier_k=k, images_per_month=c["ipm"])


# ── cleaners: take df with "NDVI filtered", return a series aligned to df.index ──
def clean_none(df, **_):
    return pd.to_numeric(df[NDVI_FILTERED_FIELD], errors="coerce")


def clean_window(df, window=7, k=3.0, **_):
    c = SourceConfig(outlier_window=window, outlier_k=k)
    return filter_outliers_sliding_window(df, c)[NDVI_CLEAN_FIELD]


def clean_time(df, half_days=15, k=3.0, one_sided=False, **_):
    c = SourceConfig(outlier_window_days=half_days, outlier_k=k,
                     outlier_direction="down" if one_sided else "both")
    return filter_outliers_time_window(df, c)[NDVI_CLEAN_FIELD]


def clean_sg_envelope(df, window_days=45, polyorder=2, n_iter=8, tol_k=1.0, **_):
    """Simplified Chen et al. (2004)-style upper-envelope Savitzky-Golay.

    Daily-interpolate, iterate fit -> max(series, fit) so the fit climbs to the upper
    envelope (clouds only push NDVI down), then drop points far below the envelope.
    A sketch of the idea, not a faithful reimplementation.
    """
    x = pd.to_numeric(df[NDVI_FILTERED_FIELD], errors="coerce").dropna()
    if len(x) < 7:
        return x.reindex(df.index)
    t = x.index.values.astype(float)
    grid = np.arange(t[0], t[-1] + DAY, DAY)
    cur = np.interp(grid, t, x.values)
    w = min(int(window_days) | 1, (len(cur) // 2) * 2 - 1)
    for _ in range(n_iter):
        fit = savgol_filter(cur, w, polyorder)
        cur = np.maximum(cur, fit)
    env = np.interp(t, grid, fit)
    d = x.values - env
    bad = d < -max(0.05, tol_k * np.std(d))
    return pd.Series(np.where(bad, np.nan, x.values), index=x.index).reindex(df.index)


def clean_old_rule(df, old_w=0.1, **_):
    """Pre-v12 average_window rule: keep ONLY values with |x - global mean| >= old_w."""
    x = pd.to_numeric(df[NDVI_FILTERED_FIELD], errors="coerce")
    return x.where((x - x.mean()).abs() >= old_w)


VARIANTS = {
    "old_rule":       (clean_old_rule, {}),
    "A_window7_k3":   (clean_window, dict(window=7, k=3.0)),
    "B_time15d_k3":   (clean_time, dict(half_days=15, k=3.0)),
    "C_time15d_down": (clean_time, dict(half_days=15, k=3.0, one_sided=True)),
    "D_none":         (clean_none, {}),
    "E_SG_envelope":  (clean_sg_envelope, {}),
}


def run_source(name, c, cleaner, kw):
    df = filter_extreme_values(load_source_csv(DATA / f"{name}.csv"), cfg(c))
    kw = dict(kw)
    if cleaner is clean_old_rule:
        kw["old_w"] = c["old_w"]
    df[NDVI_CLEAN_FIELD] = cleaner(df, **kw)
    return add_lowess(df, cfg(c))


_nsrs = {}


def nsrs_sources():
    if "s" not in _nsrs:
        clear_active_factor()
        srcs = {}
        for n in NSRS_NAMES:
            ds = DataSource.from_csv(n, DATA / f"{n}.csv", cfg(NSRS_CFG))
            ds.process()
            srcs[n] = ds
        res, _ = calibrate_nsrs3_sources(srcs)
        _nsrs["s"], _nsrs["factor"] = srcs, res["optimal_factor"]
    return _nsrs["s"]


def evaluate(sat, c, df):
    """Phenology + Table-4 metrics + direct NSRS agreement for one processed satellite."""
    ds = DataSource(name=sat, config=cfg(c), raw_data=load_source_csv(DATA / f"{sat}.csv"))
    ds._processed = df
    sdf = Site(name="RH", nsrs_sources=nsrs_sources(), satellite_sources={sat: ds}).run_analysis()
    col = f"{NDVI_LOWESS_FIELD} {sat}"
    pheno = extract_phenology(sdf, source_columns=[col], site_name="RH")
    t4 = pd.DataFrame()
    w, h = decompose_woody_herbaceous(sdf[col].dropna())
    if w is not None:
        dec = pd.DataFrame({"woody": w, "herbaceous": h}).reset_index()
        dec.columns = ["TS", "woody", "herbaceous"]
        m = sdf.reset_index()
        m = m.rename(columns={m.columns[0]: "TS"})
        t4 = compute_decomposition_stats(sat, dec, m)
    nsrs_mean = sdf[[f"{NDVI_LOWESS_FIELD} NSRS_{i}" for i in (1, 2, 3)]].mean(axis=1)
    p = pd.concat([sdf[col], nsrs_mean], axis=1).dropna()
    direct = {}
    if len(p) > 3:
        d = p.iloc[:, 0] - p.iloc[:, 1]
        direct = dict(n_overlap=len(p), bias=d.mean(), rmse=float(np.sqrt((d ** 2).mean())),
                      r=float(np.corrcoef(p.iloc[:, 0], p.iloc[:, 1])[0, 1]))
    return pheno, t4, direct


def removal_stats(sat, c):
    """What each cleaner removes: count, season, level, sign relative to local median."""
    base = filter_extreme_values(load_source_csv(DATA / f"{sat}.csv"), cfg(c))
    x = pd.to_numeric(base[NDVI_FILTERED_FIELD], errors="coerce")
    n0 = int(x.notna().sum())
    month = pd.Series(pd.to_datetime(base.index, unit="s").month, index=base.index)
    med = x.dropna().rolling(7, center=True, min_periods=3).median().reindex(x.index)
    rows = []
    for vn, (fn, kw) in VARIANTS.items():
        kw = dict(kw)
        if fn is clean_old_rule:
            kw["old_w"] = c["old_w"]
        cl = fn(base, **kw)
        rem = x.notna() & cl.isna()
        rv, mo = x[rem], month[rem]
        kept = x[x.notna() & ~rem]
        rows.append(dict(
            source=sat, variant=vn, n_in=n0, n_removed=int(rem.sum()),
            pct_removed=round(100 * rem.sum() / n0, 1),
            n_below_local_median=int((rv < med[rem]).sum()),
            n_above_local_median=int((rv > med[rem]).sum()),
            n_removed_Dec_Apr=int(mo.isin([12, 1, 2, 3, 4]).sum()),
            n_removed_Jun_Aug=int(mo.isin([6, 7, 8]).sum()),
            removed_ndvi_mean=round(float(rv.mean()), 3) if len(rv) else np.nan,
            kept_ndvi_mean=round(float(kept.mean()), 3),
            kept_ndvi_sd=round(float(kept.std()), 3),
            raw_ndvi_sd=round(float(x.std()), 3),
        ))
    return rows


def main():
    stats, ph_all, t4_all, direct_all = [], [], [], []
    store = {}

    def record(sat, c, vn, df):
        ph, t4, direct = evaluate(sat, c, df)
        ph.insert(0, "variant", vn)
        t4 = t4.copy()
        t4.insert(0, "variant", vn)
        ph_all.append(ph)
        t4_all.append(t4)
        direct_all.append(dict(satellite=sat, variant=vn, n_clean=int(df[NDVI_CLEAN_FIELD].count()), **direct))

    for sat, c in SAT_CFG.items():
        stats += removal_stats(sat, c)
        for vn, (fn, kw) in VARIANTS.items():
            store[(sat, vn)] = df = run_source(sat, c, fn, kw)
            record(sat, c, vn, df)
        for w in (5, 7, 11, 15):
            for k in (2.5, 3.0, 4.0):
                record(sat, c, f"A_w{w}_k{k}", run_source(sat, c, clean_window, dict(window=w, k=k)))
        print(sat, "done", flush=True)

    pd.DataFrame(stats).to_csv(OUT / "q1_removal_stats.csv", index=False)
    pd.concat(ph_all, ignore_index=True).to_csv(OUT / "phenology_by_variant.csv", index=False)
    pd.concat(t4_all, ignore_index=True).round(3).to_csv(OUT / "table4_by_variant.csv", index=False)
    pd.DataFrame(direct_all).round(3).to_csv(OUT / "direct_nsrs_agreement.csv", index=False)

    for sat in SAT_CFG:
        raw = load_source_csv(DATA / f"{sat}.csv")
        fig, ax = plt.subplots(figsize=(13, 5))
        ax.scatter(pd.to_datetime(raw.index, unit="s"), pd.to_numeric(raw[NDVI_RAW_FIELD], errors="coerce"),
                   s=6, c="lightgrey", label="raw")
        for vn, col, mk in [("old_rule", "tab:red", "x"), ("A_window7_k3", "tab:blue", "o"),
                            ("C_time15d_down", "tab:green", "+")]:
            df = store[(sat, vn)]
            ax.scatter(pd.to_datetime(df.index, unit="s"), df[NDVI_CLEAN_FIELD], s=10, c=col,
                       marker=mk, label=f"kept: {vn}", alpha=.7)
        for vn, col in [("old_rule", "tab:red"), ("A_window7_k3", "tab:blue"), ("D_none", "k")]:
            lw = store[(sat, vn)][NDVI_LOWESS_FIELD].dropna()
            ax.plot(pd.to_datetime(lw.index, unit="s"), lw.values, c=col, lw=1.2, label=f"LOWESS {vn}")
        ax.set_title(f"{sat}: raw vs cleaned")
        ax.set_ylabel("NDVI")
        ax.legend(fontsize=7, ncol=3)
        fig.savefig(OUT / "figures" / f"{sat}_cleaning_variants.png", dpi=130, bbox_inches="tight")
        plt.close(fig)
    print("NSRS_3 factor (derived):", _nsrs["factor"])
    print("outputs ->", OUT)


if __name__ == "__main__":
    main()
