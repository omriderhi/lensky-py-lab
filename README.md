# lensky-py-lab

Python package for the **Lensky Lab at Bar-Ilan University** — accessing and analyzing NDVI vegetation index time series from ground-based sensors and satellite sources, as used in Derhi (2025) MSc thesis.

---

## Study sites

| Site | Location | Sensors |
|---|---|---|
| Ramat Hanadiv (RH) | Mount Carmel foothills, Israel | NSRS_1, NSRS_2, NSRS_3 (calibrated, factor derived from data) |

## Satellite data sources

| Source | Collection | NDVI computation |
|---|---|---|
| MODIS | `MODIS/061/MOD09GQ` (daily, 250 m) | `(sur_refl_b02−sur_refl_b01)/(sur_refl_b02+sur_refl_b01)` |
| Sentinel-2 | `COPERNICUS/S2_SR_HARMONIZED` | `(B8−B4)/(B8+B4)` |
| Landsat-8 | `LANDSAT/LC08/C02/T1_L2` | `(SR_B5−SR_B4)/(SR_B5+SR_B4)` |
| VENuS | CSV files | Pre-computed |
| PLANET | CSV files | Pre-computed |

---

## Installation

```bash
# Clone and install in editable mode
git clone https://github.com/omriderhi/lensky-py-lab.git
cd lensky-py-lab
pip install -e .

# Optional: Google Earth Engine support
pip install -e ".[gee]"
```

**Dependencies**: `pandas`, `numpy`, `statsmodels`, `scipy`, `matplotlib`, `requests`

---

## Environment variables

All scripts read data paths from environment variables — no hardcoded local paths exist in `src/` or `scripts/`.

| Variable | Required | Description |
|---|---|---|
| `RH_DATA_DIR` | Yes | Directory containing per-source NDVI CSV files (`MODIS.csv`, `NSRS_1.csv`, …) |
| `RH_IMS_DIR` | Yes | Directory containing IMS meteorological CSV files |
| `RH_DAT_DIR` | Optional | Directory with raw Campbell `.dat` logger files (for intra-day NSRS figures) |
| `DAILY_GRAPHS_EXCEL` | Optional | Path to `daily_graphsxlsx.xlsx` (4-sheet intra-day workbook, alternative to `.dat`) |
| `RESEARCH_DATA_ROOT` | Optional | Root of the local research data tree (used by `_gen_local_notebook.py` only) |
| `GEE_PROJECT` | Optional | Google Earth Engine Cloud project, needed only to re-extract satellite series (`--extract`, `scripts/pull_gee_data.py`) |

**Re-extracting satellite data from Google Earth Engine** (optional; MODIS, S2, L8 only): choose per run which sources to pull again, the rest are read from the local CSVs.
```
python scripts/run_rh_ndvi.py --extract S2,L8 --gee-project <project>     # or: --extract all
python scripts/pull_gee_data.py --sources MODIS --modis-collection 006    # extraction only, no analysis
```
The chosen sources' CSVs in `RH_DATA_DIR` are **overwritten** (they are tracked in git, so `git diff` shows the change) and the extraction is recorded in `gee_extraction_log.json` next to them. Details, default windows and the MODIS collection choice: `docs/features/gee-extraction.md`.

**PyCharm run configuration** — paste into *Environment variables* field:
```
RH_DATA_DIR=/path/to/RH_NDVI;RH_IMS_DIR=/path/to/IMS;RH_DAT_DIR=/path/to/dat_files
```

---

## Quick start

### Load and process ground sensor data

```python
from lensky_py_lab import Site, DataSource, SourceConfig, SatelliteSource

# Configure the processing pipeline for one sensor
config = SourceConfig(
    min_value=0.0,
    max_value=1.0,
    outlier_window=7,
    images_per_month=2,
    general_factor=None,
)

# Load from CSV (two columns: DATE, NDVI RAW)
nsrs1 = DataSource.from_csv("NSRS_1", "data/raw/RH/NSRS_1.csv", config)
nsrs2 = DataSource.from_csv("NSRS_2", "data/raw/RH/NSRS_2.csv", config)

# Assemble a Site
site = Site(
    name="Ramat Hanadiv",
    nsrs_sources={"NSRS_1": nsrs1, "NSRS_2": nsrs2},
)

# Run analysis → timestamp-indexed DataFrame with LOWESS columns
site_df = site.run_analysis()
```

### Add satellite data from CSV

```python
modis_config = SourceConfig(min_value=0.0, max_value=1.0,
                             outlier_window=7, images_per_month=2)
modis = DataSource.from_csv("MODIS", "data/raw/RH/MODIS.csv", modis_config)
site.add_satellite(modis)
```

### Same-date duplicates (per-image exports)

A per-image export can list one date twice, e.g. Landsat when the site lies in the overlap of two
adjacent rows of one path (the RH point: path 174, rows 37 and 38). Set `average_same_date=True` in
`SourceConfig` (`"average_same_date": True` in the script's config dict) to average rows that share a
timestamp when loading. Off by default; the RH L8 source uses it.

### Outlier-filter options for sparse satellite series

`filter_outliers_sliding_window` counts *observations*, which spans very different time intervals for daily
MODIS and for S2/L8. Two ways to adapt it per source (see
`docs/features/satellite-data-cleaning-audit-report.md`):

- raise `outlier_min_threshold` (the NDVI floor of the removal threshold; default 0.02, tuned for daily
  ground sensors) — what `run_rh_ndvi.py` does for S2 (0.08);
- `outlier_window_days=15, outlier_direction="down"` — a calendar window that removes only low outliers
  (cloud and atmosphere lower NDVI). Not used by the research pipeline; planned default after hand-over.

### Which sources take part in the analysis

Satellite sources are checked for data sufficiency before phenology, decomposition and the comparative
figures (`lensky_py_lab.pipeline.eligibility`). The rules look at valid data inside the NSRS observation
window, after the extreme-value filter and before the outlier filter, so the verdict does not depend on
filter settings or on any result:

| Rule | Default |
|---|---|
| `min_valid_dates` — distinct valid observation dates in the window | 40 |
| `min_month_coverage` — fraction of months in the window with at least one valid observation | 0.60 |
| `min_peak_season_dates` — distinct valid dates in each complete peak season (1 Dec – 31 Mar) inside the window | 5 |

All rules must hold. The thresholds are judgment calls set after the RH data had been seen: S2 passes
(64 dates, 0.89 coverage, 8 and 11 dates in the two winters); L8 (re-extracted Collection 2) passes the first two rules (42 dates, 0.77)
but fails the peak-season rule (2 and 3 dates in the two winters, against MODIS 59 and 79): the < 10 % cloud filter leaves almost no winter
scenes, so its curve misses the seasonal peak. The peak-season rule and its threshold were added after those counts were seen. Report the
rules in the Methods, and change them only with a reason.

```python
from lensky_py_lab.pipeline.eligibility import EligibilityRules, evaluate_eligibility
table = evaluate_eligibility(satellite_sources, nsrs_sources, EligibilityRules())
```

`scripts/run_rh_ndvi.py` applies the rules by default (`--eligibility enforce`), writes
`source_eligibility.csv` (measures, verdict, reasons), and leaves failing sources out of the analysis.

It also writes `observations_per_month.csv` (supplementary Table S1): per sensor and calendar month of the NSRS window, the number of distinct dates with a kept observation (after extreme and outlier filters; `NSRS_x` and `NSRS_x_B` count as one sensor), plus a `Total` row and one row per complete Dec–Mar season. Excluded sources keep their column, labelled `(excluded)`.
`--eligibility report` only writes the table; `--exclude L8` leaves a source out regardless of the rules.
Left-out sources are still processed, still get their data-cleaning figure, and **stay in the
data-availability chart**, labelled "(excluded)".

### Query satellite data from Google Earth Engine

```python
from lensky_py_lab.clients.gee_client import GEEClient

client = GEEClient(project="my-gee-project")

# Point geometry matching the research site (lon, lat)
geometry = client.point_geometry(lon=34.946667, lat=32.555806)

# Query a single source — MODIS daily (MOD09GQ), NDVI ≥ 0.35 mask applied
ndvi_df = client.get_ndvi_timeseries(
    geometry, "2018-01-01", "2022-09-01",
    source=SatelliteSource.MODIS,
    ndvi_min=0.35,          # masks non-vegetated pixels (default)
)
modis = DataSource.from_dataframe("MODIS", ndvi_df, modis_config)
site.add_satellite(modis)

# Or query all three sources at once (mirrors the research GEE script)
frames = client.get_ndvi_timeseries_all(
    geometry, "2018-01-01", "2022-09-01",
)
for src, df in frames.items():
    ds = DataSource.from_dataframe(src.value, df, modis_config)
    site.add_satellite(ds)
```

### Extract phenological markers

```python
from lensky_py_lab.phenology import (
    extract_phenology, decompose_woody_herbaceous, helman_annual_table,
)

# SoS / PoS / EoS per satellite per hydrological year
phenology_df = extract_phenology(site_df, site_name="RH",
                                  output_csv="data/results/phenology_markers.csv")

# Helman (2015) woody/herbaceous decomposition, per seasonal year (Sep-Aug):
# woody = Jun-Aug mean (or the Oct-Apr minimum if lower), herbaceous = NDVI - woody
woody, herbaceous = decompose_woody_herbaceous(site_df["NDVI lowess MODIS"])
annual = helman_annual_table(site_df["NDVI lowess MODIS"].dropna())  # NDVI_W, NDVI_H per year
```

The woody series is a step function (one value per seasonal year); a season with no
dry-season data gets NaN, nothing is extrapolated. `method="linear_trend"` reproduces the
earlier repo behaviour (not part of Helman 2015). Details: `docs/features/helman-decomposition-alignment.md`.

### Generate publication figures

```python
from lensky_py_lab.visualization import plot_site_publication, plot_phenology_summary

# Time-series figure with SoS/PoS/EoS markers
fig = plot_site_publication(
    "Ramat Hanadiv", site_df, phenology_df,
    output_dir="data/results/figures/final"
)

# Grouped bar chart of phenological DOY across years
fig2 = plot_phenology_summary(phenology_df,
                               output_dir="data/results/figures/phenology")
```

### NSRS_3 calibration

```python
from lensky_py_lab.sensors.nsrs_calibration import (
    find_optimal_calibration_factor,
    apply_calibration,
    create_calibration_figure,
)

# Derive the empirical NSRS_3 correction factor from the data
result = find_optimal_calibration_factor(nsrs3_raw, reference)
print(f"Optimal factor: {result['optimal_factor']:.2f}")   # → ~1.36

# Apply to raw series
nsrs3_corrected = apply_calibration(nsrs3_raw)

# Generate 4-panel calibration validation figure (saves TIFF + PDF)
fig = create_calibration_figure(nsrs3_raw, nsrs1, nsrs2,
                                 output_dir="data/results/figures/calibration")
```

### IMS meteorological data

```python
from lensky_py_lab.clients.ims_client import IMSClient

ims = IMSClient(api_key="your-envista-api-key")
station = ims.nearest_station(lat=32.60, lon=34.97)
rain_df = ims.get_rainfall(station["stationId"], "2018-01-01", "2022-12-31")
site.set_ims_data(rain_df)
```

---

## Data directory layout

```
data/
├── raw/
│   ├── RH/           # Ground sensor and satellite CSV files for Ramat Hanadiv
│   │   ├── NSRS_1.csv
│   │   ├── NSRS_2.csv
│   │   ├── NSRS_3.csv
│   │   ├── MODIS.csv
│   │   └── ...
│   └── IMS/          # IMS Envista station CSV exports
└── results/
    ├── phenology_markers.csv
    ├── calibration_statistics.csv
    └── figures/
        ├── calibration/   # NSRS3_calibration_validation.tiff/.pdf
        ├── final/         # Per-site publication figures
        ├── phenology/     # phenology_summary_bars.tiff/.pdf
        └── validation/
```

See [`data/raw/README.md`](data/raw/README.md) for the expected CSV column format.

---

## Running tests

```bash
python -m pytest
python -m pytest tests/test_calibration.py -v
python -m pytest tests/test_phenology.py -v
```

Tests use synthetic data — no real data files are required.

---

## Reference

Derhi, O. (2025). *Vegetation phenology and woody/herbaceous decomposition from
multi-source remote sensing at Ramat Hanadiv*. MSc thesis, Bar-Ilan University.
