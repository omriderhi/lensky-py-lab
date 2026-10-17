#!/usr/bin/env python
"""Regenerate RH_NDVI/S2.csv from Google Earth Engine as one product.

Every row comes from COPERNICUS/S2_SR_HARMONIZED with the research script's settings
(CLOUD_COVERAGE_ASSESSMENT < 10, NDVI >= 0.35 mask, mean at scale 10 over the RH point),
so the series does not mix processing versions. See docs/features/s2-extension.md.

Usage:
    python scripts/pull_s2_gee.py --project <gee-project> [--start 2019-01-01] [--end 2021-12-05] [--out path.csv]

Needs ``earthengine authenticate`` once and ``pip install -e .[gee]``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from lensky_py_lab.clients.gee_client import GEEClient
from lensky_py_lab.constants import NDVI_RAW_FIELD, SatelliteSource

REPO_ROOT = Path(__file__).resolve().parents[1]
RH_LON, RH_LAT = 34.946667, 32.555806   # same point as the research GEE script


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", required=True, help="GEE Cloud project ID")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2021-12-05",
                   help="exclusive end; default is one month after the last NSRS date (2021-11-04)")
    p.add_argument("--out", default=str(REPO_ROOT / "data" / "research_results" / "RH_NDVI" / "S2.csv"))
    args = p.parse_args()

    client = GEEClient(project=args.project)
    df = client.get_ndvi_timeseries(
        client.point_geometry(RH_LON, RH_LAT), args.start, args.end, SatelliteSource.SENTINEL2,
    )
    dates = pd.to_datetime(df.index, unit="s")
    out = pd.DataFrame({
        "DATE": [f"{d.strftime('%b')} {d.day}, {d.year}" for d in dates],   # e.g. "Jan 5, 2019"
        "NDVI_RAW": df[NDVI_RAW_FIELD].round(3).values,
    })
    out.to_csv(args.out, index=False)
    print(f"{len(out)} images, {dates.min().date()} .. {dates.max().date()} -> {args.out}")


if __name__ == "__main__":
    main()
