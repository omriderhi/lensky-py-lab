"""
Generate intra-day NDVI figures from the raw Campbell .dat collection.

This script owns all preprocessing: it locates the raw .dat files, loads them
into a DataFrame, and hands that DataFrame to the package for analysis.

Usage (from repo root):
    python scripts/run_daily_graphs.py --dat-dir path/to/RH_data_collections

    The path can also be set via the RH_DAT_DIR environment variable:
        RH_DAT_DIR=path/to/RH_data_collections python scripts/run_daily_graphs.py
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
import matplotlib; matplotlib.use("Agg")  # noqa: E402

from lensky_py_lab.sensors.daily_graphs import load_dat_dir, generate_daily_outputs

# ── configure paths ───────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Generate intra-day NDVI figures from raw .dat files.")
parser.add_argument("--dat-dir", default=os.environ.get("RH_DAT_DIR"),
                    help="Directory with raw Campbell .dat files (env: RH_DAT_DIR).")
parser.add_argument("--out-dir", default="data/results/figures/daily",
                    help="Output directory for daily figures.")
args = parser.parse_args()

if not args.dat_dir:
    parser.error("Provide --dat-dir or set the RH_DAT_DIR environment variable.")

DAT_DIR = Path(args.dat_dir)
OUT_DIR = Path(args.out_dir)

# ── preprocessing (script responsibility) ────────────────────────────────────
df = load_dat_dir(DAT_DIR, recursive=True)

# ── analysis (package) ───────────────────────────────────────────────────────
saved = generate_daily_outputs(df, OUT_DIR)
for p in saved:
    print(f"Saved → {p}")
