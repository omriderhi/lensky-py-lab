#!/usr/bin/env python
"""Re-extract research satellite series (MODIS, S2, L8) from Google Earth Engine.

Overwrites <data-dir>/<SOURCE>.csv for the chosen sources only and records provenance in
<data-dir>/gee_extraction_log.json (see lensky_py_lab.io.gee_extract). The same extraction
runs inside the pipeline with ``run_rh_ndvi.py --extract ...``.

Usage:
    python scripts/pull_gee_data.py --sources S2
    python scripts/pull_gee_data.py --sources MODIS,L8 --modis-collection 061
    python scripts/pull_gee_data.py --sources all --data-dir path/to/RH_NDVI

Needs ``earthengine authenticate`` once, ``pip install -e .[gee]`` and a GEE project
(``--project`` or the GEE_PROJECT environment variable).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from lensky_py_lab.clients.gee_client import GEEClient
from lensky_py_lab.io.gee_extract import MODIS_COLLECTIONS, extract_sources, parse_sources

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sources", required=True, help="comma list of MODIS,S2,L8 or 'all'")
    p.add_argument("--project", default=os.environ.get("GEE_PROJECT"), help="GEE Cloud project (env: GEE_PROJECT)")
    p.add_argument("--data-dir", default=os.environ.get("RH_DATA_DIR", str(REPO_ROOT / "data" / "research_results" / "RH_NDVI")),
                   help="folder whose CSVs are overwritten (env: RH_DATA_DIR)")
    p.add_argument("--modis-collection", default="006", choices=list(MODIS_COLLECTIONS),
                   help="006 reproduces the published MODIS.csv; 061 is the current reprocessing")
    p.add_argument("--force", action="store_true", help="overwrite even if the new series is much shorter")
    args = p.parse_args()
    names = parse_sources(args.sources)
    if not args.project:
        p.error("a GEE project is required (--project or GEE_PROJECT)")
    summaries = extract_sources(names, args.data_dir, GEEClient(project=args.project),
                                modis_collection=args.modis_collection, force=args.force)
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
