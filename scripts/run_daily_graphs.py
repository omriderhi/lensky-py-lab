"""
Generate intra-day NDVI figures from the raw Campbell .dat collection.

This script owns all preprocessing: it locates the raw .dat files, loads them
into a DataFrame, and hands that DataFrame to the package for analysis.

Usage (from repo root):
    python scripts/run_daily_graphs.py --dat-dir path/to/RH_data_collections

    The path can also be set via the RH_DAT_DIR environment variable:
        RH_DAT_DIR=path/to/RH_data_collections python scripts/run_daily_graphs.py

NSRS_3 sky-catch correction (optional, --nsrs3-factor):
    auto   derive the factor from the per-source NSRS CSVs in --data-dir
           (env RH_DATA_DIR), the same way run_rh_ndvi.py does  [default]
    none   leave sensor 3 uncalibrated
    <num>  apply that fixed factor
    If 'auto' is requested but no --data-dir is given, sensor 3 is left
    uncalibrated and a warning says so.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
import matplotlib; matplotlib.use("Agg")  # noqa: E402

from lensky_py_lab import DataSource, SourceConfig
from lensky_py_lab.sensors.daily_graphs import load_dat_dir, generate_daily_outputs
from lensky_py_lab.sensors.nsrs_calibration import (
    calibrate_nsrs3_sources,
    clear_active_factor,
    set_active_factor,
)

# Same NSRS cleaning settings as run_rh_ndvi.py (verbatim from the notebook).
_NSRS_CONFIG = {"min": 0.2, "max": False, "average_window": 0.05, "images_per_month": 30}
_NSRS_NAMES = ("NSRS_1", "NSRS_2", "NSRS_3", "NSRS_1_B", "NSRS_2_B", "NSRS_3_B")

# ── configure paths ───────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Generate intra-day NDVI figures from raw .dat files.")
parser.add_argument("--dat-dir", default=os.environ.get("RH_DAT_DIR"),
                    help="Directory with raw Campbell .dat files (env: RH_DAT_DIR).")
parser.add_argument("--out-dir", default="data/results/figures/daily",
                    help="Output directory for daily figures.")
parser.add_argument("--data-dir", default=os.environ.get("RH_DATA_DIR"),
                    help="Directory with per-source NSRS CSVs, used to derive the NSRS_3 "
                         "factor (env: RH_DATA_DIR).")
parser.add_argument("--nsrs3-factor", default="auto", metavar="auto|none|NUMBER",
                    help="NSRS_3 sky-catch correction: 'auto' derives it from the data "
                         "(default), 'none' leaves sensor 3 uncalibrated, a number applies "
                         "that factor.")
args = parser.parse_args()

if not args.dat_dir:
    parser.error("Provide --dat-dir or set the RH_DAT_DIR environment variable.")

DAT_DIR = Path(args.dat_dir)
OUT_DIR = Path(args.out_dir)

# ── NSRS_3 factor (optional): derived from data, fixed, or none ───────────────
clear_active_factor()
mode = str(args.nsrs3_factor).lower()
if mode == "auto":
    if args.data_dir:
        nsrs = {
            n: DataSource.from_csv(n, Path(args.data_dir) / f"{n}.csv",
                                   SourceConfig.from_notebook_dict(_NSRS_CONFIG)).process()
            for n in _NSRS_NAMES if (Path(args.data_dir) / f"{n}.csv").exists()
        }
        try:
            result, _ = calibrate_nsrs3_sources(nsrs)
            print(f"NSRS_3 factor derived from data: {result['optimal_factor']:.3f}")
        except ValueError as exc:
            print(f"NSRS_3 calibration skipped: {exc} — sensor 3 left uncalibrated.")
    else:
        print("No --data-dir / RH_DATA_DIR: NSRS_3 factor not derived — sensor 3 left uncalibrated.")
elif mode == "none":
    print("NSRS_3 calibration disabled — sensor 3 left uncalibrated.")
else:
    set_active_factor(float(args.nsrs3_factor))
    print(f"NSRS_3 fixed factor: {float(args.nsrs3_factor):.3f}")

# ── preprocessing (script responsibility) ────────────────────────────────────
df = load_dat_dir(DAT_DIR, recursive=True)

# ── analysis (package) ───────────────────────────────────────────────────────
saved = generate_daily_outputs(df, OUT_DIR)
for p in saved:
    print(f"Saved → {p}")
