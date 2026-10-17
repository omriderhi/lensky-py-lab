"""Re-audit of the S2 outlier floor on the single-product (harmonised) S2 series.

The 0.08 floor was chosen on the earlier mixed-version S2 export. This sweeps the floor
(and window) on the regenerated series and compares each setting with no outlier filter
and with the NSRS ground sensors. Reuses the pipeline of satellite_cleaning_audit.py.
Writes to data/results/s2_floor_reaudit/ (gitignored).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import satellite_cleaning_audit as a
from lensky_py_lab import SourceConfig
from lensky_py_lab.constants import NDVI_CLEAN_FIELD, NDVI_FILTERED_FIELD
from lensky_py_lab.pipeline.cleaner import filter_outliers_sliding_window

OUT = a.REPO / "data" / "results" / "s2_floor_reaudit"
OUT.mkdir(parents=True, exist_ok=True)
SAT, C = "S2", a.SAT_CFG["S2"]
FLOORS = [0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15]
WINDOWS = [5, 7, 11, 15]


def clean(df, floor=0.02, window=7, k=3.0, **_):
    c = SourceConfig(outlier_window=window, outlier_k=k, outlier_min_threshold=floor)
    return filter_outliers_sliding_window(df, c)[NDVI_CLEAN_FIELD]


def run(variant, fn, **kw):
    return a.run_source(SAT, C, fn, kw)


def dt(ts):
    return pd.to_datetime(ts, unit="s").strftime("%Y-%m-%d")


variants = {"none": run("none", a.clean_none)}
for f in FLOORS:
    variants[f"w7_f{f:.2f}"] = run("x", clean, floor=f, window=7)
base = variants["none"]
filt = pd.to_numeric(base[NDVI_FILTERED_FIELD], errors="coerce").dropna()
print(f"S2 valid observations after extreme filter: {len(filt)}; top-5 values: "
      f"{filt.sort_values(ascending=False).head(5).round(3).tolist()}")

rows, ph_rows, t4_rows = [], [], []
for name, df in variants.items():
    kept = df[NDVI_CLEAN_FIELD].dropna()
    removed = filt.index.difference(kept.index)
    med = filt.rolling(7, center=True, min_periods=1).median()
    sign = (filt.loc[removed] - med.loc[removed])
    top5 = filt.sort_values(ascending=False).head(5).index
    ph, t4, dr = a.evaluate(SAT, C, df)
    rows.append(dict(variant=name, n_removed=len(removed), n_below=int((sign < 0).sum()),
                     n_above=int((sign > 0).sum()), top5_removed=int(len(set(top5) & set(removed))),
                     rmse_vs_nsrs=dr.get("rmse"), r_vs_nsrs=dr.get("r"), bias_vs_nsrs=dr.get("bias"),
                     n_overlap=dr.get("n_overlap")))
    ph = ph.assign(variant=name); ph_rows.append(ph)
    if len(t4):
        t4_rows.append(t4.assign(variant=name))
summary = pd.DataFrame(rows).round(3)
ph = pd.concat(ph_rows); t4 = pd.concat(t4_rows).round(3)
summary.to_csv(OUT / "floor_summary.csv", index=False)
ph.to_csv(OUT / "floor_phenology.csv", index=False)
t4.to_csv(OUT / "floor_table4.csv", index=False)
pd.set_option("display.width", 250, "display.max_columns", 30)
print("\n== removal and agreement with NSRS (window 7, k 3)"); print(summary.to_string(index=False))
order = list(variants)
for m in ["PoS_value", "PoS_doy", "SoS_doy", "EoS_doy"]:
    print(f"\n== {m}"); print(ph.pivot(index="year", columns="variant", values=m)[order].round(3).to_string())
print("\n== Table 4 full signal"); print(t4[t4.component == "Full signal"][["variant", "n", "mae", "rmse", "r", "bias"]].to_string(index=False))

# which points does each floor remove (window 7)
rem = []
for f in FLOORS:
    k = variants[f"w7_f{f:.2f}"][NDVI_CLEAN_FIELD].dropna().index
    for ts in filt.index.difference(k):
        rem.append(dict(floor=f, date=dt(ts), value=round(float(filt.loc[ts]), 3),
                        local_median=round(float(med.loc[ts]), 3)))
rem = pd.DataFrame(rem); rem.to_csv(OUT / "removed_points.csv", index=False)
print("\n== points removed at floor 0.08 and at 0.02:")
print(rem[rem.floor.isin([0.02, 0.08])].to_string(index=False))

# window x floor grid
grid = []
for w in WINDOWS:
    for f in [0.02, 0.05, 0.08, 0.10, 0.15]:
        df = run("g", clean, floor=f, window=w)
        kept = df[NDVI_CLEAN_FIELD].dropna()
        p, _, d = a.evaluate(SAT, C, df)
        pv = p.set_index("year")["PoS_value"]
        grid.append(dict(window=w, floor=f, n_removed=len(filt) - len(kept),
                         PoS2020=pv.get(2020), PoS2021=pv.get(2021), rmse=d.get("rmse"), r=d.get("r")))
grid = pd.DataFrame(grid).round(3); grid.to_csv(OUT / "window_floor_grid.csv", index=False)
print("\n== window x floor grid"); print(grid.to_string(index=False))

# figure
fig, ax = plt.subplots(figsize=(14, 4.5))
x = pd.to_datetime(filt.index, unit="s")
ax.scatter(x, filt.values, s=14, c="0.6", label="after extreme filter")
for f, col, mk in [(0.02, "#D55E00", "x"), (0.08, "#0072B2", "o")]:
    k = variants[f"w7_f{f:.2f}"][NDVI_CLEAN_FIELD].dropna().index
    r = filt.index.difference(k)
    ax.scatter(pd.to_datetime(r, unit="s"), filt.loc[r].values, s=70, marker=mk, facecolors="none" if mk == "o" else col,
               edgecolors=col, label=f"removed, floor {f:.2f} ({len(r)})", zorder=3)
ax.set(title="S2 (harmonised): points removed by the outlier filter, window 7, k 3", ylabel="NDVI")
ax.legend(); fig.tight_layout(); fig.savefig(OUT / "removed_points.png", dpi=150)
print("\nwritten to", OUT)
