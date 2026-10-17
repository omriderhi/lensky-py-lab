# Re-extracting satellite series from Google Earth Engine

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

## L8 with the NSRS-aligned window: eligibility changes

With the 2019-01-01 .. 2021-12-05 window L8 has 70 dates (97 images, adjacent-row overlaps are averaged on load) and, tested
on a scratch copy of the data, the eligibility rules give **42 valid dates in the NSRS window and month coverage 0.77, so L8
becomes eligible** (before: 32 and 0.58, excluded). It would then take part in phenology, decomposition and the comparative
figures. This contradicts the L8 exclusion in `paper-rewrite-brief.md` and `satellite-data-cleaning-audit-report.md`, which
were based on the old C01-derived export; the L8 filter question (floor 0.10, window) also has to be re-audited on the new
series before L8 is used. Not verified.
