from __future__ import annotations

import glob as _glob
from datetime import datetime
from pathlib import Path
from typing import List, Union

import pandas as pd

from lensky_py_lab.constants import (
    DATE_FIELD,
    DATE_FORMATS,
    IMS_RAIN_CODE_FIELD,
    NDVI_RAW_FIELD,
    TIMESTAMP_FIELD,
)


def load_source_csv(path: Union[str, Path]) -> pd.DataFrame:
    """Load a satellite or NSRS source CSV.

    Expects at minimum a DATE column and an NDVI_RAW (or 'NDVI RAW') column.
    Returns a DataFrame indexed by unix timestamp with DATE and NDVI_RAW_FIELD columns.
    """
    df = pd.read_csv(path)
    df.dropna(axis=0, inplace=True)

    if "NDVI_RAW" in df.columns and NDVI_RAW_FIELD not in df.columns:
        df.rename(columns={"NDVI_RAW": NDVI_RAW_FIELD}, inplace=True)

    dates: list[datetime] = []
    timestamps: list[int] = []
    for date_str in df[DATE_FIELD]:
        dt = _parse_date(str(date_str))
        dates.append(dt)
        timestamps.append(int(datetime.timestamp(dt)))

    df[DATE_FIELD] = dates
    df[TIMESTAMP_FIELD] = timestamps
    df.set_index(TIMESTAMP_FIELD, inplace=True)
    return df


def load_ims_csvs(
    paths: List[Union[str, Path]],
    collect_rain_code: bool = False,
) -> pd.DataFrame:
    """Load and join multiple IMS data files (rainfall + temperature from different stations)."""
    ims_df: pd.DataFrame = pd.DataFrame()

    for path in paths:
        file_stem = Path(path).stem  # e.g., "RH_rainfall_1"
        csv_data = load_source_csv(path)

        station_num = file_stem.split("_")[-1]
        if station_num.isdigit():
            csv_data = csv_data.add_suffix(f" {station_num}")

        if not collect_rain_code:
            cols_to_keep = [
                col
                for col in csv_data.columns
                if not col.startswith(IMS_RAIN_CODE_FIELD)
                and not col.startswith(DATE_FIELD)
            ]
            csv_data = csv_data[cols_to_keep]

        ims_df = ims_df.join(csv_data, how="outer", rsuffix=f"_{file_stem}", sort=True)

    return ims_df


def discover_ims_csvs_for_site(
    site_name: str,
    ims_folder: Union[str, Path],
) -> List[str]:
    """Find IMS CSV paths (rainfall + temperature) for a site by name prefix."""
    real_site_name = site_name.split("_")[0]
    all_files = _glob.glob(str(Path(ims_folder) / "*.csv"))
    return [
        p
        for p in all_files
        if Path(p).stem.split("_")[0] == real_site_name
    ]


def _parse_date(date_str: str) -> datetime:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str!r}")
