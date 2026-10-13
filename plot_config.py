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
FIGURE_FORMATS = ["png"]
FIGURE_MIN_WIDTH = 12              # inches — minimum figure width

# ---------------------------------------------------------------------------
# Color palette — Okabe & Ito (2008) / Wong (2011) colorblind-safe palette.
# Distinguishable under deuteranopia, protanopia and tritanopia.  Do not add red/green pairs; use shape or line weight as a
# second channel where two series must share a figure.
# ---------------------------------------------------------------------------

WONG = {
    "black":           "#000000",
    "orange":          "#E69F00",
    "sky_blue":        "#56B4E9",
    "bluish_green":    "#009E73",
    "yellow":          "#F0E442",
    "blue":            "#0072B2",
    "vermillion":      "#D55E00",
    "reddish_purple":  "#CC79A7",
    "gray":            "#999999",   # not part of Wong; neutral companion
}

COLORS = {
    # Vegetation components
    "woody":             WONG["orange"],           # woody biomass
    "herbaceous":        WONG["bluish_green"],     # herbaceous layer

    # Satellite sources
    "modis":             WONG["blue"],
    "sentinel2":         WONG["orange"],
    "landsat8":          WONG["bluish_green"],
    "venus":             WONG["vermillion"],
    "planet":            WONG["reddish_purple"],

    # In-situ sensors
    "nsrs1":             WONG["vermillion"],
    "nsrs2":             WONG["reddish_purple"],
    "nsrs3_raw":         WONG["gray"],             # uncorrected
    "nsrs3_corrected":   WONG["black"],            # corrected

    # Phenological markers (shape also encodes type: ^ SoS, o PoS, v EoS)
    "sos":               WONG["yellow"],           # Start of Season
    "pos":               WONG["vermillion"],       # Peak of Season
    "eos":               WONG["sky_blue"],         # End of Season

    # Meteorological
    "rainfall":          WONG["sky_blue"],
    "temperature":       WONG["gray"],
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
FONT_SIZE_LEGEND     = 14
FONT_SIZE_ANNOTATION = 10
FONT_SIZE_TICK_DATE  = 11
FONT_SIZE_PANEL_LETTER = 16

# ---------------------------------------------------------------------------
# Line and marker styling (reviewer round v12: NSRS lines and phenology
# markers must be clearly visible)
# ---------------------------------------------------------------------------

NSRS_LINESTYLE         = "-"
NSRS_LINEWIDTH         = 2.8
SATELLITE_LINEWIDTH    = 1.8

PHENO_MARKER_SIZE       = 220
PHENO_MARKER_EDGE_WIDTH = 2.0
PHENO_MARKER_EDGE_COLOR = "black"

SAVE_DPI = FIGURE_DPI

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
    '#0072B2'
    """
    for key, color_key in COLUMN_COLOR_MAP.items():
        if key in source_name:
            return COLORS[color_key]
    return "#333333"   # fallback dark gray
