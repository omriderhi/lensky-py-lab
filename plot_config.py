"""
Script: plot_config.py
Description: Shared publication-quality figure settings for all plots in this project.
             Import this module in any script that generates figures to ensure
             consistent appearance across thesis and journal submission.
Author: Omri Derhi
Institution: Bar-Ilan University
Date: 2025

Usage:
    from plot_config import COLORS, FIGURE_DPI, apply_publication_style
    apply_publication_style()  # Call once at top of plotting script
"""

import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Output settings
# ---------------------------------------------------------------------------

FIGURE_DPI = 300
FIGURE_FORMATS = ["tiff"]
FIGURE_MIN_WIDTH = 12              # inches — minimum figure width

# ---------------------------------------------------------------------------
# Color palette — distinguishable, colorblind-safe (Wong 2011), print-safe
# ---------------------------------------------------------------------------

COLORS = {
    # Vegetation components
    "woody":             "#5B4A3F",   # Dark brown  (woody biomass)
    "herbaceous":        "#4CAF50",   # Green        (herbaceous layer)

    # Satellite sources
    "modis":             "#1f77b4",   # Blue
    "sentinel2":         "#ff7f0e",   # Orange
    "landsat8":          "#2ca02c",   # Green
    "venus":             "#d62728",   # Red
    "planet":            "#9467bd",   # Purple

    # In-situ sensors
    "nsrs1":             "#8c564b",   # Brown
    "nsrs2":             "#e377c2",   # Pink
    "nsrs3_raw":         "#bcbd22",   # Olive / uncorrected
    "nsrs3_corrected":   "#17becf",   # Teal  / corrected

    # Phenological markers
    "sos":               "#FFA500",   # Orange  — Start of Season
    "pos":               "#FF0000",   # Red     — Peak of Season
    "eos":               "#800080",   # Purple  — End of Season

    # Meteorological
    "rainfall":          "#4169E1",   # Royal blue
    "temperature":       "#DC143C",   # Crimson
}

# Mapping from DataFrame column name patterns to COLORS keys.
# Substring matching is used (see source_color()), so "NSRS_1" also
# matches "NSRS_1_B" — _B variants automatically inherit the base color.
COLUMN_COLOR_MAP = {
    "MODIS":    "modis",
    "S2":       "sentinel2",
    "L8":       "landsat8",
    "VENuS":    "venus",
    "PLANET":   "planet",
    "NSRS_1":   "nsrs1",
    "NSRS_2":   "nsrs2",
    "NSRS_3":   "nsrs3_corrected",
}

# ---------------------------------------------------------------------------
# Font sizes
# ---------------------------------------------------------------------------

FONT_SIZE_TITLE      = 16
FONT_SIZE_LABEL      = 13
FONT_SIZE_TICK       = 11
FONT_SIZE_LEGEND     = 11
FONT_SIZE_ANNOTATION = 10

# ---------------------------------------------------------------------------
# Matplotlib rcParams block
# ---------------------------------------------------------------------------

RC_PARAMS = {
    "figure.dpi":          FIGURE_DPI,
    "savefig.dpi":         FIGURE_DPI,
    "figure.facecolor":    "white",
    "axes.facecolor":      "white",
    "axes.grid":           True,
    "grid.alpha":          0.3,
    "grid.linestyle":      "--",
    "grid.color":          "#cccccc",
    "font.family":         "sans-serif",
    "font.size":           FONT_SIZE_TICK,
    "axes.titlesize":      FONT_SIZE_TITLE,
    "axes.titleweight":    "bold",
    "axes.labelsize":      FONT_SIZE_LABEL,
    "axes.labelweight":    "bold",
    "xtick.labelsize":     FONT_SIZE_TICK,
    "ytick.labelsize":     FONT_SIZE_TICK,
    "legend.fontsize":     FONT_SIZE_LEGEND,
    "legend.framealpha":   0.9,
    "legend.edgecolor":    "#cccccc",
    "lines.linewidth":     1.8,
    "lines.markersize":    5,
    "savefig.bbox":        "tight",
    "savefig.facecolor":   "white",
}


def apply_publication_style() -> None:
    """Apply all RC_PARAMS to matplotlib globally.

    Call once at the top of any plotting script before creating any figures.

    Examples
    --------
    >>> from plot_config import apply_publication_style
    >>> apply_publication_style()
    """
    plt.rcParams.update(RC_PARAMS)


def source_color(source_name: str) -> str:
    """Return the canonical color for a data source name.

    Parameters
    ----------
    source_name : str
        Source identifier (e.g., ``"MODIS"``, ``"NSRS_1"``).

    Returns
    -------
    str
        Hex color string from :data:`COLORS`.

    Examples
    --------
    >>> source_color("MODIS")
    '#1f77b4'
    """
    for key, color_key in COLUMN_COLOR_MAP.items():
        if key in source_name:
            return COLORS[color_key]
    return "#333333"   # fallback dark gray
