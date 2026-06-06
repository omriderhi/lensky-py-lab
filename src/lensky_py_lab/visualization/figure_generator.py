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

# Marker shapes for scatter-point style
_PHENO_SHAPES: Dict[str, str] = {"SoS": "^", "PoS": "o", "EoS": "v"}

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


def add_phenology_markers(
    ax: plt.Axes,
    phenology_df: pd.DataFrame,
    source: Optional[str] = None,
    year: Optional[int] = None,
    annotate: bool = True,
    style: str = "lines",
) -> None:
    """Draw SoS / PoS / EoS markers on a date-indexed axes.

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
        If *True* (lines style), add a small rotated label near each line.
    style : str
        ``"lines"`` — vertical dashed span lines (default, publication style).
        ``"points"`` — scatter dots placed on the NDVI curve at each event date.
        Requires ``SoS_value``, ``PoS_value``, ``EoS_value`` columns in
        *phenology_df* (produced by ``extract_phenology``).

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

    if style == "points":
        _add_phenology_points(ax, df)
        return

    # --- lines style (original) ---
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


def _add_phenology_points(ax: plt.Axes, df: pd.DataFrame) -> None:
    """Plot SoS/PoS/EoS as scatter dots on the NDVI curve.

    Dot fill = phenology-type colour; dot edge = source colour.
    One legend entry per marker type is added.
    """
    xlim = ax.get_xlim()
    drawn_types: set = set()

    _DATE_VAL = [
        ("SoS", "SoS_date", "SoS_value"),
        ("PoS", "PoS_date", "PoS_value"),
        ("EoS", "EoS_date", "EoS_value"),
    ]

    for _, row in df.iterrows():
        sat = str(row.get("satellite", ""))
        edge_color = source_color(sat)
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
                s=80, zorder=5,
                edgecolors=edge_color, linewidths=1.5,
            )
            drawn_types.add(marker)

    for marker in ["SoS", "PoS", "EoS"]:
        if marker in drawn_types:
            ax.scatter([], [], color=PHENOLOGY_COLORS[marker],
                       marker=_PHENO_SHAPES[marker], s=80,
                       edgecolors="black", linewidths=1.5, label=marker)


def plot_site_publication(
    site_name: str,
    site_df: pd.DataFrame,
    phenology_df: Optional[pd.DataFrame] = None,
    output_dir: Optional[Union[str, Path]] = None,
    ims_rain: bool = True,
    figsize: Optional[Tuple[float, float]] = None,
    phenology_style: str = "lines",
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
    phenology_style : str
        ``"lines"`` — vertical span lines (default).
        ``"points"`` — scatter dots placed on each NDVI curve at the event date.

    Returns
    -------
    matplotlib.figure.Figure

    Examples
    --------
    >>> fig = plot_site_publication("Ramat Hanadiv", site_df, phenology_df,
    ...                             output_dir="data/results/figures/final",
    ...                             phenology_style="points")
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
        annotate = (phenology_style == "lines")
        add_phenology_markers(ax, phenology_df, annotate=annotate, style=phenology_style)

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
    woody_color = COLORS.get("woody", "#5B4A3F")
    herb_color = COLORS.get("herbaceous", "#4CAF50")

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

    for ax, panel in zip(axes, panels):
        # Satellite / decomposed component
        sat_s = panel["sat_series"]
        if sat_s is not None and not sat_s.dropna().empty:
            sat_ts = sat_s.index.values
            dates_plot, vals_plot = dense_interpolate_with_gaps(
                sat_ts, sat_s.values, WIDE_GAP_SECONDS
            )
            ax.plot(dates_plot, vals_plot,
                    label=panel["sat_label"], color=panel["sat_color"],
                    linewidth=2.2, linestyle="-")

        # NSRS sensor
        nsrs_col = panel["nsrs_col"]
        if nsrs_col in site_df.columns:
            dates_nsrs, vals_nsrs = dense_interpolate_with_gaps(
                ts_unix, site_df[nsrs_col].values, WIDE_GAP_SECONDS
            )
            ax.plot(dates_nsrs, vals_nsrs,
                    label=panel["nsrs_label"], color=panel["nsrs_color"],
                    linewidth=1.8, linestyle="--")
        else:
            ax.text(0.5, 0.5, f"{nsrs_col} not available",
                    transform=ax.transAxes, ha="center", va="center",
                    fontsize=9, color="gray")

        ax.set_ylabel(panel["ylabel"], fontsize=11)
        ax.set_title(panel["title"], fontsize=11, fontweight="bold")
        ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
        _format_date_axis(ax)

    fig.suptitle(
        f"{site_name} — {satellite_name} woody/herbaceous decomposition vs NSRS",
        fontsize=13, fontweight="bold", y=1.01,
    )
    fig.tight_layout()

    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{satellite_name}_decomposition_vs_NSRS.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")

    return fig


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_date_axis(ax: plt.Axes) -> None:
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=9)
