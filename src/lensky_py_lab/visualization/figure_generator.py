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
from typing import Dict, List, Optional, Tuple, Union

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
        FONT_SIZE_LEGEND,
        FONT_SIZE_PANEL_LETTER,
        FONT_SIZE_TICK_DATE,
        NSRS_LINESTYLE,
        NSRS_LINEWIDTH,
        SATELLITE_LINEWIDTH,
        SAVE_DPI,
        apply_publication_style,
        source_color,
    )

    apply_publication_style()
    _HAS_PLOT_CONFIG = True
except ImportError:  # pragma: no cover
    _HAS_PLOT_CONFIG = False
    FIGURE_DPI = 300
    SAVE_DPI = 300
    FIGURE_FORMATS = ["tiff"]
    FONT_SIZE_LEGEND = 14
    FONT_SIZE_PANEL_LETTER = 16
    FONT_SIZE_TICK_DATE = 11
    NSRS_LINESTYLE = "-"
    NSRS_LINEWIDTH = 2.8
    SATELLITE_LINEWIDTH = 1.8
    COLORS: Dict[str, str] = {
        "modis":           "#0072B2",
        "sentinel2":       "#E69F00",
        "landsat8":        "#009E73",
        "venus":           "#D55E00",
        "planet":          "#CC79A7",
        "nsrs1":           "#D55E00",
        "nsrs2":           "#CC79A7",
        "nsrs3_raw":       "#999999",
        "nsrs3_corrected": "#000000",
        "woody":           "#E69F00",
        "herbaceous":      "#009E73",
        "sos":             "#F0E442",
        "pos":             "#D55E00",
        "eos":             "#56B4E9",
        "rainfall":        "#56B4E9",
        "temperature":     "#999999",
    }

    def source_color(name: str) -> str:  # type: ignore[misc]
        """Fallback when plot_config is unavailable."""
        return "#333333"

from lensky_py_lab.gap_utils import WIDE_GAP_SECONDS, dense_interpolate_with_gaps  # noqa: E402
from lensky_py_lab.visualization.phenology_markers import draw_phenology_markers  # noqa: E402

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
        Formats to write. Defaults to ``["png"]``.
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


def add_panel_letter(ax: plt.Axes, letter: str) -> None:
    """Place a bold subplot letter (e.g. ``"A"``) in the top-left of *ax*."""
    ax.text(
        0.012, 0.97, letter, transform=ax.transAxes,
        fontsize=FONT_SIZE_PANEL_LETTER, fontweight="bold",
        ha="left", va="top", zorder=10,
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                  edgecolor="none", alpha=0.85),
    )


def add_phenology_markers(
    ax: plt.Axes,
    phenology_df: pd.DataFrame,
    source: Optional[str] = None,
    year: Optional[int] = None,
) -> None:
    """Draw SoS / PoS / EoS points on a date-indexed axes.

    Thin wrapper around :func:`lensky_py_lab.visualization.phenology_markers.draw_phenology_markers`
    kept under this name for API compatibility with existing callers.

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
    * SoS → yellow     (#F0E442)
    * PoS → vermillion (#D55E00)
    * EoS → sky blue   (#56B4E9)
    """
    draw_phenology_markers(ax, phenology_df, source=source, year=year)


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
    and draws rainfall as a secondary axis.  Saved as 300 DPI PNG when
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
        If provided, SoS / PoS / EoS markers are drawn on the axes.
    output_dir : str or Path, optional
        If given, the figure is saved here as PNG.
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
        is_nsrs = src.upper().startswith("NSRS")
        dates_plot, vals_plot = dense_interpolate_with_gaps(
            ts_unix, site_df[col].values, WIDE_GAP_SECONDS
        )
        ax.plot(dates_plot, vals_plot, label=src, color=color,
                linewidth=NSRS_LINEWIDTH if is_nsrs else SATELLITE_LINEWIDTH,
                linestyle=NSRS_LINESTYLE if is_nsrs else "-",
                zorder=4 if is_nsrs else 3)

    # Phenology markers — drawn before legend so they appear in it
    if phenology_df is not None and not phenology_df.empty:
        add_phenology_markers(ax, phenology_df)

    ax.set_ylabel("NDVI", fontsize=12)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_title(f"{site_name} — NDVI Time Series", fontsize=14, fontweight="bold")
    ax.legend(loc="upper left", fontsize=FONT_SIZE_LEGEND, framealpha=0.9)
    _format_date_axis(ax)

    if has_rain:
        ax2 = ax.twinx()
        rain_vals = site_df[IMS_RAINFALL_FIELD].values
        rain_mask = np.isfinite(rain_vals)
        rain_dates = pd.to_datetime(ts_unix[rain_mask], unit="s")
        ax2.bar(rain_dates, rain_vals[rain_mask], alpha=0.22,
                color=COLORS.get("rainfall", "#56B4E9"),
                width=5, label="Rainfall (mm)", zorder=0)
        ax2.invert_yaxis()
        ax2.set_ylabel("Rainfall (mm)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=FONT_SIZE_LEGEND)

    if has_temp:
        ax3 = ax.twinx()
        if has_rain:
            ax3.spines["right"].set_position(("outward", 60))
        temp_vals = site_df[IMS_TEMPERATURE_FIELD].values
        temp_mask = np.isfinite(temp_vals)
        temp_dates = pd.to_datetime(ts_unix[temp_mask], unit="s")
        ax3.plot(temp_dates, temp_vals[temp_mask],
                 color=COLORS.get("temperature", "#999999"),
                 linewidth=1.2, linestyle=":", label="Temp (°C)")
        ax3.set_ylabel("Temperature (°C)", fontsize=10)
        ax3.legend(loc="lower right", fontsize=FONT_SIZE_LEGEND)

    fig.tight_layout()

    if output_dir is not None:
        safe_name = site_name.replace(" ", "_").replace("/", "-")
        save_figure(fig, output_dir, f"{safe_name}_timeseries")

    return fig


def plot_decomposition_comparative(
    site_name: str,
    site_df: pd.DataFrame,
    satellite_name: str,
    woody_series: pd.Series,
    herbaceous_series: pd.Series,
    nsrs_full_col: str = "NDVI lowess NSRS_3",
    nsrs_woody_col: str = "NDVI lowess NSRS_2",
    nsrs_herb_col: str = "NDVI lowess NSRS_1",
    output_dir: Optional[Union[str, Path]] = None,
    figsize: Optional[Tuple[float, float]] = None,
) -> plt.Figure:
    """Three-panel figure comparing each satellite NDVI component to its NSRS equivalent.

    Validates the Helman (2015) decomposition against direct sensor measurements:

    * Panel 1 — Full signal: satellite raw NDVI vs NSRS_3 (wide-angle, satellite-imitating).
    * Panel 2 — Woody component: satellite woody trend vs NSRS_2 (narrow, aimed at canopy).
    * Panel 3 — Herbaceous component: satellite herbaceous residual vs NSRS_1 (narrow, aimed at understory).

    The NSRS sensors observe each vegetation layer directly; the decomposition
    attempts to extract those same layers from the mixed satellite pixel.  Matching
    phenological timing across panels confirms the decomposition is ecologically valid.

    Parameters
    ----------
    site_name : str
        Site identifier used in the figure title.
    site_df : pd.DataFrame
        Output of ``Site.run_analysis()``, indexed by unix timestamp.
        Must contain ``"NDVI lowess <satellite_name>"`` and the NSRS columns.
    satellite_name : str
        Name of the satellite source (e.g. ``"MODIS"``).
    woody_series : pd.Series
        Woody component produced by
        :func:`~lensky_py_lab.phenology.phenolopy_integration.decompose_woody_herbaceous`,
        indexed by unix timestamp.
    herbaceous_series : pd.Series
        Herbaceous component from the same decomposition call.
    nsrs_full_col : str
        Column name in *site_df* for the full-signal NSRS sensor (default: NSRS_3).
    nsrs_woody_col : str
        Column name for the woody-targeting NSRS sensor (default: NSRS_2).
    nsrs_herb_col : str
        Column name for the herbaceous-targeting NSRS sensor (default: NSRS_1).
    output_dir : str or Path, optional
        If given, saves the figure as a PNG (150 DPI) in this directory.
    figsize : tuple, optional
        Override ``(width, height)`` in inches.

    Returns
    -------
    matplotlib.figure.Figure

    Examples
    --------
    >>> woody, herb = decompose_woody_herbaceous(site_df["NDVI lowess MODIS"])
    >>> if woody is not None:
    ...     fig = plot_decomposition_comparative("RH", site_df, "MODIS", woody, herb,
    ...                                          output_dir="data/results/figures/decomposition")
    """
    from lensky_py_lab.constants import NDVI_LOWESS_FIELD

    sat_col = f"{NDVI_LOWESS_FIELD} {satellite_name}"
    sat_color = source_color(satellite_name)
    woody_color = COLORS.get("woody", "#E69F00")
    herb_color = COLORS.get("herbaceous", "#009E73")

    panels = [
        {
            "sat_series": site_df.get(sat_col),
            "sat_label": satellite_name,
            "sat_color": sat_color,
            "nsrs_col": nsrs_full_col,
            "nsrs_label": nsrs_full_col.replace(f"{NDVI_LOWESS_FIELD} ", ""),
            "nsrs_color": source_color(nsrs_full_col.replace(f"{NDVI_LOWESS_FIELD} ", "")),
            "title": f"Full signal: {satellite_name} vs "
                     f"{nsrs_full_col.replace(NDVI_LOWESS_FIELD + ' ', '')} (wide-angle)",
            "ylabel": "NDVI",
        },
        {
            "sat_series": woody_series,
            "sat_label": f"{satellite_name} woody",
            "sat_color": woody_color,
            "nsrs_col": nsrs_woody_col,
            "nsrs_label": nsrs_woody_col.replace(f"{NDVI_LOWESS_FIELD} ", ""),
            "nsrs_color": source_color(nsrs_woody_col.replace(f"{NDVI_LOWESS_FIELD} ", "")),
            "title": f"Woody component: {satellite_name} decomposed vs "
                     f"{nsrs_woody_col.replace(NDVI_LOWESS_FIELD + ' ', '')} (canopy)",
            "ylabel": "NDVI",
        },
        {
            "sat_series": herbaceous_series,
            "sat_label": f"{satellite_name} herbaceous",
            "sat_color": herb_color,
            "nsrs_col": nsrs_herb_col,
            "nsrs_label": nsrs_herb_col.replace(f"{NDVI_LOWESS_FIELD} ", ""),
            "nsrs_color": source_color(nsrs_herb_col.replace(f"{NDVI_LOWESS_FIELD} ", "")),
            "title": f"Herbaceous component: {satellite_name} decomposed vs "
                     f"{nsrs_herb_col.replace(NDVI_LOWESS_FIELD + ' ', '')} (understory)",
            "ylabel": "ΔNDVI",
        },
    ]

    fig, axes = plt.subplots(3, 1, figsize=figsize or (18, 12), sharex=True)
    ts_unix = site_df.index.values

    for ax, panel, letter in zip(axes, panels, "ABC"):
        # Satellite / decomposed component
        sat_s = panel["sat_series"]
        if sat_s is not None and not sat_s.dropna().empty:
            sat_ts = sat_s.index.values
            dates_plot, vals_plot = dense_interpolate_with_gaps(
                sat_ts, sat_s.values, WIDE_GAP_SECONDS
            )
            ax.plot(dates_plot, vals_plot,
                    label=panel["sat_label"], color=panel["sat_color"],
                    linewidth=SATELLITE_LINEWIDTH, linestyle="-", zorder=3)

        # NSRS sensor
        nsrs_col = panel["nsrs_col"]
        if nsrs_col in site_df.columns:
            dates_nsrs, vals_nsrs = dense_interpolate_with_gaps(
                ts_unix, site_df[nsrs_col].values, WIDE_GAP_SECONDS
            )
            ax.plot(dates_nsrs, vals_nsrs,
                    label=panel["nsrs_label"], color=panel["nsrs_color"],
                    linewidth=NSRS_LINEWIDTH, linestyle=NSRS_LINESTYLE, zorder=4)
        else:
            ax.text(0.5, 0.5, f"{nsrs_col} not available",
                    transform=ax.transAxes, ha="center", va="center",
                    fontsize=9, color="gray")

        ax.set_ylabel(panel["ylabel"])
        ax.set_title(panel["title"])
        ax.legend(loc="upper right", fontsize=FONT_SIZE_LEGEND, framealpha=0.9)
        add_panel_letter(ax, letter)
        _format_date_axis(ax)

    _equalize_y_span(axes[1:])

    fig.suptitle(
        f"{site_name} — {satellite_name} woody/herbaceous decomposition vs NSRS",
        fontsize=13, fontweight="bold", y=1.01,
    )
    fig.tight_layout()

    if output_dir is not None:
        save_figure(fig, output_dir, f"{satellite_name}_decomposition_vs_NSRS",
                    dpi=SAVE_DPI)

    return fig


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _equalize_y_span(axes) -> None:
    """Give *axes* the same y-axis span (largest current span), each centred on its own data.

    Tick spacing is then directly comparable between panels even when the
    panels have different offsets (e.g. woody NDVI vs herbaceous ΔNDVI).
    """
    limits = [ax.get_ylim() for ax in axes]
    span = max(hi - lo for lo, hi in limits)
    for ax, (lo, hi) in zip(axes, limits):
        mid = (lo + hi) / 2
        ax.set_ylim(mid - span / 2, mid + span / 2)


def _format_date_axis(ax: plt.Axes) -> None:
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=FONT_SIZE_TICK_DATE)
