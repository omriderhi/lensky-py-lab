"""
Module: plotter.py
Description: Diagnostic and exploratory plotting for the Lensky Lab pipeline.
             Publication-quality export is handled by
             :mod:`lensky_py_lab.visualization.figure_generator`.
Author: Omri Derhi
Institution: Bar-Ilan University
Date: 2025
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from lensky_py_lab.constants import (
    IMS_RAINFALL_FIELD,
    IMS_TEMPERATURE_FIELD,
    NDVI_CLEAN_FIELD,
    NDVI_FILTERED_FIELD,
    NDVI_LOWESS_FIELD,
    NDVI_RAW_FIELD,
)
from lensky_py_lab.gap_utils import (
    WIDE_GAP_SECONDS,
    boundaries_from_raw,
    dense_interpolate_from_boundaries,
    dense_interpolate_with_gaps,
    iter_segments_from_boundaries,
)

# ---------------------------------------------------------------------------
# Attempt to load shared plot_config from repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from plot_config import COLORS, apply_publication_style, source_color  # type: ignore[import]

    apply_publication_style()
    _HAS_PLOT_CONFIG = True
except ImportError:
    _HAS_PLOT_CONFIG = False
    COLORS: dict = {}

    def source_color(name: str) -> str:  # type: ignore[misc]
        return "#333333"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PIPELINE_STAGES = [NDVI_RAW_FIELD, NDVI_FILTERED_FIELD, NDVI_CLEAN_FIELD, NDVI_LOWESS_FIELD]

_PHENOLOGY_COLORS: dict = {
    "SoS": COLORS.get("sos", "#FF7F00"),   # orange
    "PoS": COLORS.get("pos", "#E41A1C"),   # red
    "EoS": COLORS.get("eos", "#984EA3"),   # purple
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plot_cleaning_pipeline(
    source_name: str,
    processed_df: pd.DataFrame,
    figsize: Optional[tuple] = None,
) -> Figure:
    """Show each stage of the cleaning pipeline as a vertically-stacked subplot.

    Each panel uses a rendering style suited to its data density:

    * **RAW / filtered** — scatter dots + connecting line (data is dense).
    * **clean** — scatter dots only; connecting sparse points would produce
      crossing diagonal lines ("spider-web" artefact).
    * **lowess** — dense linear interpolation between LOWESS knots so the
      curve is always smooth and connected, even with very few knot points.

    NaN values are masked in every panel so no vertical drop-to-zero
    artefacts appear.

    Parameters
    ----------
    source_name : str
        Used as the figure title.
    processed_df : pd.DataFrame
        Output of :func:`~lensky_py_lab.pipeline.processor.process_source`,
        indexed by unix timestamp.
    figsize : tuple, optional
        Override ``(width, height)`` in inches.

    Returns
    -------
    matplotlib.figure.Figure
    """
    stages = [s for s in _PIPELINE_STAGES if s in processed_df.columns]
    n = len(stages)
    if n == 0:
        raise ValueError("processed_df contains none of the expected pipeline columns.")

    fig, axes = plt.subplots(n, 1, figsize=figsize or (18, 4 * n), sharex=True)
    if n == 1:
        axes = [axes]

    ts_unix = processed_df.index.values   # unix timestamps (int)

    # Derive segment boundaries from the raw column once so that every stage
    # (filtered, clean, LOWESS) shares identical break points. This prevents
    # data-quality holes in filtered/clean data from producing false extra cuts.
    raw_bounds = None
    if NDVI_RAW_FIELD in processed_df.columns:
        raw_bounds = boundaries_from_raw(
            ts_unix, processed_df[NDVI_RAW_FIELD].values, WIDE_GAP_SECONDS
        )

    for ax, stage in zip(axes, stages):
        values = processed_df[stage].values
        mask = np.isfinite(values)

        if not mask.any():
            ax.set_ylabel(stage, fontsize=9)
            ax.legend(loc="upper right", fontsize=8)
            continue

        color = source_color(source_name)

        if stage == NDVI_LOWESS_FIELD:
            if raw_bounds is not None:
                dates_plot, vals_plot = dense_interpolate_from_boundaries(
                    ts_unix, values, raw_bounds
                )
            else:
                dates_plot, vals_plot = dense_interpolate_with_gaps(
                    ts_unix, values, WIDE_GAP_SECONDS
                )
            ax.plot(dates_plot, vals_plot, linewidth=2.0, color=color, label=stage)

        elif stage == NDVI_CLEAN_FIELD:
            # Scatter only — connecting sparse points creates crossing lines
            dates_plot = pd.to_datetime(ts_unix[mask], unit="s")
            ax.scatter(dates_plot, values[mask], s=18, zorder=3, color=color, label=stage)

        else:
            # RAW / filtered: iterate segments from raw boundaries so all stages
            # share the same break points and data-quality gaps are not false-cut
            seg_iter = (
                iter_segments_from_boundaries(ts_unix, values, raw_bounds)
                if raw_bounds is not None
                else _iter_gap_fallback(ts_unix, values)
            )
            first = True
            for ts_seg, vals_seg in seg_iter:
                dates_seg = pd.to_datetime(ts_seg, unit="s")
                ax.plot(dates_seg, vals_seg, "o-", color=color,
                        markersize=2, linewidth=0.8,
                        label=stage if first else None)
                first = False

        ax.set_ylabel(stage, fontsize=9)
        ax.legend(loc="upper right", fontsize=8)
        _format_date_axis(ax)

    fig.suptitle(f"{source_name} — cleaning pipeline", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def plot_site(
    site_name: str,
    site_df: pd.DataFrame,
    phenology_df: Optional[pd.DataFrame] = None,
    figsize: Optional[tuple] = None,
) -> Figure:
    """Overlay all LOWESS sources on one axes; add IMS data on secondary axes.

    Each LOWESS column is densely interpolated before plotting so all curves
    are smooth and fully connected regardless of how many knot points the
    LOWESS produced.

    Parameters
    ----------
    site_name : str
        Used as the axes title.
    site_df : pd.DataFrame
        Output of :meth:`~lensky_py_lab.models.site.Site.run_analysis`,
        indexed by unix timestamp.
    phenology_df : pd.DataFrame, optional
        If provided, draws SoS / PoS / EoS vertical dashed lines.
        Expected columns: ``SoS_date``, ``PoS_date``, ``EoS_date``.
        Colours: SoS=orange, PoS=red, EoS=purple (thesis convention).
    figsize : tuple, optional
        Override ``(width, height)`` in inches.

    Returns
    -------
    matplotlib.figure.Figure
    """
    lowess_cols = [c for c in site_df.columns if c.startswith(f"{NDVI_LOWESS_FIELD} ")]
    has_rain = IMS_RAINFALL_FIELD in site_df.columns
    has_temp = IMS_TEMPERATURE_FIELD in site_df.columns

    fig, ax = plt.subplots(figsize=figsize or (16, 6))
    ts_unix = site_df.index.values

    for col in lowess_cols:
        src = col.removeprefix(f"{NDVI_LOWESS_FIELD} ")
        color = source_color(src)
        linestyle = "--" if src.upper().startswith("NSRS") else "-"

        dates_plot, vals_plot = dense_interpolate_with_gaps(
            ts_unix, site_df[col].values, WIDE_GAP_SECONDS
        )
        ax.plot(dates_plot, vals_plot, label=src, color=color,
                linewidth=1.8, linestyle=linestyle)

    # ---- Phenological markers ----
    if phenology_df is not None and not phenology_df.empty:
        _draw_phenology_markers(ax, phenology_df)

    ax.set_ylabel("NDVI", fontsize=11)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_title(site_name, fontsize=12, fontweight="bold")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    _format_date_axis(ax)

    if has_rain:
        ax2 = ax.twinx()
        rain_color = COLORS.get("rainfall", "steelblue")
        # Rainfall: bar chart only for non-NaN dates
        rain_vals = site_df[IMS_RAINFALL_FIELD].values
        rain_mask = np.isfinite(rain_vals)
        rain_dates = pd.to_datetime(ts_unix[rain_mask], unit="s")
        ax2.bar(rain_dates, rain_vals[rain_mask], alpha=0.25, color=rain_color,
                width=5, label="Rainfall (mm)", zorder=0)
        ax2.invert_yaxis()
        ax2.set_ylabel("Rainfall (mm)", fontsize=10)
        ax2.legend(loc="upper right", fontsize=8)

    if has_temp:
        ax3 = ax.twinx()
        if has_rain:
            ax3.spines["right"].set_position(("outward", 60))
        temp_color = COLORS.get("temperature", "red")
        # Temperature: connect only non-NaN values (no gaps)
        temp_vals = site_df[IMS_TEMPERATURE_FIELD].values
        temp_mask = np.isfinite(temp_vals)
        temp_dates = pd.to_datetime(ts_unix[temp_mask], unit="s")
        ax3.plot(temp_dates, temp_vals[temp_mask], color=temp_color,
                 linewidth=1.2, linestyle=":", label="Temp (°C)")
        ax3.set_ylabel("Temperature (°C)", fontsize=10)
        ax3.legend(loc="lower right", fontsize=8)

    fig.tight_layout()
    return fig


def plot_data_availability(
    site_name: str,
    site_df: pd.DataFrame,
    figsize: Optional[tuple] = None,
) -> Figure:
    """Horizontal timeline showing data coverage for every NDVI source.

    One row per source; each observation (non-NaN LOWESS knot) is drawn as a
    short vertical tick in the source's colour.  Gaps are visible as empty
    space, making it easy to compare coverage across satellites and sensors.

    Parameters
    ----------
    site_name : str
        Used as the figure title.
    site_df : pd.DataFrame
        Output of :meth:`~lensky_py_lab.models.site.Site.run_analysis`,
        indexed by unix timestamp.
    figsize : tuple, optional
        Override ``(width, height)`` in inches.

    Returns
    -------
    matplotlib.figure.Figure
    """
    lowess_cols = [c for c in site_df.columns if c.startswith(f"{NDVI_LOWESS_FIELD} ")]
    n = len(lowess_cols)
    if n == 0:
        raise ValueError("site_df contains no NDVI lowess columns.")

    fig, ax = plt.subplots(figsize=figsize or (16, max(3.0, 0.5 * n + 1.5)))
    ts_unix = site_df.index.values

    for i, col in enumerate(lowess_cols):
        src = col.removeprefix(f"{NDVI_LOWESS_FIELD} ")
        color = source_color(src)
        mask = np.isfinite(site_df[col].values)
        if mask.any():
            date_nums = mdates.date2num(
                pd.to_datetime(ts_unix[mask], unit="s").to_pydatetime()
            )
            ax.eventplot(date_nums, lineoffsets=i, linelengths=0.7,
                         colors=color, linewidths=2.0)

    ax.set_yticks(range(n))
    ax.set_yticklabels([c.removeprefix(f"{NDVI_LOWESS_FIELD} ") for c in lowess_cols],
                       fontsize=9)
    ax.set_ylim(-0.5, n - 0.5)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_title(f"{site_name} — Data Availability", fontsize=12, fontweight="bold")
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    _format_date_axis(ax)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iter_gap_fallback(ts_unix, values):
    """Fallback segment iterator used when no raw column is available."""
    from lensky_py_lab.gap_utils import iter_gap_segments
    yield from iter_gap_segments(ts_unix, values, WIDE_GAP_SECONDS)


_MARKER_LINESTYLES: dict = {"SoS": "--", "PoS": "-", "EoS": ":"}


def _draw_phenology_markers(ax: plt.Axes, phenology_df: pd.DataFrame) -> None:
    """Draw SoS / PoS / EoS vertical lines on *ax* using source colours.

    Each source gets its own colour (matching the NDVI curve).  Line styles
    distinguish marker type: SoS '--', PoS '-', EoS ':'.
    One schematic legend entry per marker type (black, no source label) is
    added so the legend stays compact regardless of how many sources are shown.
    """
    xlim = ax.get_xlim()
    drawn_types: set = set()

    for _, row in phenology_df.iterrows():
        sat = str(row.get("satellite", ""))
        color = source_color(sat)
        for marker, col in [("SoS", "SoS_date"), ("PoS", "PoS_date"), ("EoS", "EoS_date")]:
            val = row.get(col)
            if val is None or pd.isna(val):
                continue
            date = pd.to_datetime(val)
            if not (xlim[0] <= mdates.date2num(date) <= xlim[1]):
                continue
            ax.axvline(date, color=color, linestyle=_MARKER_LINESTYLES[marker],
                       linewidth=1.3, alpha=0.8, label=None)
            y_top = ax.get_ylim()[1]
            ax.text(date, y_top * 0.97, marker,
                    color=color, fontsize=7, ha="center", va="top",
                    rotation=90, clip_on=True)
            drawn_types.add(marker)

    # One schematic legend entry per marker type actually drawn
    for marker in ["SoS", "PoS", "EoS"]:
        if marker in drawn_types:
            ax.plot([], [], color="black", linestyle=_MARKER_LINESTYLES[marker],
                    linewidth=1.3, alpha=0.8, label=marker)


def _format_date_axis(ax: plt.Axes) -> None:
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
