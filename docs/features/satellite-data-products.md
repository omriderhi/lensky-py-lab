# Data products and extraction methods: register for the paper

One place listing every dataset behind the RH_NDVI analysis, how each was produced, what changed relative to the earlier
export / manuscript, and the numbers from the current run. Use it for Methods, the data-availability statement and the SI.
Companion documents: `s2-extension.md` (S2 decision record), `gee-extraction.md` (extraction tool, measured alignment),
`paper-rewrite-brief.md` (decisions and manuscript sentences), `satellite-data-cleaning-audit-report.md` (filter audit).

Date of the extractions and of the numbers below: 2026-10-17 (Earth Engine collections as served that day).
The files are `data/research_results/RH_NDVI/*.csv`; `gee_extraction_log.json` next to them records each extraction.

## 1. Products

| Product | What it is | Version / collection | Window | Filters applied at extraction | Records | Role in the analysis |
|---|---|---|---|---|---|---|
| NSRS_1, NSRS_2, NSRS_3 (+ `_B` replacements) | Ground NDVI sensors (Campbell loggers) | not from GEE | 2019-10-06 .. 2021-11-03 | none at extraction; cleaning: values >= 0.2, outlier filter window 7 / floor 0.02, LOWESS | 202 / 202 / 202 (+ 389 / 390 / 390 `_B`) raw dates | reference |
| MODIS | Daily 250 m surface-reflectance NDVI, mean over the RH point | `MODIS/006/MOD09GQ` (Collection 6), `(b02-b01)/(b02+b01)` | 2018-01-01 .. 2022-09-01 | NDVI >= 0.35; no pixel-level cloud mask | 1,113 dates with a value | in the analysis |
| S2 | Sentinel-2 L2A 10 m NDVI, mean at the RH point | `COPERNICUS/S2_SR_HARMONIZED`, `(B8-B4)/(B8+B4)` | 2019-01-01 .. 2021-12-05 (last image 2021-11-16) | `CLOUD_COVERAGE_ASSESSMENT < 10` (scene level), NDVI >= 0.35 | 107 images | in the analysis |
| L8 | Landsat-8 30 m NDVI, mean at the RH point | `LANDSAT/LC08/C02/T1_L2` (scale 0.0000275, offset -0.2), `QA_PIXEL` cloud and shadow mask | 2019-01-01 .. 2021-12-05 | `CLOUD_COVER < 10`, NDVI >= 0.35 | 97 images, 70 dates (one overpass appears as two adjacent-row scenes; averaged on load) | **excluded by rule 3** (section 4) |
| IMS rainfall, temperature | Station data | not from GEE | as before | none | unchanged | context in figures |
| VENuS, PLANET | listed in the README | no client support, no RH file | | | | not part of this analysis |

Point: Ramat Hanadiv, 34.946667 E / 32.555806 N (the point of the research GEE script). Reducer: mean at the sensor's native
scale (MODIS 250 m, S2 10 m, L8 30 m). For MODIS, scale 10 m and 250 m give identical values at a point (measured).

## 2. How the satellite series are extracted

- **Tool:** `GEEClient` (`clients/gee_client.py`) and `io/gee_extract.py`, run as `python scripts/pull_gee_data.py --sources ...` or
  `python scripts/run_rh_ndvi.py --extract ...` (details: `gee-extraction.md`). The user chooses per run which of MODIS, S2, L8 to
  extract; the others are read from the local CSVs. An extraction overwrites that source's CSV and logs provenance (collection,
  filters, scale, window, row count, extraction time, code commit, comparison with the replaced file).
- **Defaults:** MODIS collection 006 (reproduces the published file; `--modis-collection 061` is selectable), windows as in the
  table above.
- **Safeguards:** nothing is written unless all chosen sources were fetched and checked; empty or much shorter results and files
  locked by another program are refused.
- **Client fixes made while doing this:** (1) `ee.Initialize(credentials=None)` meant "no credentials", so the stored login was never
  used (now `'persistent'`); (2) the S2 cloud filter is `CLOUD_COVERAGE_ASSESSMENT < 10` as in the research script (it was
  `CLOUDY_PIXEL_PERCENTAGE`; the two are tile-wide and correlate at 0.999, and differ for the cut-off only on two 2018 dates
  outside the S2 record); (3) `get_ndvi_timeseries` takes an optional `collection` override.

## 3. What changed compared with the earlier export and the manuscript

| Product | Change | Evidence | Consequence for the text |
|---|---|---|---|
| MODIS | none (file untouched) | the research script's collection `MODIS/006` still reproduces the file: 1,112 of 1,112 shared dates identical (max difference 0.0005). `MODIS/061` does not: 504 of 1,111 identical, RMSE 0.021, max 0.435 before filtering | name the collection as **MODIS/006 (Collection 6)**; do not describe the data as Collection 6.1. 006 is deprecated and may leave Earth Engine; the exported CSV is the archive |
| S2 | whole series regenerated as one product and extended from 2021-04-30 to 2021-11-16 | the old export mixes processing baselines: 47 of 79 comparable dates differ from today's archive by up to 0.10 (RMSE 0.029), all on baseline 05.00, and every one of them was generated 757-1,506 days after sensing (Nov 2022 - 2023), i.e. reprocessed, whereas every matching baseline 02.xx scene was generated the day it was sensed; the original collection `COPERNICUS/S2_SR` is deprecated, returns 74 instead of 135 images and carries a +1000 offset on baseline 05.00 scenes | name the collection as **S2_SR_HARMONIZED**; every S2 number changes slightly (full set of numbers in section 5) |
| L8 | replaced by a Collection-2 extraction with a QA mask, window aligned to the NSRS record | the original `LANDSAT/LC08/C01/T1_SR` no longer exists; the new series differs from the old on all 49 shared dates (bias -0.03, max 0.058, RMSE 0.034) | L8 cannot be reproduced from the research script; state C02 and that it is excluded |
| NSRS, IMS | none | | |

## 4. L8: why it is excluded

With the new extraction L8 has 42 valid dates and month coverage 0.77 in the NSRS window, so it passes the first two eligibility
rules (>= 40 dates, >= 60 % of months). It fails the third, **peak-season sampling**: at least 5 valid dates in each 1 Dec - 31 Mar
that lies wholly inside the NSRS window. Dates per winter (2019/20, 2020/21): MODIS 59 / 79, S2 8 / 11, L8 2 / 3 (largest gap inside
Dec-Mar: MODIS 9 days, S2 35 / 30, L8 80 / 48). L8 is therefore left out of phenology, Table 3 / Table 4 and the comparative and
decomposition figures (it stays in the data-availability figure, labelled "(excluded)", and its data-cleaning figure is still produced).

Why the rule exists: the < 10 % scene cloud filter leaves very few winter scenes, so the smoothed L8 curve stays between about 0.40 and
0.50 while NSRS reaches 0.73-0.81, and its "peak of season" markers are not seasonal peaks (2020: 0.609 on 2020-04-12; 2021: 0.503 on
2020-11-26). If L8 were included, Table 4 would have n = 24-26 and a herbaceous correlation of 0.40. Its markers also depend on the
filter choice (up to 0.20 in peak value and 36 days between the configured setting, no filter and window 5; see section 5 sensitivity).

State in the Methods that rule 3 and its threshold were set after the counts were seen; the threshold sits between S2 and L8 and is close
to neither, but it is a judgment call like the other two. Do not write that L8 "failed the date or month rules" (it did on the old export;
it does not on the current one).

## 5. Numbers from the current run

Run: `python scripts/run_rh_ndvi.py --data-dir data/research_results/RH_NDVI --ims-dir data/research_results/IMS`
(outputs in `data/results/`, gitignored). Regenerate before quoting.

Observations per source (raw dates -> after extreme and outlier filters): MODIS 1,113 -> 1,056; S2 107 -> 90; L8 70 -> 59.
S2 outlier filter at floor 0.08 removes 1 of 91 observations (see `s2-extension.md`: S2 is effectively unfiltered apart from the
0.4 minimum and LOWESS).

NSRS_3 correction factor, derived from the data: 1.384 (n = 470 co-observations; RMSE 0.159 -> 0.0405; R2 0.899).

Eligibility (NSRS window 2019-10-06 to 2021-11-03):

| Source | valid dates | month coverage | min dates in a Dec-Mar winter | rules | in the analysis |
|---|---|---|---|---|---|
| MODIS | 523 | 1.00 | 59 | pass | yes |
| S2 | 64 | 0.89 | 8 | pass | yes |
| L8 | 42 | 0.77 | 2 | fails rule 3 | no |

Table 4 (Full signal vs NSRS_3, Woody vs NSRS_2, Herbaceous vs NSRS_1):

| Satellite | Component | n | MAE | RMSE | r | bias |
|---|---|---|---|---|---|---|
| MODIS | Full signal | 371 | 0.042 | 0.052 | 0.974 | -0.018 |
| MODIS | Woody | 357 | 0.123 | 0.140 | 0.045 | -0.120 |
| MODIS | Herbaceous | 342 | 0.449 | 0.459 | 0.863 | -0.449 |
| S2 | Full signal | 46 | 0.039 | 0.048 | 0.956 | 0.027 |
| S2 | Woody | 46 | 0.138 | 0.156 | -0.219 | -0.138 |
| S2 | Herbaceous | 44 | 0.385 | 0.390 | 0.917 | -0.385 |

The woody and herbaceous rows compare a satellite-derived component with a differently defined NSRS layer (bias is about minus the
MAE); they are not an accuracy of the decomposition.

Phenology (hydrological year Y = Sep Y-1 to Aug Y; dates carry a 21:00/22:00 time of day from time-zone conversion, so a date may
be one day off the local calendar date):

| Source | Year | SoS | PoS | EoS | PoS value | note |
|---|---|---|---|---|---|---|
| MODIS | 2018 | 2018-01-05 | 2018-02-27 | 2018-04-16 | 0.599 | record starts Jan 2018: SoS is an edge effect |
| MODIS | 2019 | 2018-11-01 | 2019-01-13 | 2019-06-29 | 0.632 | |
| MODIS | 2020 | 2019-10-30 | 2020-03-01 | 2020-07-01 | 0.634 | |
| MODIS | 2021 | 2020-11-05 | 2021-02-20 | 2021-06-01 | 0.655 | |
| MODIS | 2022 | 2021-11-08 | 2022-02-06 | 2022-07-26 | 0.601 | |
| S2 | 2019 | 2018-12-31 | 2018-12-31 | 2019-05-09 | 0.744 | record starts 2019-01-01: SoS and PoS are edge artefacts, do not interpret |
| S2 | 2020 | 2019-11-30 | 2020-03-04 | 2020-05-29 | 0.702 | SoS moved 25 days between S2 product versions: imprecise |
| S2 | 2021 | 2020-10-30 | 2021-02-10 | 2021-05-06 | 0.810 | EoS found because S2 now runs to 2021-11-16 (it was censored when S2 ended 2021-04-30) |

Sensitivity of the satellite outlier filter on the current series (`scripts/audit/satellite_k_window_reaudit.py`, window 5-15 x k 2.5-4 at
each source's configured floor; reference = window 7, k 3): MODIS peak values stay within 0.011; timing markers stay within 4 days for
window >= 11 or k = 4, and move up to 55 days (310 in one case; not examined which marker) for aggressive settings (window 5 at k <= 3,
window 7 at k 2.5). S2 does not depend on k (the 0.08 floor dominates; 1 point removed at windows 5 and 7) but loses up to 0.141 in peak
value and 51 days at window >= 11. L8 (excluded) moves up to 0.20 / 36 days (no filter, window 5), 0.054 / 22 days at floor 0.05, and
351 days at floor 0.02; floor 0.15 and k 2.5 / 4 equal the configured setting.

## 6. Figures produced (all under `data/results/figures/`)

- `final/RH_NDVI_S2_vs_NSRS_timeseries.png`: **new**, S2 + NSRS + IMS rainfall and temperature + phenology markers (same design as the MODIS one).
- `final/RH_NDVI_MODIS_vs_NSRS_timeseries.png`, `final/RH_NDVI_timeseries.png`, `final/RH_NDVI_all_data*.png`: regenerated.
- `final/RH_NDVI_data_availability.png`: shows L8 as "(excluded)".
- `comparative/` (MODIS, S2), `decomposition/` (MODIS, S2), `data_cleaning/RH_NDVI/<source>.png` (all sources, L8 included), `calibration/`, `orientation/`.

## 7. Manuscript statements to update

- **Data / Methods, satellite data:** MODIS = `MODIS/006/MOD09GQ`, NDVI from b02 and b01, mask NDVI >= 0.35, no pixel-level cloud mask;
  S2 = `COPERNICUS/S2_SR_HARMONIZED`, scene cloud filter < 10 %, mask >= 0.35, 2019-01-01 to 2021-11-16 (107 images); L8 = C02 T1_L2 with
  QA_PIXEL mask, acquired and excluded (section 4). All three: mean at the RH point at native scale, accessed 2026-10-17 through Earth Engine.
- **Data availability:** the CSVs and `gee_extraction_log.json` are in the repository; the extraction code is `scripts/pull_gee_data.py`.
  Note that `MODIS/006` and the original `COPERNICUS/S2_SR` are deprecated assets and may disappear from Earth Engine.
- **Eligibility paragraph:** the three rules, thresholds and the three verdicts (section 5); L8 is excluded by the peak-season rule (rule 3) for lack of winter coverage.
- **Table 3 / Table 4 satellite rows, Sections 3.1-3.2:** MODIS and S2 per section 5; S2 values changed (and S2 SoS is imprecise).
- **Fig S4-S6 and the availability-figure caption:** regenerate from the current run; the S2 publication figure is new.
- **Limitations:** S2 is effectively unfiltered at floor 0.08 and its result depends on window = 7 observations; MODIS 006 is deprecated;
  L8 cannot be reproduced from the research script.

## 8. Not verified

- Figures were not diffed against the manuscript (text and tables were: `manuscript-comparison-v13.md`); the `.docx` was not edited.
- The 310-day shift of a MODIS marker at window 5 / k 2.5 was not traced to a specific season or marker.
- The pairing behind the manuscript's per-sensor agreement numbers (Section 3.1) is undocumented.
- Rule 3's threshold (5 dates) is a judgment call made after seeing the RH counts; other sites or periods may need another value.
- MODIS was not re-extracted with the new tool (the existing file is the research export; re-extraction would swap 6 dates in and 1 out).
