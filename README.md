# lensky-py-lab

Python package for the **Lensky Lab at Bar-Ilan University** — accessing and analyzing NDVI vegetation index time series from ground-based sensors and satellite sources, as used in Derhi (2025) MSc thesis.

---

## Study sites

| Site | Location | Sensors |
|---|---|---|
| Ramat Hanadiv (RH) | Mount Carmel foothills, Israel | NSRS_1, NSRS_2, NSRS_3 (calibrated ×1.4) |

## Satellite data sources

| Source | Collection | NDVI computation |
|---|---|---|
| MODIS | `MODIS/061/MOD13Q1` | Direct (`NDVI × 0.0001`) |
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

All scripts read data paths from environment variables. No hardcoded paths exist in the codebase.

| Variable | Required | Description |
|---|---|---|
| `RH_DATA_DIR` | Yes | Directory containing per-source NDVI CSV files (`MODIS.csv`, `NSRS_1.csv`, …) |
| `RH_IMS_DIR` | Yes | Directory containing IMS meteorological CSV files |
| `RH_DAT_DIR` | Optional | Directory with raw Campbell `.dat` logger files (for intra-day NSRS figures) |
| `DAILY_GRAPHS_EXCEL` | Optional | Path to `daily_graphsxlsx.xlsx` (4-sheet intra-day workbook, alternative to `.dat`) |
| `RESEARCH_DATA_ROOT` | Optional | Root of the local research data tree (used by `_gen_local_notebook.py` only) |

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
    average_window=0.05,
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
                             average_window=0.05, images_per_month=2)
modis = DataSource.from_csv("MODIS", "data/raw/RH/MODIS.csv", modis_config)
site.add_satellite(modis)
```

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
from lensky_py_lab.phenology import extract_phenology, decompose_woody_herbaceous

# SoS / PoS / EoS per satellite per hydrological year
phenology_df = extract_phenology(site_df, site_name="RH",
                                  output_csv="data/results/phenology_markers.csv")

# Helman (2015) woody/herbaceous decomposition
woody, herbaceous = decompose_woody_herbaceous(site_df["NDVI lowess MODIS"])
```

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

# Derive and confirm the ×1.4 empirical correction factor
result = find_optimal_calibration_factor(nsrs3_raw, reference)
print(f"Optimal factor: {result['optimal_factor']:.2f}")   # → ~1.40

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
