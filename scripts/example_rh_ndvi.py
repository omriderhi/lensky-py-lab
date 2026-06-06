"""
Minimal RH_NDVI pipeline example.
Demonstrates the full flow in as few lines as possible.

Usage (from repo root):
    python scripts/example_rh_ndvi.py --data-dir path/to/RH_NDVI --ims-dir path/to/IMS

    Paths can also be set via environment variables:
        RH_DATA_DIR   — directory containing per-source NDVI CSV files
        RH_IMS_DIR    — directory containing IMS CSV files
        RH_DAT_DIR    — directory with raw Campbell .dat files (optional)
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
import matplotlib; matplotlib.use("Agg")  # noqa: E402
import matplotlib.pyplot as plt

from lensky_py_lab import DataSource, Site, SourceConfig
from lensky_py_lab.io.csv_loader import discover_ims_csvs_for_site, load_ims_csvs
from lensky_py_lab.phenology import decompose_woody_herbaceous, extract_phenology
from lensky_py_lab.plotting.plotter import plot_data_availability
from lensky_py_lab.visualization.figure_generator import (
    plot_decomposition_comparative,
    plot_site_publication,
    save_figure,
)
from lensky_py_lab.sensors.daily_graphs import load_dat_dir, generate_daily_outputs

# ── paths ────────────────────────────────────────────────────────────────────
_REPO = Path(__file__).parents[1]

parser = argparse.ArgumentParser(description="Minimal RH_NDVI pipeline example.")
parser.add_argument("--data-dir", default=os.environ.get("RH_DATA_DIR", str(_REPO / "data/raw/RH")),
                    help="Directory containing per-source NDVI CSV files (env: RH_DATA_DIR).")
parser.add_argument("--ims-dir",  default=os.environ.get("RH_IMS_DIR",  str(_REPO / "data/raw/IMS")),
                    help="Directory containing IMS CSV files (env: RH_IMS_DIR).")
parser.add_argument("--dat-dir",  default=os.environ.get("RH_DAT_DIR"),
                    help="Directory with raw Campbell .dat files, optional (env: RH_DAT_DIR).")
parser.add_argument("--out-dir",  default=str(_REPO / "data/results/figures/final"),
                    help="Output directory for figures.")
args = parser.parse_args()

DATA    = Path(args.data_dir)
IMS     = Path(args.ims_dir)
OUT     = Path(args.out_dir)
DAT_DIR = Path(args.dat_dir) if args.dat_dir else None

# ── per-source configs (verbatim from notebook) ───────────────────────────────
CONFIGS = {
    "MODIS":    {"min": False, "max": 0.8,  "average_window": 0.1125, "images_per_month": 30},
    "S2":       {"min": 0.4,  "max": False, "average_window": 0.1005, "images_per_month": 5},
    "L8":       {"min": 0.4,  "max": False, "average_window": 0.1005, "images_per_month": 4},
    "NSRS_1":   {"min": 0.2,  "max": False, "average_window": 0.05,   "images_per_month": 30},
    "NSRS_2":   {"min": 0.2,  "max": False, "average_window": 0.05,   "images_per_month": 30},
    "NSRS_3":   {"min": 0.2,  "max": False, "average_window": 0.05,   "images_per_month": 30, "general_factor": 1.4},
    "NSRS_1_B": {"min": 0.2,  "max": False, "average_window": 0.05,   "images_per_month": 30},
    "NSRS_2_B": {"min": 0.2,  "max": False, "average_window": 0.05,   "images_per_month": 30},
    "NSRS_3_B": {"min": 0.2,  "max": False, "average_window": 0.05,   "images_per_month": 30, "general_factor": 1.4},
}

# ── load & process (skips missing files gracefully) ───────────────────────────
sources = {
    name: DataSource.from_csv(name, DATA / f"{name}.csv",
                              SourceConfig.from_notebook_dict(cfg)).process()
    for name, cfg in CONFIGS.items()
    if (DATA / f"{name}.csv").exists()
}

# ── build site & run analysis ─────────────────────────────────────────────────
ims_df  = load_ims_csvs(discover_ims_csvs_for_site("RH_NDVI", IMS))
site    = Site(
    name="Ramat Hanadiv",
    nsrs_sources={k: v for k, v in sources.items() if k.startswith("NSRS")},
    satellite_sources={k: v for k, v in sources.items() if not k.startswith("NSRS")},
    ims_data=ims_df,
)
site_df     = site.run_analysis()
phenology   = extract_phenology(site_df, site_name="Ramat Hanadiv",
                                output_csv=OUT / "phenology_markers.csv")

# ── plot & save ───────────────────────────────────────────────────────────────
fig   = plot_site_publication("Ramat Hanadiv", site_df)
paths = save_figure(fig, OUT, "RH_NDVI_timeseries")
for p in paths:
    print(f"Saved → {p}")

fig_avail = plot_data_availability("Ramat Hanadiv", site_df)
avail_path = OUT / "RH_NDVI_data_availability.png"
fig_avail.savefig(avail_path, dpi=150, bbox_inches="tight")
print(f"Saved → {avail_path}")

# ── decomposition (woody / herbaceous) ───────────────────────────────────────
from lensky_py_lab.constants import NDVI_LOWESS_FIELD

out_decomp = OUT.parent / "decomposition"
sat_cols = [c for c in site_df.columns
            if c.startswith(f"{NDVI_LOWESS_FIELD} ") and "NSRS" not in c]
for sat_col in sat_cols:
    sat_name = sat_col.removeprefix(f"{NDVI_LOWESS_FIELD} ")
    woody, herb = decompose_woody_herbaceous(site_df[sat_col].dropna(), min_dry_seasons=2)
    if woody is None:
        print(f"Decomposition skipped for {sat_name} — insufficient dry seasons")
        continue
    fig_d = plot_decomposition_comparative(
        "Ramat Hanadiv", site_df, sat_name, woody, herb, output_dir=out_decomp
    )
    plt.close(fig_d)
    print(f"Saved → {out_decomp / sat_name}_decomposition_vs_NSRS.png")

# ── daily graphs (intra-day NDVI from raw .dat files) ────────────────────────
if DAT_DIR is not None:
    nsrs_df = load_dat_dir(DAT_DIR, recursive=True)
    saved   = generate_daily_outputs(nsrs_df, _REPO / "data/results/figures/daily")
    for p in saved:
        print(f"Saved → {p}")
else:
    print("Skipping daily graphs — set RH_DAT_DIR or pass --dat-dir to enable.")
