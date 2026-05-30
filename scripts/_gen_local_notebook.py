"""One-off script: generates archive/research_base_notebook_local.ipynb from the original.

Changes applied to the copy:
  Cell 3  — replace Google Colab / Drive mount with local path setup
  Cell 24 — disable image saving, save per-source CSVs, uncomment join + final CSV
  Cell 25 — wrap availability section (site_df is now defined)
  New     — comparison cell: notebook counts vs package counts
"""
import json
import copy
import os
from pathlib import Path

REPO = Path(__file__).parents[1]
SRC  = REPO / "archive" / "research_base_notebook.ipynb"
DST  = REPO / "archive" / "research_base_notebook_local.ipynb"

with SRC.open("r", encoding="utf-8") as f:
    nb = json.load(f)

nb2 = copy.deepcopy(nb)

# ── helpers ──────────────────────────────────────────────────────────────────

def lines(*args):
    """Join lines into a cell source list."""
    return list(args)


# ── Cell 3: local path setup (replaces Google Drive mount) ───────────────────
DATA_ROOT = os.environ.get("RESEARCH_DATA_ROOT")
if not DATA_ROOT:
    raise EnvironmentError(
        "Set the RESEARCH_DATA_ROOT environment variable to the local research data directory."
    )
REPO_ROOT = str(Path(__file__).parents[1])

nb2["cells"][3]["source"] = lines(
    "import os, json\n",
    "from pathlib import Path\n",
    "\n",
    "# Local path setup — replaces Google Colab / Google Drive\n",
    f"BASE_DATA_PATH = Path(r'{DATA_ROOT}')\n",
    "\n",
    "BASE_FOLDER_PATH        = str(BASE_DATA_PATH)\n",
    "SUPPORT_FOLDER_PATH     = str(BASE_DATA_PATH / 'support_files')\n",
    "\n",
    "# Outputs go to the repo's results folder\n",
    f"_REPO_ROOT = Path(r'{REPO_ROOT}')\n",
    "DEFAULT_OUTPUT_FOLDER = str(_REPO_ROOT / 'data' / 'results' / 'notebook_comparison')\n",
    "\n",
    "DEFAULTֹ_IMS_DATA_FOLDER_NAME = 'IMS'\n",
    "DEFAULTֹ_IMS_DATA_FOLDER_PATH = str(BASE_DATA_PATH / 'IMS')\n",
    "\n",
    "# Create output sub-directories\n",
    "for _sub in ['CSVs', 'per_source_CSVs']:\n",
    "    Path(DEFAULT_OUTPUT_FOLDER, _sub).mkdir(parents=True, exist_ok=True)\n",
    "\n",
    'print(f"Input  : {BASE_FOLDER_PATH}")\n',
    'print(f"Output : {DEFAULT_OUTPUT_FOLDER}")\n',
)
nb2["cells"][3]["outputs"] = []
nb2["cells"][3]["execution_count"] = None

# ── Cell 24: main operation — no graphs, add CSVs, fix commented-out lines ───
nb2["cells"][24]["source"] = lines(
    "import os, glob, csv\n",
    "import pandas as pd\n",
    "import matplotlib\n",
    "matplotlib.use('Agg')  # headless — prevents any display window\n",
    "import matplotlib.pyplot as plt\n",
    "from datetime import datetime as dt\n",
    "\n",
    "\n",
    "for site_name, site_configurations in SOURCES_CONFIGURATIONS.items():\n",
    "    sources_data_smoothed = {}\n",
    "    if site_name.startswith('MATA'):\n",
    "        continue\n",
    "\n",
    "    site_data_files = generate_sources_data_file_names_for_site(\n",
    "        site_name,\n",
    "        SOURCES_CONFIGURATIONS\n",
    "    )\n",
    "\n",
    '    print(f"\\n=== {site_name} ===")\n',
    "    for source_results_file in site_data_files:\n",
    "        source_name = os.path.split(source_results_file)[1].replace('.csv', '')\n",
    "        source_configurations = SOURCES_CONFIGURATIONS[site_name][source_name]\n",
    "\n",
    "        raw_df = load_raw_results_csv(source_results_file)\n",
    "        filtered_extremes_data = filter_extremes_in_df(raw_df, source_configurations)\n",
    "        average_filtered_data = filter_by_average_groups_in_df(\n",
    "            filtered_extremes_data,\n",
    "            source_configurations\n",
    "        )\n",
    "\n",
    "        if source_configurations.get('images_per_month'):\n",
    "            loess_factor = source_configurations['images_per_month']\n",
    "            loess_factor_frac = loess_factor / len(average_filtered_data.dropna(axis=0))\n",
    "            loess_df = add_loess_to_df(average_filtered_data, 'NDVI clean', source_configurations)\n",
    "        else:\n",
    "            loess_df = average_filtered_data.copy()\n",
    "            loess_df[NDVI_LOWESS_FIELD_NAME] = loess_df[NDVI_CLEAN_FIELD_NAME]\n",
    "\n",
    '        plt.close("all")  # no graph saving\n',
    "\n",
    "        # Save per-source CSV (all pipeline columns for comparison)\n",
    "        per_src_csv = os.path.join(\n",
    "            DEFAULT_OUTPUT_FOLDER, 'per_source_CSVs', f'{source_name}.csv'\n",
    "        )\n",
    "        loess_df.to_csv(per_src_csv)\n",
    "\n",
    "        # Progress report\n",
    "        n_raw      = loess_df['NDVI RAW'].count()\n",
    "        n_filtered = loess_df['NDVI filtered'].count()\n",
    "        n_clean    = loess_df['NDVI clean'].count()\n",
    "        n_lowess   = loess_df['NDVI lowess'].count() if 'NDVI lowess' in loess_df else 0\n",
    '        print(f"  {source_name:12s}  raw={n_raw:4d}  filtered={n_filtered:4d}  "\n',
    '              f"clean={n_clean:4d}  lowess={n_lowess:4d}")\n',
    "\n",
    "        sources_data_smoothed[source_name] = loess_df\n",
    "\n",
    "    # Join all sources into site_df\n",
    "    site_df = join_site_dataframes(sources_data_smoothed, lowess_only=True)\n",
    "\n",
    "    # Attach IMS data\n",
    "    ims_paths = get_ims_file_paths_for_site(site_name)\n",
    "    if ims_paths:\n",
    "        ims_df = get_site_ims_data(ims_paths).add_suffix(' IMS')\n",
    "        site_df = add_ims_data_to_site_df(site_df, ims_df)\n",
    "\n",
    "    # Save final joined CSV\n",
    "    csv_output_path = os.path.join(\n",
    "        DEFAULT_OUTPUT_FOLDER, 'CSVs', f'{site_name}_final_result.csv'\n",
    "    )\n",
    "    site_df.to_csv(csv_output_path)\n",
    '    print(f"  → saved {csv_output_path}")\n',
    '    print(f"  site_df shape: {site_df.shape}")\n',
)
nb2["cells"][24]["outputs"] = []
nb2["cells"][24]["execution_count"] = None

# ── Cell 25: availability CSV (site_df now defined) ───────────────────────────
nb2["cells"][25]["source"] = lines(
    "# Data availability summary\n",
    "# site_df is defined at the end of the main loop above (last site = RH_NDVI)\n",
    "\n",
    "sources_aviability_codes = {\n",
    "    'NDVI lowess MODIS':    1,\n",
    "    'NDVI lowess S2':       2,\n",
    "    'NDVI lowess L8':       3,\n",
    "    'NDVI lowess NSRS_1':   4,\n",
    "    'NDVI lowess NSRS_2':   5,\n",
    "    'NDVI lowess NSRS_3':   6,\n",
    "    'NDVI lowess NSRS_1_B': 4,\n",
    "    'NDVI lowess NSRS_2_B': 5,\n",
    "    'NDVI lowess NSRS_3_B': 6,\n",
    "}\n",
    "\n",
    "avaiability_site_df   = pd.notnull(site_df)\n",
    "avaiability_site_dict = avaiability_site_df.to_dict()\n",
    "for column_name, column_rows in avaiability_site_dict.items():\n",
    "    for i, available_data in column_rows.items():\n",
    "        if available_data and column_name in sources_aviability_codes:\n",
    "            avaiability_site_dict[column_name][i] = sources_aviability_codes[column_name]\n",
    "\n",
    "coded_avaiability_site_df = pd.DataFrame.from_dict(avaiability_site_dict)\n",
    "coded_avaiability_site_df['DATE'] = [\n",
    "    dt.fromtimestamp(ts) for ts in coded_avaiability_site_df.index\n",
    "]\n",
    "csv_output_path = os.path.join(\n",
    "    DEFAULT_OUTPUT_FOLDER, 'CSVs', 'RH_data_avaiability.csv'\n",
    ")\n",
    "coded_avaiability_site_df.to_csv(csv_output_path)\n",
    'print(f"Availability CSV saved to {csv_output_path}")\n',
)
nb2["cells"][25]["outputs"] = []
nb2["cells"][25]["execution_count"] = None

# ── New cell: comparison vs package output ────────────────────────────────────
comparison_cell = {
    "cell_type": "code",
    "metadata": {},
    "source": lines(
        "# ══════════════════════════════════════════════════════════════════════════\n",
        "# Comparison: notebook cleaning algorithm vs package cleaning algorithm\n",
        "#\n",
        "# Key algorithmic difference discovered during analysis:\n",
        "#\n",
        "#   NOTEBOOK filter_by_average_groups_in_df:\n",
        "#     Bug: loop variable `i` is a unix timestamp (e.g. 1571011200), not a\n",
        "#     row index.  first_in_group = i - i - 3 = -3  → clamped to 1;\n",
        "#     last_in_group = timestamp + 3  → clamped to len(df).\n",
        "#     Effect: test_group is always the ENTIRE filtered series.\n",
        "#     → compares each value to the GLOBAL mean of all filtered data.\n",
        "#     → keeps only values that deviate from the global mean by >= window.\n",
        "#\n",
        "#   PACKAGE filter_by_average_groups:\n",
        "#     Uses integer positional index `pos`.  Window = ±3 rows (7-point).\n",
        "#     → compares each value to its LOCAL neighbourhood mean.\n",
        "#     → for a smooth NDVI time-series, almost every point looks like its\n",
        "#       neighbours → almost all data is dropped as \"too smooth\".\n",
        "#\n",
        "# Expected result: notebook keeps far MORE points than the package,\n",
        "# especially in the 'NDVI clean' column that feeds into LOWESS.\n",
        "# ══════════════════════════════════════════════════════════════════════════\n",
        "\n",
        "from pathlib import Path\n",
        "import pandas as pd\n",
        "\n",
        f"_repo = Path(r'{REPO_ROOT}')\n",
        "_nb_dir  = _repo / 'data' / 'results' / 'notebook_comparison'\n",
        "_pkg_csv = _repo / 'data' / 'results' / 'RH_NDVI_final_result.csv'\n",
        "\n",
        "# Package lowess point counts\n",
        "pkg_counts = {}\n",
        "if _pkg_csv.exists():\n",
        "    _pkg_df = pd.read_csv(_pkg_csv, index_col=0)\n",
        "    for _col in _pkg_df.columns:\n",
        "        if _col.startswith('NDVI lowess '):\n",
        "            _src = _col.replace('NDVI lowess ', '')\n",
        "            pkg_counts[_src] = int(_pkg_df[_col].count())\n",
        "else:\n",
        '    print(f"Package result not found: {_pkg_csv}")\n',
        '    print("Run scripts/run_rh_ndvi.py first to generate the package output.")\n',
        "\n",
        "# Notebook per-source CSV counts\n",
        "_src_dir = _nb_dir / 'per_source_CSVs'\n",
        "rows = []\n",
        "for _csv_path in sorted(_src_dir.glob('*.csv')):\n",
        "    _src = _csv_path.stem\n",
        "    _df  = pd.read_csv(_csv_path, index_col=0)\n",
        "    _row = {\n",
        "        'source':       _src,\n",
        "        'nb_raw':       int(_df['NDVI RAW'].count())      if 'NDVI RAW'      in _df else 0,\n",
        "        'nb_filtered':  int(_df['NDVI filtered'].count()) if 'NDVI filtered' in _df else 0,\n",
        "        'nb_clean':     int(_df['NDVI clean'].count())    if 'NDVI clean'    in _df else 0,\n",
        "        'nb_lowess':    int(_df['NDVI lowess'].count())   if 'NDVI lowess'   in _df else 0,\n",
        "        'pkg_lowess':   pkg_counts.get(_src, 'N/A'),\n",
        "    }\n",
        "    if isinstance(_row['pkg_lowess'], int):\n",
        "        _row['delta_lowess'] = _row['nb_lowess'] - _row['pkg_lowess']\n",
        "    else:\n",
        "        _row['delta_lowess'] = 'N/A'\n",
        "    rows.append(_row)\n",
        "\n",
        "if rows:\n",
        "    _cmp = pd.DataFrame(rows).set_index('source')\n",
        "    print('\\n' + '═'*72)\n",
        "    print('Notebook (global-mean filter) vs Package (local-window filter)')\n",
        "    print('Point counts at each pipeline stage')\n",
        "    print('═'*72)\n",
        "    print(_cmp.to_string())\n",
        "    print()\n",
        "    print('delta_lowess > 0  →  notebook kept MORE lowess points than package')\n",
        "    print('delta_lowess < 0  →  package  kept MORE lowess points than notebook')\n",
        "else:\n",
        "    print('No per_source_CSVs found. Run cell 24 first.')\n",
    ),
    "outputs": [],
    "execution_count": None,
}
nb2["cells"].append(comparison_cell)

# ── Write output notebook ────────────────────────────────────────────────────
with DST.open("w", encoding="utf-8") as f:
    json.dump(nb2, f, ensure_ascii=False, indent=1)

print(f"Written : {DST}")
print(f"Cells   : {len(nb2['cells'])} (original had {len(nb['cells'])})")
