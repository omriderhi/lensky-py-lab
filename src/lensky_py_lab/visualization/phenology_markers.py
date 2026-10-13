"""
Module: phenology_markers.py
Description: Single shared implementation for drawing SoS / PoS / EoS
             phenological markers on NDVI time-series axes. Used by both
             lensky_py_lab.plotting.plotter and
             lensky_py_lab.visualization.figure_generator so the two figure
             pipelines stay visually consistent.
Author: Omri Derhi
Institution: Bar-Ilan University
Date: 2025
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

# ---------------------------------------------------------------------------
# Attempt to load shared plot_config from repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from plot_config import (  # type: ignore[import]
        COLORS,
        PHENO_MARKER_EDGE_COLOR,
        PHENO_MARKER_EDGE_WIDTH,
        PHENO_MARKER_SIZE,
        source_color,
    )
except ImportError:  # pragma: no cover
    COLORS: Dict[str, str] = {"sos": "#F0E442", "pos": "#D55E00", "eos": "#56B4E9"}
    PHENO_MARKER_SIZE = 220
    PHENO_MARKER_EDGE_WIDTH = 2.0
    PHENO_MARKER_EDGE_COLOR = "black"

    def source_color(name: str) -> str:  # type: ignore[misc]
        return "#333333"

# ---------------------------------------------------------------------------
# Phenology marker colour / shape constants (thesis-consistent)
# ---------------------------------------------------------------------------

PHENOLOGY_COLORS: Dict[str, str] = {
    "SoS": COLORS.get("sos", "#F0E442"),   # yellow
    "PoS": COLORS.get("pos", "#D55E00"),   # vermillion
    "EoS": COLORS.get("eos", "#56B4E9"),   # sky blue
}

_PHENO_SHAPES: Dict[str, str] = {"SoS": "^", "PoS": "o", "EoS": "v"}

_DATE_VAL = [
    ("SoS", "SoS_date", "SoS_value"),
    ("PoS", "PoS_date", "PoS_value"),
    ("EoS", "EoS_date", "EoS_value"),
]


def draw_phenology_markers(
    ax: plt.Axes,
    phenology_df: pd.DataFrame,
    source: Optional[str] = None,
    year: Optional[int] = None,
) -> None:
    """Scatter SoS / PoS / EoS points at ``(event_date, event_value)``.

    Marker fill colour encodes the event type (SoS/PoS/EoS); the edge is a
    constant high-contrast colour so markers stand out against any curve.
    One legend entry per marker type actually drawn is added.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes. The x-axis is expected to be in matplotlib date format.
    phenology_df : pd.DataFrame
        Output of :func:`~lensky_py_lab.phenology.phenolopy_integration.extract_phenology`.
        Must contain ``SoS_date``/``SoS_value``, ``PoS_date``/``PoS_value``,
        ``EoS_date``/``EoS_value`` columns.
    source : str, optional
        Filter to a single satellite/source name (matches the ``satellite`` column).
    year : int, optional
        Filter to a single hydrological year.

    Notes
    -----
    Marker colours are thesis-consistent:
    * SoS -> yellow     (#F0E442)
    * PoS -> vermillion (#D55E00)
    * EoS -> sky blue   (#56B4E9)
    """
    df = phenology_df
    if source is not None and "satellite" in df.columns:
        df = df[df["satellite"] == source]
    if year is not None and "year" in df.columns:
        df = df[df["year"] == year]

    xlim = ax.get_xlim()
    drawn_types: set = set()

    for _, row in df.iterrows():
        for marker, col_date, col_val in _DATE_VAL:
            date_raw = row.get(col_date)
            val = row.get(col_val)
            if date_raw is None or pd.isna(date_raw):
                continue
            if val is None or pd.isna(val):
                continue
            date = pd.to_datetime(date_raw)
            if not (xlim[0] <= mdates.date2num(date) <= xlim[1]):
                continue
            ax.scatter(
                date, val,
                color=PHENOLOGY_COLORS[marker],
                marker=_PHENO_SHAPES[marker],
                s=PHENO_MARKER_SIZE, zorder=6,
                edgecolors=PHENO_MARKER_EDGE_COLOR,
                linewidths=PHENO_MARKER_EDGE_WIDTH,
            )
            drawn_types.add(marker)

    for marker in ["SoS", "PoS", "EoS"]:
        if marker in drawn_types:
            ax.scatter([], [], color=PHENOLOGY_COLORS[marker],
                       marker=_PHENO_SHAPES[marker], s=PHENO_MARKER_SIZE,
                       edgecolors=PHENO_MARKER_EDGE_COLOR,
                       linewidths=PHENO_MARKER_EDGE_WIDTH, label=marker)
