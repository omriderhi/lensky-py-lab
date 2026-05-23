from __future__ import annotations

from datetime import date, datetime
from math import asin, cos, radians, sin, sqrt
from typing import List, Union

import pandas as pd
import requests

from lensky_py_lab.constants import IMS_RAINFALL_FIELD, IMS_TEMPERATURE_FIELD, TIMESTAMP_FIELD


class IMSClient:
    """Client for the Israeli Meteorological Service (IMS) Envista API.

    Args:
        api_key: IMS API key obtained from https://ims.gov.il/

    Example::

        client = IMSClient(api_key="your-key")
        station = client.nearest_station(lat=31.77, lon=35.22)
        df = client.get_site_data(station["stationId"], start="2020-01-01", end="2023-12-31")
    """

    BASE_URL = "https://api.ims.gov.il/v1/envista"

    def __init__(self, api_key: str) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"ApiToken {api_key}",
            "Accept": "application/json",
        })

    def list_stations(self) -> List[dict]:
        """Return all available IMS weather stations."""
        resp = self._session.get(f"{self.BASE_URL}/stations/")
        resp.raise_for_status()
        return resp.json().get("data", [])

    def nearest_station(self, lat: float, lon: float) -> dict:
        """Return the station geographically closest to the given coordinates."""
        stations = self.list_stations()
        return min(
            stations,
            key=lambda s: _haversine(
                lat, lon,
                s["location"]["latitude"],
                s["location"]["longitude"],
            ),
        )

    def get_daily_data(
        self,
        station_id: int,
        start: Union[date, str],
        end: Union[date, str],
    ) -> List[dict]:
        """Fetch raw daily channel records for a station over a date range."""
        url = (
            f"{self.BASE_URL}/stations/{station_id}/data/daily"
            f"/{_fmt_date(start)}/{_fmt_date(end)}"
        )
        resp = self._session.get(url)
        resp.raise_for_status()
        return resp.json().get("data", [])

    def get_rainfall(
        self,
        station_id: int,
        start: Union[date, str],
        end: Union[date, str],
    ) -> pd.DataFrame:
        """Return daily rainfall [mm] as a TS-indexed DataFrame."""
        return self._extract_channel(
            station_id, start, end, alias_prefix="Rain", col_name=IMS_RAINFALL_FIELD,
        )

    def get_temperature(
        self,
        station_id: int,
        start: Union[date, str],
        end: Union[date, str],
    ) -> pd.DataFrame:
        """Return daily mean temperature [°C] as a TS-indexed DataFrame."""
        return self._extract_channel(
            station_id, start, end, alias_prefix="TD", col_name=IMS_TEMPERATURE_FIELD,
        )

    def get_site_data(
        self,
        station_id: int,
        start: Union[date, str],
        end: Union[date, str],
    ) -> pd.DataFrame:
        """Return rainfall and temperature joined into a single TS-indexed DataFrame."""
        rain = self.get_rainfall(station_id, start, end)
        temp = self.get_temperature(station_id, start, end)
        return rain.join(temp, how="outer", sort=True)

    def _extract_channel(
        self,
        station_id: int,
        start: Union[date, str],
        end: Union[date, str],
        alias_prefix: str,
        col_name: str,
    ) -> pd.DataFrame:
        records = self.get_daily_data(station_id, start, end)
        rows = []
        for record in records:
            dt = datetime.strptime(record["datetime"], "%Y/%m/%d")
            ts = int(datetime.timestamp(dt))
            for ch in record.get("channels", []):
                if ch.get("alias", "").startswith(alias_prefix) and ch.get("valid", False):
                    rows.append({TIMESTAMP_FIELD: ts, col_name: ch["value"]})
                    break

        if not rows:
            return pd.DataFrame(columns=[col_name])

        df = pd.DataFrame(rows)
        df.set_index(TIMESTAMP_FIELD, inplace=True)
        return df


def _fmt_date(d: Union[date, str]) -> str:
    if isinstance(d, str):
        return d
    return d.strftime("%Y/%m/%d")


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))
