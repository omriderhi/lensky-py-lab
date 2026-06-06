# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Python package for the **Lensky Lab at Bar-Ilan University** to access and analyze Remote Sensing / GIS time-series data (NDVI vegetation indices). The research involves correlating ground-based NSRS sensors, multiple satellite sources (MODIS, Sentinel-2, Landsat-8), and IMS meteorological data, as published in Derhi (2025) MSc thesis. The prior research prototype lives in [archive/research_base_notebook.ipynb](archive/research_base_notebook.ipynb).

> **Note**: The lab PI's surname is **Lensky** (not Lenski — unrelated to Richard Lenski's E. coli LTEE). The GitHub repo is still named `lenski-py-lab`; rename to `lensky-py-lab` is pending.

## Commands

```bash
# Install core dependencies
pip install -e .
# or with Poetry
poetry install

# Install with Google Earth Engine support
poetry install --extras gee

# Run all tests
python -m pytest

# Run a single test file
python -m pytest tests/test_calibration.py -v

# Run the full pipeline
python scripts/run_rh_ndvi.py

# Run daily intra-day graphs only
python scripts/run_daily_graphs.py --dat-dir path/to/dat_files
```

No lint, format, or typecheck tooling is configured.

## Environment variables

All data paths are configured via environment variables — no hardcoded local paths exist in the codebase. See README.md → "Environment variables" for the full table and PyCharm run-config paste line.

| Variable | Purpose |
|---|---|
| `RH_DATA_DIR` | Directory with per-source NDVI CSV files |
| `RH_IMS_DIR` | Directory with IMS meteorological CSV files |
| `RH_DAT_DIR` | Directory with raw Campbell `.dat` files (optional) |
| `DAILY_GRAPHS_EXCEL` | Path to `daily_graphsxlsx.xlsx` (optional) |
| `RESEARCH_DATA_ROOT` | Root of local research data tree (`_gen_local_notebook.py` only) |

## Architecture

The package lives in `src/lensky_py_lab/`. The main entry point is `Site`.

```
src/lensky_py_lab/
├── __init__.py           # Exports: Site, DataSource, SourceConfig, SatelliteSource
├── configs.py            # SourceConfig dataclass
├── constants.py          # Field names (TS, NDVI RAW, …), SatelliteSource enum
├── models/
│   ├── site.py           # Site — main analysis object
│   └── source.py         # DataSource — one satellite or NSRS sensor
├── pipeline/
│   ├── cleaner.py        # filter_extreme_values, filter_by_average_groups
│   ├── smoother.py       # add_lowess (statsmodels LOWESS)
│   └── processor.py      # process_source — runs the full pipeline
├── clients/
│   ├── ims_client.py     # IMSClient — IMS Envista REST API (api_key auth)
│   └── gee_client.py     # GEEClient — Google Earth Engine (earthengine-api)
├── io/
│   └── csv_loader.py     # load_source_csv, load_ims_csvs, discover_ims_csvs_for_site
├── phenology/
│   └── phenolopy_integration.py  # extract_phenology, decompose_woody_herbaceous
├── sensors/
│   ├── nsrs_calibration.py       # NSRS_3 ×1.4 calibration, 4-panel figure
│   └── daily_graphs.py           # load_dat_dir/file, intra-day NDVI figures
├── plotting/
│   └── plotter.py        # plot_cleaning_pipeline, plot_site, plot_data_availability
└── visualization/
    └── figure_generator.py  # save_figure, plot_site_publication, add_phenology_markers
```

`plot_config.py` (repo root) — shared publication style: 300 DPI, TIFF+PDF, colorblind-safe palette.

Scripts in `scripts/`:
- `run_rh_ndvi.py` — full RH_NDVI pipeline (steps 1–11)
- `example_rh_ndvi.py` — minimal end-to-end example
- `run_daily_graphs.py` — standalone intra-day NSRS figures from `.dat` files
- `_gen_local_notebook.py` — one-off: generates a local copy of the archive notebook

## Data flow

1. **Load** — `DataSource.from_csv()` or `DataSource.from_dataframe()` (GEE output)
2. **Process** — `DataSource.process()` runs: extreme filter → average-group filter → LOWESS
3. **Assemble** — `Site(nsrs_sources={…}, satellite_sources={…}, ims_data=df)`
4. **Analyse** — `site.run_analysis()` → joins all LOWESS columns into a single timestamp-indexed DataFrame
5. **Phenology** — `extract_phenology(site_df)` → SoS / PoS / EoS per satellite per year
6. **Figures** — `plot_site_publication(...)` / `create_calibration_figure(...)` → 300 DPI TIFF + PDF

## Key conventions

- All DataFrames are indexed by **unix timestamp** (integer seconds, field name `TS`).
- Column names follow the pattern `"NDVI lowess <source_name>"` after processing.
- NSRS sensor variants (e.g., `NSRS_1` / `NSRS_1_B`) are automatically merged by forward-fill inside `Site.run_analysis()`.
- `SourceConfig` uses `None` for "no threshold / skip this step" (the notebook used `False` — `SourceConfig.from_notebook_dict()` converts that).
- GEE support is an optional extra (`pip install lensky-py-lab[gee]`); `earthengine-api` is not imported at module load time.
- Hydrological year Y = Sep (Y-1) through Aug Y, matching Mediterranean growing season.

## Phenological markers

Extracted by `extract_phenology()` using a **native scipy/Savitzky-Golay seasonal-amplitude** implementation — no external Phenolopy dependency.

- **SoS** (Start of Season) — onset of herbaceous green-up after autumn rain; colour: `#FFA500`
- **PoS** (Peak of Season) — maximum NDVI, typically January–April in Mediterranean; colour: `#FF0000`
- **EoS** (End of Season) — dry-season senescence, typically March–May; colour: `#800080`

Markers are rendered as vertical dashed lines on comparative plots (NSRS vs satellite). They are **not** drawn on the main time-series figure.

## NSRS_3 calibration

NSRS_3 has a wide-angle lens that captured sky reflectance due to sensor pole tilt.  
Correction: `corrected_NDVI = raw_NDVI × 1.4` (Derhi, 2025 — **not** 0.4).  
`NSRS3_PUBLISHED_FACTOR = 1.4` in `sensors/nsrs_calibration.py`.

Validation (n=296 co-observations): optimal factor = 1.36, confirming the published 1.4 is near-optimal. RMSE improves from 0.149 → 0.030 after correction.

## Figure outputs

All outputs go to `data/results/` (gitignored — regenerate by running `run_rh_ndvi.py`).

| Figure | Output path | Format |
|---|---|---|
| Calibration validation (4-panel) | `figures/calibration/NSRS3_calibration_validation.png` | PNG |
| Site time-series | `figures/final/<site>_timeseries.png` | PNG |
| Comparative (NSRS vs satellite) | `figures/comparative/<site>_NSRS_vs_<sat>.png` | PNG |
| Data-cleaning pipeline | `figures/data_cleaning/<site>/<source>.png` | PNG |
| Daily intra-day NDVI | `figures/daily_graphs/*.png` | PNG |

## PyPI publishing

```bash
poetry build
poetry publish   # requires: poetry config pypi-token.pypi <token>
```
