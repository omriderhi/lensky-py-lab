# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Python package for the **Lensky Lab at Bar-Ilan University** to access and analyze Remote Sensing / GIS time-series data (NDVI vegetation indices). The research involves correlating ground-based NSRS sensors, multiple satellite sources (MODIS, Sentinel-2, Landsat-8), and IMS meteorological data, as published in Derhi (2025) MSc thesis. The prior research prototype lives in [archive/research_base_notebook.ipynb](archive/research_base_notebook.ipynb).

> **Note**: The lab PI's surname is **Lensky** (not Lenski — unrelated to Richard Lenski's E. coli LTEE). The GitHub repo is `github.com/omriderhi/lensky-py-lab` (public).

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
│   ├── cleaner.py        # filter_extreme_values, filter_outliers_sliding_window
│   ├── smoother.py       # add_lowess (statsmodels LOWESS)
│   ├── eligibility.py    # EligibilityRules, evaluate_eligibility — which satellites take part
│   └── processor.py      # process_source — runs the full pipeline
├── clients/
│   ├── ims_client.py     # IMSClient — IMS Envista REST API (api_key auth)
│   └── gee_client.py     # GEEClient — Google Earth Engine (earthengine-api)
├── io/
│   └── csv_loader.py     # load_source_csv, load_ims_csvs, discover_ims_csvs_for_site
├── phenology/
│   └── phenolopy_integration.py  # extract_phenology, decompose_woody_herbaceous
├── sensors/
│   ├── nsrs_calibration.py       # NSRS_3 data-derived calibration, 4-panel figure
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
- `fov_canopy_fraction.py` — share of the NSRS_3 signal coming from the crown (reviewer [18]); defaults are placeholders and the script says so when used
- `_gen_local_notebook.py` — one-off: generates a local copy of the archive notebook

## Data flow

1. **Load** — `DataSource.from_csv()` or `DataSource.from_dataframe()` (GEE output)
2. **Process** — `DataSource.process()` runs: extreme filter → sliding-window outlier filter → LOWESS
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

## Outlier filter

`filter_outliers_sliding_window()` (pipeline/cleaner.py): a point is removed when it deviates from the median of its centred `outlier_window` observations (default 7 in the scripts) by more than `max(outlier_k × 1.4826 × MAD, outlier_min_threshold)` (k = 3, floor 0.02 NDVI; MAD over a 31-observation window). The earlier `average_window` rule (a mean-deviation test against the global mean that kept outliers and dropped ordinary values) was removed; `SourceConfig.from_notebook_dict` raises if it sees `average_window`. The satellite sources use the same filter; S2 has a raised floor (0.08) because 0.02 removed real peaks on sparse series — audited in `docs/features/satellite-data-cleaning-audit-report.md`.

`extract_phenology()` reports an end of season only if the curve falls below the threshold before the record ends; otherwise `EoS_censored` is True and `EoS_date` / `EoS_value` / `EoS_doy` are NaT / NaN.

## Source eligibility and duplicates

- `pipeline/eligibility.py`: a satellite takes part in phenology / decomposition / comparative figures only if it has ≥ 40 valid dates inside the NSRS window and valid data in ≥ 60 % of its months (measured after the extreme filter, before the outlier filter). `run_rh_ndvi.py --eligibility enforce|report`, `--exclude <SOURCE>`; verdicts in `source_eligibility.csv`. Excluded sources stay in the data-availability chart ("(excluded)"). Current RH verdicts: MODIS and S2 pass (S2: 64 dates, coverage 0.89), L8 fails (32 dates, coverage 0.58). Thresholds are judgment calls — see README.
- `SourceConfig.average_same_date` averages rows sharing a timestamp at load (L8: one overpass exported as two adjacent-row scenes). On for L8 in `run_rh_ndvi.py`.
- `SourceConfig.outlier_window_days` / `outlier_direction` select the calendar-window, optionally downward-only outlier filter (`filter_outliers_time_window`). Not used by the research config; the planned satellite default after hand-over. S2 uses a raised `outlier_min_threshold` (0.08) instead. See `docs/features/satellite-data-cleaning-audit-report.md`.

## Phenological markers

Extracted by `extract_phenology()` using a **native scipy/Savitzky-Golay seasonal-amplitude** implementation — no external Phenolopy dependency.

- **SoS** (Start of Season) — onset of herbaceous green-up after autumn rain; colour: `#F0E442` (yellow)
- **PoS** (Peak of Season) — maximum NDVI, typically January–April in Mediterranean; colour: `#D55E00` (vermillion)
- **EoS** (End of Season) — dry-season senescence, typically March–May; colour: `#56B4E9` (sky blue)

Markers are rendered as colored scatter points (▲ SoS, ● PoS, ▼ EoS) on comparative plots (NSRS vs satellite). They are **not** drawn on the main time-series figure.

## NSRS_3 calibration

NSRS_3 has a wide-angle lens that captured sky reflectance due to sensor pole tilt.  
Correction: `corrected_NDVI = raw_NDVI × factor`, where the factor is **derived from the data** — the RMSE-minimising multiplier against the mean of NSRS_1 and NSRS_2 (`calibrate_nsrs3_sources()` in `sensors/nsrs_calibration.py`). It is applied to the NSRS_3 / NSRS_3_B LOWESS columns and registered via `get_active_factor()`. The earlier hardcoded value 1.4 (**not** 0.4) survives only as `NSRS3_PUBLISHED_FACTOR`, for comparison; it is never applied. The manuscript (v12) reports the optimum, 1.36, which the derived 1.364 reproduces.

Validation (n=470 co-observations, sliding-window cleaning): derived factor = 1.384 (earlier code: 1.4; the manuscript's 1.36 predates the cleaning fix). RMSE improves from 0.159 → 0.0405 at the derived factor (0.0409 at ×1.4); R² = 0.899.

Calibration is **optional**: nothing in the package requires it. `run_rh_ndvi.py --nsrs3-factor auto|none|<number>` (default `auto`) derives it, skips it, or applies a fixed value; the validation figure/CSV (step 9) only runs in `auto` mode. Applying twice raises, and each run clears any previous factor. Do not hardcode a factor anywhere; RMSE is computed by the single `metrics.rmse()`. `get_logger_ndvi` (daily graphs) only calibrates sensor 3 if a factor is registered in the same process. `run_rh_ndvi.py` registers it before its daily-graph step; the standalone `run_daily_graphs.py` takes the same `--nsrs3-factor auto|none|<number>` (auto needs `--data-dir`/`RH_DATA_DIR` with the NSRS CSVs) and otherwise leaves sensor 3 uncalibrated.

## Figure outputs

All outputs go to `data/results/` (gitignored — regenerate by running `run_rh_ndvi.py`).

| Figure | Output path | Format |
|---|---|---|
| Calibration validation (4-panel) | `figures/calibration/NSRS3_calibration_validation.png` | PNG |
| Site time-series | `figures/final/<site>_timeseries.png` | PNG |
| Satellite + NSRS + IMS publication (MODIS, S2) | `figures/final/RH_NDVI_<sat>_vs_NSRS_timeseries.png` | PNG |
| Comparative (NSRS vs satellite) | `figures/comparative/<site>_NSRS_vs_<sat>.png` | PNG |
| Data-cleaning pipeline | `figures/data_cleaning/<site>/<source>.png` | PNG |
| Daily intra-day NDVI | `figures/daily_graphs/*.png` | PNG |

## PyPI publishing

```bash
poetry build
poetry publish   # requires: poetry config pypi-token.pypi <token>
```
