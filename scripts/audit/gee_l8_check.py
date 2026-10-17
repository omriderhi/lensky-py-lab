"""List the Landsat-8 / Sentinel-2 images the research JS script would reduce (read-only)."""
import sys
import ee
import pandas as pd

ee.Initialize(project="rh-venus-data")
pt = ee.Geometry.Point([34.946667, 32.555806])
S, E = "2018-01-01", "2022-09-01"


def ndvi_rows(col_id, nir, red, cloud_prop, props):
    col = (ee.ImageCollection(col_id).filterDate(S, E).filterBounds(pt)
           .filter(ee.Filter.lt(cloud_prop, 10)))

    def f(img):
        img = img.select([nir, red]).multiply(0.0000275).add(-0.2)
        nd = img.normalizedDifference([nir, red]).rename("ndvi")
        masked = nd.updateMask(nd.gte(0.35))
        v = masked.reduceRegion(ee.Reducer.mean(), pt, 10).get("ndvi")
        return ee.Feature(None, {"idx": img.get("system:index"), "t": img.get("system:time_start"),
                                 "ndvi": v, **{p: img.get(p) for p in props}})
    return pd.DataFrame([x["properties"] for x in col.map(f).getInfo()["features"]])


for name, args in {
    # C01 (used by the research JS) has been removed from Earth Engine; C02 needs scale factors,
    # which do not change which images/dates are returned. NDVI values are only indicative.
    "L8": ("LANDSAT/LC08/C02/T1_L2", "SR_B5", "SR_B4", "CLOUD_COVER", ["WRS_PATH", "WRS_ROW"]),
    "S2": ("COPERNICUS/S2_SR", "B8", "B4", "CLOUD_COVERAGE_ASSESSMENT", ["MGRS_TILE"]),
}.items():
    try:
        d = ndvi_rows(*args)
    except Exception as e:
        print(name, "ERR", str(e)[:300]); continue
    d["date"] = pd.to_datetime(d.t, unit="ms").dt.date
    d.to_csv(sys.argv[1] + f"/{name}_gee.csv", index=False)
    dup = d[d.duplicated("date", keep=False)].sort_values("date")
    print(name, "images", len(d), "unique dates", d.date.nunique(), "null ndvi", d.ndvi.isna().sum())
    print(dup.head(12).to_string(index=False))
