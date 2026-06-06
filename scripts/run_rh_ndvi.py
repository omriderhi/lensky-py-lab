#!/usr/bin/env python
"""
Script: run_rh_ndvi.py
Description: Full RH_NDVI analysis pipeline — reproduces every output that the
             original research notebook produced, using the lensky_py_lab package.
Author: Omri Derhi
Institution: Bar-Ilan University
Date: 2025

Usage:
    # From the repo root (package installed or editable):
    python scripts/run_rh_ndvi.py

    # Override data directories:
    python scripts/run_rh_ndvi.py --data-dir path/to/RH_NDVI --ims-dir path/to/IMS

    # Provide a directory containing raw Campbell .dat files for intra-day figures:
    python scripts/run_rh_ndvi.py --dat-dir path/to/dat_files/

Inputs:
    $RH_DATA_DIR/{MODIS,S2,L8,NSRS_1,NSRS_2,NSRS_3,NSRS_1_B,NSRS_2_B,NSRS_3_B}.csv
    $RH_IMS_DIR/RH_*.csv
    daily_graphsxlsx.xlsx  (4-sheet workbook with 1-min intra-day NSRS data; set DAILY_GRAPHS_EXCEL)
    *.dat  (Campbell TOA5 raw datalogger files — used for dat-based daily figures)

Outputs (all under data/results/):
    figures/data_cleaning/RH_NDVI/<source>.png   — per-source cleaning pipeline
    figures/final/RH_NDVI_timeseries.png          — publication site time-series
    figures/comparative/<source>_vs_NSRS.png     — satellite vs NSRS overlays
    figures/final/RH_NDVI_timeseries.tiff         — publication site time-series
    figures/comparative/<source>_vs_NSRS.png          — satellite vs NSRS overlays
    figures/decomposition/<source>_decomposition_vs_NSRS.png  — 3-panel decomposition vs NSRS
    figures/calibration/NSRS3_calibration_*      — 4-panel calibration figure
    figures/daily_graphs/daily_ndvi_summary.png  — 4-panel seasonal intra-day NDVI
    figures/daily_graphs/<date>_ndvi.png         — per-day NDVI for all sensors
    figures/daily_graphs/<date>_bands_sensor1.png — NIR/Red irradiance for sensor 1
    figures/orientation/pixel_size_comparison.*  — MODIS/L8/S2 pixel grid schematic
    figures/orientation/site_location.*          — Mediterranean + Israel map (cartopy)
    RH_NDVI_final_result.csv                     — joined LOWESS time series
    phenology_markers.csv                        — SoS/PoS/EoS per year/satellite
    calibration_statistics.csv                   — NSRS_3 calibration metrics

Pipeline (mirrors the original notebook exactly):
    1. Load raw CSV  →  parse dates, set unix-timestamp index
    2. Filter extremes        (NDVI filtered)
    3. Filter by avg groups   (NDVI clean)      ← fixed the notebook's index bug
    4. LOWESS smooth          (NDVI lowess)
    5. Join all sources into site_df
    6. Merge NSRS_X + NSRS_X_B via forward-fill
    7. Attach IMS rainfall & temperature
    8. Generate all figures and CSVs
    9. NSRS_3 calibration validation (new)
   10. Phenological marker extraction (new)
   11. Intra-day NSRS daily graph figures (new)
   12. Orientation map + pixel-size comparison figures (new)
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path
from typing import Optional

# ── make the package importable when running as a plain script ───────────────
REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import matplotlib
matplotlib.use("Agg")   # non-interactive — safe for headless / file output
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from lensky_py_lab import DataSource, Site, SourceConfig
from lensky_py_lab.constants import (
    IMS_RAINFALL_FIELD,
    IMS_TEMPERATURE_FIELD,
    NDVI_CLEAN_FIELD,
    NDVI_LOWESS_FIELD,
)
from lensky_py_lab.io.csv_loader import discover_ims_csvs_for_site, load_ims_csvs
from lensky_py_lab.phenology.phenolopy_integration import (
    decompose_woody_herbaceous,
    extract_phenology,
)
from lensky_py_lab.plotting.plotter import plot_cleaning_pipeline, plot_site, plot_data_availability
from lensky_py_lab.sensors.nsrs_calibration import (
    create_calibration_figure,
    find_optimal_calibration_factor,
    save_calibration_statistics,
)
from lensky_py_lab.sensors.daily_graphs import (
    generate_daily_graph_outputs,
    generate_daily_outputs,
    load_dat_dir,
)
from lensky_py_lab.visualization.figure_generator import (
    plot_decomposition_comparative,
    plot_site_publication,
    save_figure,
)
from lensky_py_lab.visualization.orientation_map import (
    plot_pixel_size_comparison,
    plot_site_location,
)

# ── source configurations — verbatim from the original notebook ──────────────

NOTEBOOK_CONFIGS: dict = {
    # Satellite sources
    "MODIS":    {"min": False,  "max": 0.8,   "average_window": 0.1125, "images_per_month": 30},
    "S2":       {"min": 0.4,    "max": False,  "average_window": 0.1005, "images_per_month": 5},
    "L8":       {"min": 0.4,    "max": False,  "average_window": 0.1005, "images_per_month": 4},
    # Ground sensors
    "NSRS_1":   {"min": 0.2,    "max": False,  "average_window": 0.05,   "images_per_month": 30},
    "NSRS_2":   {"min": 0.2,    "max": False,  "average_window": 0.05,   "images_per_month": 30},
    "NSRS_3":   {"min": 0.2,    "max": False,  "average_window": 0.05,   "images_per_month": 30,
                 "general_factor": 1.4},   # wide-angle sky-catch correction ×1.4
    "NSRS_1_B": {"min": 0.2,    "max": False,  "average_window": 0.05,   "images_per_month": 30},
    "NSRS_2_B": {"min": 0.2,    "max": False,  "average_window": 0.05,   "images_per_month": 30},
    "NSRS_3_B": {"min": 0.2,    "max": False,  "average_window": 0.05,   "images_per_month": 30,
                 "general_factor": 1.4},
}

# Which sources are ground sensors (NSRS) vs satellite
_NSRS_SOURCES    = {k for k in NOTEBOOK_CONFIGS if k.startswith("NSRS")}
_SAT_SOURCES     = {k for k in NOTEBOOK_CONFIGS if not k.startswith("NSRS")}
_NSRS_BASE_NAMES = {k for k in NOTEBOOK_CONFIGS if k.startswith("NSRS") and not k.endswith("_B")}


# ────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ────────────────────────────────────────────────────────────────────────────

def run(data_dir: Path, ims_dir: Path, out_dir: Path, dat_dir: Optional[Path] = None) -> None:
    # ── output sub-directories ───────────────────────────────────────────────
    out_cleaning      = out_dir / "figures" / "data_cleaning" / "RH_NDVI"
    out_final         = out_dir / "figures" / "final"
    out_comparative   = out_dir / "figures" / "comparative"
    out_decomposition = out_dir / "figures" / "decomposition"
    out_calib         = out_dir / "figures" / "calibration"
    out_daily         = out_dir / "figures" / "daily_graphs"
    out_orientation   = out_dir / "figures" / "orientation"
    for d in (out_cleaning, out_final, out_comparative, out_decomposition,
              out_calib, out_daily, out_orientation):
        d.mkdir(parents=True, exist_ok=True)

    # ── Step 1–4: load and process every source ──────────────────────────────
    print("=" * 60)
    print("Step 1-4: Loading and processing sources")
    print("=" * 60)

    nsrs_sources: dict[str, DataSource] = {}
    sat_sources:  dict[str, DataSource] = {}

    # ── Pass A: process every source (no plotting yet) ───────────────────────
    all_processed: dict[str, DataSource] = {}

    for source_name, nb_cfg in NOTEBOOK_CONFIGS.items():
        csv_path = data_dir / f"{source_name}.csv"
        if not csv_path.exists():
            warnings.warn(f"[SKIP] {csv_path} not found — skipping {source_name}")
            continue

        config = SourceConfig.from_notebook_dict(nb_cfg)
        ds = DataSource.from_csv(source_name, csv_path, config)
        ds.process()   # runs filter_extreme_values → filter_by_average_groups → LOWESS

        n_clean  = ds.processed[NDVI_CLEAN_FIELD].count()
        n_lowess = ds.processed[NDVI_LOWESS_FIELD].count() if NDVI_LOWESS_FIELD in ds.processed else 0
        print(f"  {source_name:12s}  raw={len(ds.raw_data):4d}  "
              f"clean={n_clean:4d}  lowess={n_lowess:4d}")

        all_processed[source_name] = ds
        if source_name in _NSRS_SOURCES:
            nsrs_sources[source_name] = ds
        else:
            sat_sources[source_name] = ds

    # ── Pass B: generate data-cleaning figures ───────────────────────────────
    # NSRS base sources are merged with their _B variant and plotted once.
    # _B variants are skipped here — their data appears in the primary's figure.
    for source_name, ds in all_processed.items():
        if source_name.endswith("_B"):
            continue

        backup_name = f"{source_name}_B"
        if backup_name in all_processed:
            merged_df = _merge_processed_for_plot(
                ds.processed, all_processed[backup_name].processed
            )
            fig_clean = plot_cleaning_pipeline(source_name, merged_df)
        else:
            fig_clean = plot_cleaning_pipeline(source_name, ds.processed)

        fig_clean.savefig(out_cleaning / f"{source_name}.png", dpi=100, bbox_inches="tight")
        plt.close(fig_clean)
        print(f"    → {out_cleaning / source_name}.png")

    # ── Step 5–6: assemble Site and run analysis ─────────────────────────────
    print()
    print("=" * 60)
    print("Step 5-6: Assembling site and joining sources")
    print("=" * 60)

    site = Site(
        name="RH_NDVI",
        nsrs_sources=nsrs_sources,
        satellite_sources=sat_sources,
    )
    site_df = site.run_analysis()
    print(f"  site_df shape: {site_df.shape}")
    print(f"  columns: {list(site_df.columns)}")

    # ── Step 7: IMS data (rainfall + temperature) ────────────────────────────
    print()
    print("=" * 60)
    print("Step 7: Loading IMS meteorological data")
    print("=" * 60)

    ims_paths = discover_ims_csvs_for_site("RH", ims_dir)
    if ims_paths:
        raw_ims = load_ims_csvs(ims_paths, collect_rain_code=False)
        ims_df = _normalise_ims_columns(raw_ims)
        site.set_ims_data(ims_df)
        site_df = site.run_analysis()   # re-run to include IMS columns
        print(f"  IMS files: {[Path(p).name for p in ims_paths]}")
        print(f"  IMS columns: {list(ims_df.columns)}")
    else:
        warnings.warn(f"No IMS files found in {ims_dir}")
        ims_df = None

    # ── Step 8a: save final result CSV ───────────────────────────────────────
    csv_out = out_dir / "RH_NDVI_final_result.csv"
    site_df.to_csv(csv_out)
    print()
    print(f"Saved final_result.csv → {csv_out}")

    # ── Step 8b: phenological marker extraction (needed for figure annotation) ─
    print()
    print("=" * 60)
    print("Step 8b: Phenological marker extraction")
    print("=" * 60)

    pheno_df = extract_phenology(
        site_df,
        site_name="RH",
        output_csv=out_dir / "phenology_markers.csv",
    )

    if pheno_df.empty:
        print("  No phenological markers extracted (possibly insufficient data).")
    else:
        print(f"  Extracted {len(pheno_df)} marker rows:")
        print(pheno_df[["satellite", "year", "SoS_date", "PoS_date", "EoS_date"]].to_string(index=False))

    # ── Step 8c: site-level plots ────────────────────────────────────────────
    print()
    print("=" * 60)
    print("Step 8c: Generating site-level figures")
    print("=" * 60)

    pheno_arg = pheno_df if not pheno_df.empty else None

    # All sources — full time-series (no phenology markers on the main graph)
    fig_all = plot_site("RH_NDVI", site_df)
    fig_all.savefig(out_final / "RH_NDVI_all_data.png", dpi=150, bbox_inches="tight")
    plt.close(fig_all)
    print(f"  → {out_final / 'RH_NDVI_all_data.png'}")

    # All sources — clipped to NSRS timeframe (no phenology markers)
    nsrs_start, nsrs_end = _nsrs_timeframe(site_df)
    if nsrs_start and nsrs_end:
        site_df_nsrs = site_df.loc[nsrs_start:nsrs_end]
        fig_nsrs = plot_site("RH_NDVI (NSRS window)", site_df_nsrs)
        fig_nsrs.savefig(out_final / "RH_NDVI_all_data_focused_on_NSRS.png",
                         dpi=150, bbox_inches="tight")
        plt.close(fig_nsrs)
        print(f"  → {out_final / 'RH_NDVI_all_data_focused_on_NSRS.png'}")

    # One comparative figure per satellite (NSRS + that satellite)
    sat_lowess_cols = [c for c in site_df.columns
                       if c.startswith(f"{NDVI_LOWESS_FIELD} ")
                       and not any(s in c for s in ("NSRS",))]
    for sat_col in sat_lowess_cols:
        sat_name = sat_col.removeprefix(f"{NDVI_LOWESS_FIELD} ")
        nsrs_cols = [c for c in site_df.columns
                     if f"{NDVI_LOWESS_FIELD} NSRS" in c]
        cols_to_show = nsrs_cols + [sat_col]
        sub_df = site_df[cols_to_show].loc[nsrs_start:nsrs_end] if nsrs_start else site_df[cols_to_show]
        # Phenology for all sources visible in this comparative plot
        visible = {c.removeprefix(f"{NDVI_LOWESS_FIELD} ") for c in sub_df.columns
                   if c.startswith(f"{NDVI_LOWESS_FIELD} ")}
        comp_pheno = pheno_df[pheno_df["satellite"].isin(visible)] if pheno_arg is not None else None
        fig_comp = plot_site(f"RH_NDVI — NSRS vs {sat_name}", sub_df,
                             phenology_df=comp_pheno if (comp_pheno is not None and not comp_pheno.empty) else None)
        out_path = out_comparative / f"RH_NDVI_NSRS_vs_{sat_col}.png"
        fig_comp.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig_comp)
        print(f"  → {out_path.name}")

    # MODIS + NSRS only — publication figure with IMS and phenology dots (figures/final/)
    modis_nsrs_cols = [c for c in site_df.columns
                       if c.startswith(f"{NDVI_LOWESS_FIELD} ")
                       and any(s in c for s in ("MODIS", "NSRS"))]
    if modis_nsrs_cols:
        ims_cols = [c for c in site_df.columns if c in (IMS_RAINFALL_FIELD, IMS_TEMPERATURE_FIELD)]
        keep_cols = modis_nsrs_cols + ims_cols
        sub_modis_nsrs = (site_df[keep_cols].loc[nsrs_start:nsrs_end]
                          if nsrs_start else site_df[keep_cols])
        modis_nsrs_pheno = (pheno_df[pheno_df["satellite"].isin(
            {c.removeprefix(f"{NDVI_LOWESS_FIELD} ") for c in modis_nsrs_cols}
        )] if pheno_arg is not None else None)
        fig_mn = plot_site_publication(
            "RH_NDVI_MODIS_vs_NSRS",
            sub_modis_nsrs,
            phenology_df=modis_nsrs_pheno if (modis_nsrs_pheno is not None and not modis_nsrs_pheno.empty) else None,
            output_dir=out_final,
            phenology_style="points",
        )
        plt.close(fig_mn)
        print(f"  → {out_final / 'RH_NDVI_MODIS_vs_NSRS_timeseries.png'}")

    # Publication-quality figure — no phenology markers on main graph
    pub_fig = plot_site_publication("RH_NDVI", site_df, output_dir=out_final)
    plt.close(pub_fig)
    print(f"  → {out_final / 'RH_NDVI_timeseries.png'}")

    # Data availability chart
    fig_avail = plot_data_availability("RH_NDVI", site_df)
    fig_avail.savefig(out_final / "RH_NDVI_data_availability.png", dpi=150, bbox_inches="tight")
    plt.close(fig_avail)
    print(f"  → {out_final / 'RH_NDVI_data_availability.png'}")

    # ── Step 9: NSRS_3 calibration validation ───────────────────────────────
    print()
    print("=" * 60)
    print("Step 9: NSRS_3 calibration validation")
    print("=" * 60)

    nsrs3_result = _run_calibration(site_df, out_calib, out_dir)

    # ── Step 10: Woody / herbaceous decomposition (all satellites) ──────────
    print()
    print("=" * 60)
    print("Step 10: Woody / herbaceous decomposition")
    print("=" * 60)

    sat_lowess_for_decomp = [
        c for c in site_df.columns
        if c.startswith(f"{NDVI_LOWESS_FIELD} ")
        and not any(s in c for s in ("NSRS",))
    ]

    for sat_col in sat_lowess_for_decomp:
        sat_name = sat_col.removeprefix(f"{NDVI_LOWESS_FIELD} ")
        series = site_df[sat_col].dropna()
        woody, herbaceous = decompose_woody_herbaceous(series, min_dry_seasons=2)

        if woody is None:
            # warning already printed by decompose_woody_herbaceous
            print(f"  [{sat_name}] skipped — insufficient dry seasons")
            continue

        # Save CSV
        decomp_csv = out_dir / f"RH_NDVI_{sat_name}_decomposition.csv"
        pd.DataFrame({"woody": woody, "herbaceous": herbaceous}).to_csv(decomp_csv)
        print(f"  [{sat_name}] → {decomp_csv.name}")

        # Generate 3-panel comparative figure vs NSRS sensors
        fig_decomp = plot_decomposition_comparative(
            "RH_NDVI", site_df, sat_name, woody, herbaceous,
            output_dir=out_decomposition,
        )
        plt.close(fig_decomp)
        print(f"  [{sat_name}] → {sat_name}_decomposition_vs_NSRS.png")

    # ── Step 11: Intra-day (daily graphs) figures ────────────────────────────
    print()
    print("=" * 60)
    print("Step 11: Generating intra-day NSRS daily graph figures")
    print("=" * 60)

    _run_daily_graphs(data_dir, out_daily, dat_dir=dat_dir)

    # ── Step 12: Orientation and pixel-size figures ──────────────────────────
    print()
    print("=" * 60)
    print("Step 12: Orientation and pixel-size figures")
    print("=" * 60)

    plot_pixel_size_comparison(out_dir=out_orientation, stem="pixel_size_comparison")
    print(f"  Saved pixel-size comparison → {out_orientation}")

    try:
        plot_site_location(out_dir=out_orientation, stem="site_location")
        print(f"  Saved site location map    → {out_orientation}")
    except ImportError:
        print("  Skipping site location map (cartopy not installed).")
        print("  Install with: pip install cartopy  or  pip install 'lensky-py-lab[maps]'")

    print()
    print("=" * 60)
    print("All done.")
    print(f"Results are in: {out_dir}")
    print("=" * 60)


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _normalise_ims_columns(raw_ims: pd.DataFrame) -> pd.DataFrame:
    """Rename IMS columns to the standard names expected by plotter / Site.

    * Any column containing 'RAINFALL' (e.g. 'RAINFALL[mm] 121710')
      → averaged across stations → renamed to 'RAINFALL'
    * 'TEMP' stays as 'TEMP'
    * 'DATE' columns are dropped.
    """
    df = raw_ims.copy()

    # Drop DATE columns (may appear from the loader)
    df = df[[c for c in df.columns if not c.startswith("DATE")]]

    # Rainfall: collect all columns containing "RAINFALL", average, rename
    rain_cols = [c for c in df.columns if "RAINFALL" in c.upper()]
    if rain_cols:
        df[IMS_RAINFALL_FIELD] = df[rain_cols].mean(axis=1)
        df = df.drop(columns=rain_cols)

    # Temperature: rename any "TEMP..." column to exactly "TEMP"
    temp_cols = [c for c in df.columns if c.upper().startswith("TEMP") and c != IMS_TEMPERATURE_FIELD]
    for col in temp_cols:
        df.rename(columns={col: IMS_TEMPERATURE_FIELD}, inplace=True)

    return df


def _nsrs_timeframe(site_df: pd.DataFrame):
    """Return (start_ts, end_ts) unix timestamps spanning NSRS data.

    Mirrors `get_nsrs_timeframe` from the original notebook.
    """
    nsrs_cols = [c for c in site_df.columns if "NSRS" in c]
    if not nsrs_cols:
        return None, None
    nsrs_sub = site_df[nsrs_cols].dropna(how="all")
    if nsrs_sub.empty:
        return None, None
    return int(nsrs_sub.index.min()), int(nsrs_sub.index.max())


def _run_calibration(site_df: pd.DataFrame, out_calib: Path, out_dir: Path) -> dict | None:
    """Run NSRS_3 calibration validation and save figure + statistics."""
    nsrs3_raw_col  = f"{NDVI_LOWESS_FIELD} NSRS_3"
    nsrs1_col = f"{NDVI_LOWESS_FIELD} NSRS_1"
    nsrs2_col = f"{NDVI_LOWESS_FIELD} NSRS_2"

    missing = [c for c in (nsrs3_raw_col, nsrs1_col, nsrs2_col) if c not in site_df.columns]
    if missing:
        warnings.warn(f"Calibration skipped — missing columns: {missing}")
        return None

    # NOTE: site_df already has NSRS_3 with ×1.4 applied via general_factor in the
    # processing config. To validate the factor we back out the raw (÷1.4) values.
    nsrs3_corrected = site_df[nsrs3_raw_col].dropna()
    nsrs3_raw       = (nsrs3_corrected / 1.4).rename("NSRS_3_raw")
    nsrs1           = site_df[nsrs1_col].dropna()
    nsrs2           = site_df[nsrs2_col].dropna()
    reference       = (nsrs1.add(nsrs2, fill_value=np.nan) / 2).dropna()

    calib_result = find_optimal_calibration_factor(nsrs3_raw, reference)
    print(f"  Optimal factor: {calib_result['optimal_factor']:.3f}  "
          f"(published: {calib_result['published_factor']})")
    print(f"  RMSE before: {calib_result['rmse_raw']:.4f}  "
          f"after: {calib_result['rmse_corrected']:.4f}")
    print(f"  R² before: {calib_result['r2_raw']:.4f}  "
          f"after: {calib_result['r2_corrected']:.4f}")

    # 4-panel figure
    fig_calib = create_calibration_figure(
        nsrs3_raw=nsrs3_raw,
        nsrs1=nsrs1,
        nsrs2=nsrs2,
        calibration_result=calib_result,
        output_dir=out_calib,
    )
    plt.close(fig_calib)
    print(f"  → {out_calib / 'NSRS3_calibration_validation.png'}")

    # Statistics CSV
    stats_df = save_calibration_statistics(
        calib_result,
        output_path=out_dir / "calibration_statistics.csv",
    )
    print(f"  → calibration_statistics.csv")

    return calib_result


def _merge_processed_for_plot(
    primary_df: pd.DataFrame,
    backup_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge two processed DataFrames for a unified cleaning-pipeline figure.

    Primary timestamps are kept as-is; backup contributes only at timestamps
    not already present in primary. The result is sorted by index so the plotter
    sees a single time series with a natural gap between the two deployment periods.
    """
    extra = backup_df.index.difference(primary_df.index)
    return pd.concat([primary_df, backup_df.loc[extra]]).sort_index()


def _run_daily_graphs(data_dir: Path, out_daily: Path, dat_dir: Optional[Path] = None) -> None:
    """Locate intra-day NSRS data sources and generate all daily-graph figures.

    Tries two sources (both are used if available):
    1. Raw Campbell ``.dat`` files found in *dat_dir* (``--dat-dir``), the
       ``DAT_DIR`` env var, or common locations next to the CSV data.
    2. The pre-extracted seasonal Excel workbook (``daily_graphsxlsx.xlsx``),
       located via ``DAILY_GRAPHS_EXCEL`` env var or common search paths.

    The acquisition window is "from before sunrise till noon" per the
    published research figures.
    """
    import os

    # ── Source 1: raw .dat directory ─────────────────────────────────────────
    # Priority: explicit arg > env var > search next to data_dir
    env_dat_dir = os.environ.get("DAT_DIR")
    if dat_dir is not None:
        resolved_dat_dir = dat_dir
    elif env_dat_dir:
        resolved_dat_dir = Path(env_dat_dir)
    else:
        # Search for a directory that contains .dat files
        candidates = [data_dir, data_dir.parent, data_dir.parent / "raw_dat"]
        resolved_dat_dir = next(
            (d for d in candidates if d.exists() and list(d.glob("*.dat"))),
            None,
        )

    dat_processed = False
    if resolved_dat_dir is not None and resolved_dat_dir.exists():
        dat_files = sorted(resolved_dat_dir.glob("*.dat"))
        if dat_files:
            print(f"  Raw .dat dir: {resolved_dat_dir}  ({len(dat_files)} file(s))")
            dat_processed = True
            try:
                out_dat = out_daily / "from_dat"
                df_dat = load_dat_dir(resolved_dat_dir, recursive=True)
                saved = generate_daily_outputs(df_dat, out_dat, dpi=150, noon_cutoff=True)
                for p in saved:
                    print(f"  → {Path(p).name}")
            except Exception as exc:
                warnings.warn(f"Daily-graphs from .dat files failed: {exc}")
        else:
            warnings.warn(
                f"DAT directory {resolved_dat_dir} contains no .dat files — skipping."
            )

    # ── Source 2: pre-extracted seasonal Excel workbook ──────────────────────
    excel_candidates = [
        data_dir / "daily_graphsxlsx.xlsx",
        data_dir.parent / "daily_graphsxlsx.xlsx",
        data_dir / "daily_graphs" / "daily_graphsxlsx.xlsx",
        data_dir.parent / "daily_graphs" / "daily_graphsxlsx.xlsx",
    ]
    env_excel = os.environ.get("DAILY_GRAPHS_EXCEL")
    if env_excel:
        excel_candidates.insert(0, Path(env_excel))

    excel_path = next((p for p in excel_candidates if p.exists()), None)

    if excel_path is None:
        if not dat_processed:
            warnings.warn(
                "No daily-graph data sources found (no .dat directory, no Excel workbook). "
                "Pass --dat-dir or set DAT_DIR / DAILY_GRAPHS_EXCEL. Skipping Step 11."
            )
        return

    print(f"  Excel workbook source: {excel_path}")
    try:
        out_excel = out_daily / "from_excel"
        saved = generate_daily_graph_outputs(
            excel_path, out_excel, dpi=150, noon_cutoff=True,
        )
        for p in saved:
            print(f"  → {Path(p).name}")
    except Exception as exc:
        warnings.warn(f"Daily-graphs from Excel failed: {exc}")


# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--data-dir",
        default=os.environ.get("RH_DATA_DIR", str(REPO_ROOT / "data" / "raw" / "RH")),
        help="Directory containing the RH_NDVI source CSV files (env: RH_DATA_DIR).",
    )
    p.add_argument(
        "--ims-dir",
        default=os.environ.get("RH_IMS_DIR", str(REPO_ROOT / "data" / "raw" / "IMS")),
        help="Directory containing the IMS station CSV files (env: RH_IMS_DIR).",
    )
    p.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "data" / "results"),
        help="Root directory for all outputs (figures and CSVs).",
    )
    p.add_argument(
        "--dat-dir",
        default=None,
        help=(
            "Directory containing raw Campbell .dat files for intra-day figures. "
            "If omitted, a directory containing .dat files is searched next to --data-dir."
        ),
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(
        data_dir=Path(args.data_dir),
        ims_dir=Path(args.ims_dir),
        out_dir=Path(args.out_dir),
        dat_dir=Path(args.dat_dir) if args.dat_dir else None,
    )
