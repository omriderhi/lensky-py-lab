# Re-extracting satellite series from Google Earth Engine

Paper-facing summary of all products and numbers: `satellite-data-products.md`.

Choose per run which satellite series to pull again; every other source is read from the local CSVs.

```
python scripts/run_rh_ndvi.py --extract S2,L8 --gee-project <project>      # extraction, then the full pipeline
python scripts/pull_gee_data.py --sources all --project <project>          # extraction only
```

`--extract` takes `MODIS`, `S2`, `L8`, a comma list, `all`, or `none` (default). The chosen sources' CSVs in the data
directory are overwritten (they are tracked in git: `git diff` shows exactly what changed) and each extraction is
recorded in `<data-dir>/gee_extraction_log.json` (collection, window, point, row count, extraction time, code commit,
and a date-by-date comparison with the file it replaced).

Safeguards: all chosen sources are fetched and checked before any file is written; an empty result, or one with fewer
than half the dates of the existing file, is refused unless `--force-extract`; a file held open by another program
(e.g. Excel) stops the run before anything is written. Only MODIS, S2 and L8 come from GEE: NSRS comes from the loggers,
VENuS and PLANET have no client support.

## Defaults per source

| Source | GEE collection | Window (end exclusive) | Filters |
|---|---|---|---|
| MODIS | `MODIS/006/MOD09GQ` (default) or `MODIS/061/MOD09GQ` (`--modis-collection 061`) | 2018-01-01 .. 2022-09-01 (research script) | NDVI >= 0.35 |
| S2 | `COPERNICUS/S2_SR_HARMONIZED` | 2019-01-01 .. 2021-12-05 | `CLOUD_COVERAGE_ASSESSMENT < 10`, NDVI >= 0.35 |
| L8 | `LANDSAT/LC08/C02/T1_L2` (scale/offset, QA_PIXEL cloud and shadow mask) | 2019-01-01 .. 2021-12-05 | `CLOUD_COVER < 10`, NDVI >= 0.35 |

S2 and L8 windows end one month after the last NSRS date (2021-11-04), aligned to the NSRS record. Point: Ramat Hanadiv,
34.946667 E / 32.555806 N. Edit `EXTRACTION_SPECS` in `io/gee_extract.py` to change a window.

## Alignment with the original research script (measured)

The research JS used `MODIS/006`, `COPERNICUS/S2_SR` and `LANDSAT/LC08/C01/T1_SR`, all at scale 10.

- **MODIS 006 reproduces the published `MODIS.csv`**: 1,112 of 1,112 shared dates identical (max difference 0.0005,
  RMSE 0.0003). Scale 10 m vs 250 m gives identical values at the point. The comparison also found 6 dates that GEE
  has and the file lacks, and 1 date the file has and GEE lacks.
- **MODIS 061 does not**: only 504 of 1,111 shared dates are identical; RMSE 0.021, maximum difference 0.435 (before any
  filtering), mean bias -0.0015. Using 061 would change MODIS Table 3/4 and phenology and they would need regenerating.
  006 is the default so the published MODIS numbers stay valid; it is a deprecated asset and may disappear from GEE.
- **S2** (harmonised): identical to the current `S2.csv` (it was produced this way), see `s2-extension.md`.
- **L8 cannot be reproduced**: `LANDSAT/LC08/C01/T1_SR` no longer exists. The client's C02 series (with the QA mask the
  script lacked) differs on all 49 dates shared with the existing file (bias -0.03, max 0.058, RMSE 0.034).

## L8 with the NSRS-aligned window: applied (2026-10-17)

`L8.csv` was re-extracted with the 2019-01-01 .. 2021-12-05 window: 70 dates (97 images; adjacent-row overlaps are averaged
on load). `gee_extraction_log.json` holds the comparison with the replaced file. Effect on the analysis:

- **Rules 1-2 (dates, months) now pass:** 42 valid dates in the NSRS window and month coverage 0.77 (before 32 and 0.58).
- **But the L8 curve misses the winter peaks.** Few scenes pass the < 10 % cloud filter in winter, so the smoothed L8 curve
  stays between about 0.40 and 0.50 while NSRS reaches 0.73-0.81. Phenology if L8 were included: PoS 2020 = 0.609 on 2020-04-12
  (NSRS peaks in Feb-Mar); PoS 2021 = 0.503 on 2020-11-26, which is not the seasonal peak. Table 4, L8 (n = 24-26): full signal
  MAE 0.023, r 0.87; woody r -0.32; herbaceous r 0.40. Rules 1-2 count dates and months, not whether the peak season is sampled.
- **Rule 3 (peak-season sampling) added to the eligibility rules:** at least 5 valid dates in each 1 Dec - 31 Mar that lies wholly
  inside the NSRS window. Dates per winter (2019/20, 2020/21): MODIS 59 / 79, S2 8 / 11, L8 2 / 3. L8 fails it, so **L8 is excluded
  by rule**, not by hand (`pipeline/eligibility.py`; it stays in the data-availability figure, labelled "(excluded)", and in its
  data-cleaning figure). The threshold lies between S2 and L8 and close to neither, but it was chosen after the counts were seen:
  state that in the Methods. The largest gap inside Dec-Mar tells the same story (MODIS 9 days, S2 35 / 30, L8 80 / 48).
- **L8 filter re-audit on the new series** (`scripts/audit/satellite_k_window_reaudit.py`): L8 phenology depends on the filter
  choice, up to 0.20 in peak value and 36 days between the configured setting (window 7, k 3, floor 0.10), no filter and window 5;
  floor 0.02 shifts markers by up to 351 days (a season flips) and floor 0.05 by 0.054 / 22 days; floor 0.15, k 2.5 / 4 and the
  configured setting are identical; windows 11-15 move the peak by 0.054. This instability is consistent with excluding L8.
  Everything for the paper: `satellite-data-products.md`.
