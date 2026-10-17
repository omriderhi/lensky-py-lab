"""Observation-window filter with a per-source threshold floor (config-only fix).

MODIS keeps the current floor (0.02); S2 uses 0.08; L8 uses 0.10. Compared with the
current filter (A), no outlier filter (D) and the calendar/downward-only option (C),
using the pipeline of satellite_cleaning_audit.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
import satellite_cleaning_audit as a
from lensky_py_lab import SourceConfig
from lensky_py_lab.constants import NDVI_CLEAN_FIELD
from lensky_py_lab.pipeline.cleaner import filter_outliers_sliding_window

FLOORS = {"MODIS": 0.02, "S2": 0.08, "L8": 0.10}


def clean_floor(df, floor=0.02, **_):
    c = SourceConfig(outlier_window=7, outlier_k=3.0, outlier_min_threshold=floor)
    return filter_outliers_sliding_window(df, c)[NDVI_CLEAN_FIELD]


ph_all, t4_all, dr_all = [], [], []
for sat, c in a.SAT_CFG.items():
    for vn, fn, kw in [("A_current", a.clean_window, {}),
                       ("F_floor", clean_floor, dict(floor=FLOORS[sat])),
                       ("C_time15d_down", a.clean_time, dict(one_sided=True)),
                       ("D_none", a.clean_none, {})]:
        df = a.run_source(sat, c, fn, kw)
        ph, t4, dr = a.evaluate(sat, c, df)
        ph.insert(0, "variant", vn); t4 = t4.copy(); t4.insert(0, "variant", vn)
        ph_all.append(ph); t4_all.append(t4)
        dr_all.append(dict(satellite=sat, variant=vn, n_clean=int(df[NDVI_CLEAN_FIELD].count()), **dr))
ph = pd.concat(ph_all); t4 = pd.concat(t4_all).round(3); dr = pd.DataFrame(dr_all).round(3)
ph.to_csv(a.OUT / "floor_phenology.csv", index=False)
t4.to_csv(a.OUT / "floor_table4.csv", index=False)
dr.to_csv(a.OUT / "floor_direct.csv", index=False)
pd.set_option("display.width", 250, "display.max_rows", 200)
order = ["A_current", "F_floor", "C_time15d_down", "D_none"]
for m in ["PoS_value", "PoS_doy", "SoS_doy", "EoS_doy"]:
    for s in a.SAT_CFG:
        print(s, m); print(ph[ph.satellite == s].pivot(index="year", columns="variant", values=m)[order].round(3).to_string())
print(dr.to_string(index=False))
print(t4[t4.component == "Full signal"].to_string(index=False))
