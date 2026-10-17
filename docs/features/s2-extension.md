# Sentinel-2 series: verification against the original GEE script and extension to Nov 2021

## What was checked

The original research script (GEE JS, point 34.946667 E / 32.555806 N) was compared with
`GEEClient` and with the exported `S2.csv` (92 rows, 2019-01-01 to 2021-04-30).

| Item | Original JS | `GEEClient` |
|---|---|---|
| Collection | `COPERNICUS/S2_SR` (now deprecated) | `COPERNICUS/S2_SR_HARMONIZED` |
| Cloud filter | `CLOUD_COVERAGE_ASSESSMENT < 10` | same (was `CLOUDY_PIXEL_PERCENTAGE`) |
| NDVI | `(B8-B4)/(B8+B4)`, mask `>= 0.35` | same |
| Reducer | mean at scale 10 over the point | same (`bestEffort=True`) |

Run on the harmonised collection, the JS logic and `GEEClient` return identical series
(135 images, 2018-01-16 to 2021-11-16, max difference 0.0).

`CLOUD_COVERAGE_ASSESSMENT` (L1C tile metadata) and `CLOUDY_PIXEL_PERCENTAGE` (L2A) are tile-wide
properties correlated at 0.999 here; they select different images only on 2018-03-12 and 2018-03-17,
before the S2 record starts. The change reproduces the script; it is not a correctness fix.

## Existing `S2.csv` vs what GEE serves today

79 non-null CSV dates are comparable; all exist in the harmonised pull. 32 match exactly (to 3
decimals). The other 47 differ by up to 0.10 (RMSE 0.029, mean +0.005, r = 0.976). Every
mismatch is processing baseline 05.00 (all baseline 02.xx dates match). The likely cause is ESA
reprocessing of the archive after the CSV was exported; not verified.

The deprecated `S2_SR` now returns 74 images instead of 135 and carries the +1000 reflectance
offset on baseline 05.00 scenes (NDVI about 0.41 where harmonised gives about 0.69), so it
cannot be used to continue the series.

## Extension

`S2.csv` = the original 92 rows unchanged + 27 harmonised-collection images from 2021-05-05 to
2021-11-16 (window end 2021-12-05, one month after the last NSRS date, 2021-11-04). The new rows
are baseline 05.00, so there is a small product-version seam at 2021-04-30 (unbiased, see above).
The unextended file is recoverable from git history (`data/research_results/RH_NDVI/S2.csv` at `ef914c2`).

To regenerate the new rows:

```python
from lensky_py_lab.clients.gee_client import GEEClient
from lensky_py_lab.constants import SatelliteSource
c = GEEClient(project="rh-venus-data")
df = c.get_ndvi_timeseries(c.point_geometry(34.946667, 32.555806),
                           "2019-01-01", "2021-12-05", SatelliteSource.SENTINEL2)
```

Effect on the analysis (current cleaning, floor 0.08): S2 is eligible (61 valid dates in the
NSRS window, month coverage 0.85) and the 2021 season now has an end of season (2021-05-12)
instead of being censored.

MODIS and L8 were not re-checked: the JS uses scale 10 for all sources and `MODIS/006`,
`LANDSAT/LC08/C01`, while the client uses `MODIS/061` and Landsat C02.
