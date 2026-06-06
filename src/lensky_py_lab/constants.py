from __future__ import annotations
from enum import Enum

DATE_FIELD = "DATE"
TIMESTAMP_FIELD = "TS"
NDVI_RAW_FIELD = "NDVI RAW"
NDVI_FILTERED_FIELD = "NDVI filtered"
NDVI_CLEAN_FIELD = "NDVI clean"
NDVI_LOWESS_FIELD = "NDVI lowess"

IMS_RAINFALL_FIELD = "RAINFALL"
IMS_TEMPERATURE_FIELD = "TEMP"
IMS_RAIN_CODE_FIELD = "RAIN_CODE"

AVERAGE_GROUP_SIZE = 7
DATE_FORMATS = ("%b %d, %Y", "%d/%m/%Y")


class SatelliteSource(str, Enum):
    MODIS = "MODIS"
    SENTINEL2 = "S2"
    LANDSAT8 = "L8"
    VENUS = "VENuS"
    PLANET = "PLANET"


# Native ground-sampling distance [metres] for each satellite used in the research.
# Source: MOD09GQ (250 m), Landsat-8 OLI (30 m), Sentinel-2 MSI (10 m).
# GEEClient._DEFAULT_SCALE and orientation_map both import from here.
SATELLITE_NATIVE_RESOLUTION_M: "dict[SatelliteSource, int]" = {
    SatelliteSource.MODIS:     250,
    SatelliteSource.SENTINEL2:  10,
    SatelliteSource.LANDSAT8:   30,
}
