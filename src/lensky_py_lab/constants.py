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
