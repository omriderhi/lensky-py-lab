"""
Module: figure_generator.py
Description: Publication-quality figure utilities for the Lensky Lab thesis.
             Provides helpers for saving figures, adding phenological markers,
             and generating the main site time-series and phenology summary figures.
Author: Omri Derhi
Institution: Bar-Ilan University
Date: 2025

Usage:
    from lensky_py_lab.visualization.figure_generator import (
        save_figure,
        add_phenology_markers,
        plot_site_publication,
    )
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Union

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
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
        FIGURE_DPI,
        FIGURE_FORMATS,
        apply_publication_style,
        source_color,
    )

    apply_publication_style()
    _HAS_PLOT_CONFIG = True
except ImportError:  # pragma: no cover
    _HAS_PLOT_CONFIG = False
    FIGURE_DPI = 300
    FIGURE_FORMATS = ["tiff"]
    COLORS: Dict[str, str] = {
        "modis":           "#1f77b4",
        "sentinel2":       "#ff7f0e",
        "landsat8":        "#2ca02c",
        "venus":           "#d62728",
        "planet":          "#9467bd",
        "nsrs1":           "#8c564b",
        "nsrs2":           "#e377c2",
        "nsrs3_raw":       "#bcbd22",
        "nsrs3_corrected": "#17becf",
        "woody":           "#5B4A3F",
        "herbaceous":      "#4CAF50",
        "sos":             "#FF7F00",
        "pos":             "#E41A1C",
        "eos":             "#984EA3",
        "rainfall":        "#4169E1",
        "temperature":     "#DC143C",
    }

    def source_color(name: str) -> str:  # type: ignore[misc]
        """Fallback when plot_config is unavailable."""
        return "#333333"

from lensky_py_lab.gap_utils import WIDE_GAP_SECONDS, dense_interpolate_with_gaps  # noqa: E402

# ---------------------------------------------------------------------------
# Phenology marker colour constants (thesis-consistent)
# ---------------------------------------------------------------------------

PHENOLOGY_COLORS: Dict[str, str] = {
    "SoS": COLORS.get("sos", "#FF7F00"),   # orange
    "PoS": COLORS.get("pos", "#E41A1C"),   # red
    "EoS": COLORS.get("eos", "#984EA3"),   # purple
}

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def save_figure(
    fig: plt.Figure,
    output_dir: Union[str, Path],
    stem: str,
    formats: Optional[List[str]] = None,
    dpi: int = FIGURE_DPI,
) -> List[Path]:
    """Save *fig* to one or more file formats at publication resolution.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to save.
    output_dir : str or Path
        Destination directory (created if it does not exist).
    stem : str
        File name without extension.
    formats : list of str, optional
        Formats to write. Defaults to ``["tiff", "pdf"]``.
    dpi : int
        Resolution in dots per inch. Defaults to 300.

    Returns
    -------
    list of Path
        Absolute paths of every file written.

    Examples
    --------
    >>> paths = save_figure(fig, "data/results/figures", "site_RH")
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    formats = formats or FIGURE_FORMATS
    saved: List[Path] = []
    for fmt in formats:
        path = output_dir / f"{stem}.{fmt}"
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        saved.append(path)
    return saved


def add_phenology_markers(
    ax: plt.Axes,
    phenology_df: pd.DataFrame,
    source: Optional[str] = None,
    year: Optional[int] = None,
    annotate: bool = True,
) -> None:
    """Draw SoS / PoS / EoS vertical dashed lines on a date-indexed axes.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes. The x-axis is expected to be in matplotlib date format.
    phenology_df : pd.DataFrame
        Output of :func:`~lensky_py_lab.phenology.phenolopy_integration.extract_phenology`.
        Must contain columns ``SoS_date``, ``PoS_date``, ``EoS_date``.
    source : str, optional
        Filter to a single satellite/source name (matches the ``satellite`` column).
    year : int, optional
        Filter to a single hydrological year.
    annotate : bool
        If *True*, add a small rotated label near each line.

    Notes
    -----
    Marker colours are thesis-consistent:
    * SoS → orange  (#FF7F00)
    * PoS → red     (#E41A1C)
    * EoS → purple  (#984EA3)
    """
    df = phenology_df.copy()
    if source is not None and "satellite" in df.columns:
        df = df[df["satellite"] == source]
    if year is not None and "year" in df.columns:
        df = df[df["year"] == year]

    _MARKER_LINESTYLES = {"SoS": "--", "PoS": "-", "EoS": ":"}
    drawn_types: set = set()
    xlim = ax.get_xlim()

    for _, row in df.iterrows():
        sat = str(row.get("satellite", ""))
        color = source_color(sat)
        for marker, col in [("SoS", "SoS_date"), ("PoS", "PoS_date"), ("EoS", "EoS_date")]:
            val = row.get(col)
            if val is None or pd.isna(val):
                continue
            date = pd.to_datetime(val)
            if not (xlim[0] <= mdates.date2num(date) <= xlim[1]):
                continue
            ax.axvline(
                date, color=color, linestyle=_MARKER_LINESTYLES[marker],
                linewidth=1.3, alpha=0.8, label=None,
            )
            if annotate:
                ymax = ax.get_ylim()[1]
                ax.text(
                    date, ymax * 0.97, marker,
                    color=color, fontsize=7, ha="center", va="top",
                    rotation=90, clip_on=True,
                )
            drawn_types.add(marker)

    # One schematic legend entry per marker type actually drawn
    for marker in ["SoS", "PoS", "EoS"]:
        if marker in drawn_types:
            ax.plot([], [], color="black", linestyle=_MARKER_LINESTYLES[marker],
                    linewidth=1.3, alpha=0.8, label=marker)


def plot_site_publication(
    site_name: str,
    site_df: pd.DataFrame,
    phenology_df: Optional[pd.DataFrame] = None,
    output_dir: Optional[Union[str, Path]] = None,
    ims_rain: bool = True,
    figsize: Optional[Tuple[float, float]] = None,
) -> plt.Figure:
    """Publication-quality site time-series figure.

    Overlays all LOWESS series, optionally annotates phenological markers,
    and draws rainfall as a secondary axis.  Saved as 300 DPI TIFF + PDF when
    *output_dir* is provided.

    Parameters
    ----------
    site_name : str
        Site identifier used as the figure title and output file stem.
    site_df : pd.DataFrame
        Output of :meth:`~lensky_py_lab.models.site.Site.run_analysis`, indexed
        by unix timestamp.
    phenology_df : pd.DataFrame, optional
        Output of :func:`~lensky_py_lab.phenology.phenolopy_integration.extract_phenology`.
        If provided, SoS / PoS / EoS lines are drawn on the axes.
    output_dir : str or Path, optional
        If given, the figure is saved here as TIFF and PDF.
    ims_rain : bool
        Whether to plot rainfall on a secondary y-axis (default *True*).
    figsize : tuple, optional
        Override ``(width, height)`` in inches.

    Returns
    -------
    matplotlib.figure.Figure

    Examples
    --------
    >>> fig = plot_site_publication("Ramat Hanadiv", site_df, phenology_df,
    ...                             output_dir="data/results/figures/final")
    """
    from lensky_py_lab.constants import (
        IMS_RAINFALL_FIELD,
        IMS_TEMPERATURE_FIELD,
        NDVI_LOWESS_FIELD,
    )

    lowess_cols = [c for c in site_df.columns if c.startswith(f"{NDVI_LOWESS_FIELD} ")]
    has_rain = ims_rain and IMS_RAINFALL_FIELD in site_df.columns
    has_temp = IMS_TEMPERATURE_FIELD in site_df.columns

    fig, ax = plt.subplots(figsize=figsize or (18, 7))
    ts_unix = site_df.index.values
    for col in lowess_cols:
        src = col.removeprefix(f"{NDVI_LOWESS_FIELD} ")
        color = source_color(src)
        linestyle = "--" if src.upper().startswith("NSRS") else "-"
        dates_plot, vals_plot = dense_interpolate_with_gaps(
            ts_unix, site_df[col].values, WIDE_GAP_SECONDS
        )
        ax.plot(dates_plot, vals_plot, label=src, color=color,
                linewidth=2.0, linestyle=linestyle)

    # Phenology markers — drawn before legend so they appear in it
    if phenology_df is not None and not phenology_df.empty:
        add_phenology_markers(ax, phenology_df, annotate=True)

    ax.set_ylabel("NDVI", fontsize=12)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_title(f"{site_name} — NDVI Time Series", fontsize=14, fontweight="bold")
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    _format_date_axis(ax)

    if has_rain:
        ax2 = ax.twinx()
        rain_vals = site_df[IMS_RAINFALL_FIELD].values
        rain_mask = np.isfinite(rain_vals)
        rain_dates = pd.to_datetime(ts_unix[rain_mask], unit="s")
        ax2.bar(rain_dates, rain_vals[rain_mask], alpha=0.22,
                color=COLORS.get("rainfall", "steelblue"),
                width=5, label="Rainfall (mm)", zorder=0)
        ax2.invert_yaxis()
        ax2.set_ylabel("Rainfall (mm)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=9)

    if has_temp:
        ax3 = ax.twinx()
        if has_rain:
            ax3.spines["right"].set_position(("outward", 60))
        temp_vals = site_df[IMS_TEMPERATURE_FIELD].values
        temp_mask = np.isfinite(temp_vals)
        temp_dates = pd.to_datetime(ts_unix[temp_mask], unit="s")
        ax3.plot(temp_dates, temp_vals[temp_mask],
                 color=COLORS.get("temperature", "red"),
                 linewidth=1.2, linestyle=":", label="Temp (°C)")
        ax3.set_ylabel("Temperature (°C)", fontsize=10)
        ax3.legend(loc="lower right", fontsize=9)

    fig.tight_layout()

    if output_dir is not None:
        safe_name = site_name.replace(" ", "_").replace("/", "-")
        save_figure(fig, output_dir, f"{safe_name}_timeseries")

    return fig


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_date_axis(ax: plt.Axes) -> None:
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=9)


