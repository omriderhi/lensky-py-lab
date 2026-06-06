"""
Module: orientation_map.py
Description: Orientation and pixel-resolution figures for the Lensky Lab thesis.

Two publication-quality figures:

1. ``plot_site_location``         — two-panel figure: Israel overview (OSM basemap)
                                     and a local zoom, so the reader can place the
                                     research site on a real map.

2. ``plot_pixel_size_comparison`` — single-panel figure: MODIS (250 m), Landsat-8
                                     (30 m), and Sentinel-2 (10 m) pixel grids all
                                     overlaid on satellite imagery at the study site,
                                     so pixel sizes are directly comparable.

Both require the ``maps`` optional extra (contextily)::

    pip install contextily
    pip install 'lensky-py-lab[maps]'

Author: Omri Derhi
Institution: Bar-Ilan University
Date: 2025
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from lensky_py_lab.constants import SATELLITE_NATIVE_RESOLUTION_M, SatelliteSource
from lensky_py_lab.visualization.figure_generator import save_figure

# ---------------------------------------------------------------------------
# Shared plot_config (same pattern as plotter.py / figure_generator.py)
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
# Site constants
# ---------------------------------------------------------------------------

_SITE_LON:  float = 34.946667
_SITE_LAT:  float = 32.555806
_SITE_NAME: str   = "Ramat HaNadiv"

# Web Mercator scale factor at the site latitude.
# At lat φ, 1 ground metre = 1/cos(φ) units in EPSG:3857.
_MERC_SCALE: float = 1.0 / math.cos(math.radians(_SITE_LAT))

# Pixel-grid params: (source, line width, alpha).
# Alpha=1.0 keeps legend and line colours identical; imagery shows through the gaps.
# Line widths follow a 4× ratio per coarseness level (MODIS=4×L8, L8=4×S2).
# Drawn coarsest-first so finer grids sit on top; S2 gets the highest zorder
# to stay fully opaque wherever gridlines intersect.
_GRID_STYLE: List[Tuple] = [
    (SatelliteSource.MODIS,     10, 1.0),  # 4× L8
    (SatelliteSource.LANDSAT8,   4.8, 1.0),  # 4× S2
    (SatelliteSource.SENTINEL2,  1.2, 1.0),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_contextily():
    """Import contextily or raise a clear, actionable ImportError."""
    try:
        import contextily as ctx
        return ctx
    except ImportError:
        raise ImportError(
            "contextily is required for this figure.\n"
            "Install with:  pip install contextily\n"
            "          or:  pip install 'lensky-py-lab[maps]'"
        )


def _to_webmercator(lon: float, lat: float) -> Tuple[float, float]:
    """Convert WGS-84 lon/lat to EPSG:3857 (Web Mercator) x, y in metres."""
    R = 6_378_137.0
    x = math.radians(lon) * R
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R
    return x, y


def _draw_pixel_grid(
    ax: plt.Axes,
    cx: float,
    cy: float,
    px_merc: float,
    half_win: float,
    color: str,
    lw: float,
    alpha: float,
    label: str,
    zorder: int = 4,
) -> mpatches.Patch:
    """Overlay one satellite's pixel grid on *ax* (Web Mercator coords).

    Grid lines are aligned so that the centre pixel straddles the site.
    Returns a legend proxy patch.
    """
    n = int(half_win / px_merc) + 2

    # Pixel boundary positions: the pixel at grid index k spans
    # [centre + (k-0.5)*px, centre + (k+0.5)*px]
    x_bounds = [cx + (k - 0.5) * px_merc for k in range(-n, n + 2)]
    y_bounds = [cy + (k - 0.5) * px_merc for k in range(-n, n + 2)]

    x_lines = [x for x in x_bounds if cx - half_win <= x <= cx + half_win]
    y_lines = [y for y in y_bounds if cy - half_win <= y <= cy + half_win]

    ax.vlines(
        x_lines, cy - half_win, cy + half_win,
        colors=color, linewidths=lw, alpha=alpha, zorder=zorder,
    )
    ax.hlines(
        y_lines, cx - half_win, cx + half_win,
        colors=color, linewidths=lw, alpha=alpha, zorder=zorder,
    )

    # Shade the pixel that contains the site centre
    ax.add_patch(mpatches.Rectangle(
        (cx - px_merc / 2, cy - px_merc / 2), px_merc, px_merc,
        facecolor=color, alpha=0.20, edgecolor="none", zorder=zorder - 1,
    ))

    return mpatches.Patch(
        facecolor=color, alpha=1.0, edgecolor=color, linewidth=1.5,
        label=label,
    )


def _add_scalebar(
    ax: plt.Axes,
    cx: float,
    cy: float,
    half_win: float,
    bar_ground_m: float = 200.0,
) -> None:
    """Draw a map scale bar in the lower-left corner of *ax*."""
    bar_merc = bar_ground_m * _MERC_SCALE
    x0 = cx - half_win + 0.05 * 2 * half_win
    x1 = x0 + bar_merc
    y  = cy - half_win + 0.06 * 2 * half_win
    tick = 0.012 * 2 * half_win

    kw = dict(color="white", linewidth=2, zorder=11, solid_capstyle="butt")
    ax.plot([x0, x1], [y,  y],  **kw)
    ax.plot([x0, x0], [y - tick, y + tick], **kw)
    ax.plot([x1, x1], [y - tick, y + tick], **kw)
    ax.text(
        (x0 + x1) / 2, y + 1.5 * tick,
        f"{int(bar_ground_m)} m",
        ha="center", va="bottom", fontsize=8.5, fontweight="bold",
        color="white", zorder=12,
        bbox=dict(facecolor="black", alpha=0.45, edgecolor="none", pad=1.5),
    )


def _add_basemap(ax: plt.Axes, ctx, satellite: bool = True) -> None:
    """Try satellite imagery first, fall back to OSM Mapnik."""
    if satellite:
        try:
            ctx.add_basemap(
                ax, crs="EPSG:3857",
                source=ctx.providers.Esri.WorldImagery,
                zoom="auto",
            )
            return
        except Exception:
            pass
    ctx.add_basemap(
        ax, crs="EPSG:3857",
        source=ctx.providers.OpenStreetMap.Mapnik,
        zoom="auto",
    )


# ---------------------------------------------------------------------------
# Figure 1 — Site location map
# ---------------------------------------------------------------------------

def plot_site_location(
    lon: float = _SITE_LON,
    lat: float = _SITE_LAT,
    out_dir: Optional[Union[str, Path]] = None,
    stem: str = "site_location",
) -> plt.Figure:
    """Two-panel location figure: Israel OSM overview + satellite local zoom.

    Left panel — OpenStreetMap basemap of Israel with the site marked and a
    red rectangle showing the right-panel extent.

    Right panel — Satellite imagery zoomed to ~6 km around the site, so the
    reader can see the actual landscape (nature reserve, agricultural mosaic).

    Requires ``contextily``::

        pip install contextily   # or   pip install 'lensky-py-lab[maps]'

    Args:
        lon: Site longitude (decimal degrees). Defaults to Ramat HaNadiv.
        lat: Site latitude (decimal degrees). Defaults to Ramat HaNadiv.
        out_dir: Output directory; skips saving when *None*.
        stem: File name stem without extension.

    Returns:
        The matplotlib Figure object.
    """
    ctx = _require_contextily()

    cx, cy = _to_webmercator(lon, lat)

    # ── extents in Web Mercator ──────────────────────────────────────────────
    # Israel overview: ~34°-36.5°E, 29°-34°N
    isr_w, isr_s = _to_webmercator(34.0, 29.0)
    isr_e, isr_n = _to_webmercator(36.5, 34.0)

    # Local zoom: 6 km radius around site
    local_half = 6_000 * _MERC_SCALE
    loc_w, loc_e = cx - local_half, cx + local_half
    loc_s, loc_n = cy - local_half, cy + local_half

    fig, (ax_isr, ax_local) = plt.subplots(1, 2, figsize=(13, 7))

    # ── Left: Israel overview ────────────────────────────────────────────────
    ax_isr.set_xlim(isr_w, isr_e)
    ax_isr.set_ylim(isr_s, isr_n)
    ax_isr.set_aspect("equal")
    ctx.add_basemap(
        ax_isr, crs="EPSG:3857",
        source=ctx.providers.OpenStreetMap.Mapnik,
        zoom="auto",
    )
    # Red rectangle showing local-zoom extent
    ax_isr.add_patch(mpatches.Rectangle(
        (loc_w, loc_s), loc_e - loc_w, loc_n - loc_s,
        fill=False, edgecolor="red", linewidth=2.0, zorder=5,
    ))
    ax_isr.plot(cx, cy, "r*", markersize=12, zorder=6)
    ax_isr.set_axis_off()
    ax_isr.set_title("Israel", fontsize=11, pad=6)

    # ── Right: local satellite zoom ──────────────────────────────────────────
    ax_local.set_xlim(loc_w, loc_e)
    ax_local.set_ylim(loc_s, loc_n)
    ax_local.set_aspect("equal")
    _add_basemap(ax_local, ctx, satellite=True)
    ax_local.plot(cx, cy, "r*", markersize=16, zorder=6)
    ax_local.annotate(
        _SITE_NAME,
        xy=(cx, cy),
        xytext=(cx + 0.25 * local_half, cy + 0.35 * local_half),
        fontsize=10, fontweight="bold", color="white", zorder=7,
        arrowprops=dict(arrowstyle="->", color="white", lw=1.2),
        bbox=dict(facecolor="black", alpha=0.55, edgecolor="none", pad=3),
    )
    _add_scalebar(ax_local, cx, cy, local_half, bar_ground_m=1000)
    ax_local.set_axis_off()
    ax_local.set_title("Research site", fontsize=11, pad=6)

    fig.suptitle(
        f"Research site location — {_SITE_NAME}, Israel",
        fontsize=12, fontweight="bold",
    )
    plt.tight_layout()

    if out_dir is not None:
        save_figure(fig, out_dir, stem)

    return fig


# ---------------------------------------------------------------------------
# Figure 2 — Satellite pixel-size comparison
# ---------------------------------------------------------------------------

def plot_pixel_size_comparison(
    out_dir: Optional[Union[str, Path]] = None,
    stem: str = "pixel_size_comparison",
    window_m: float = 550.0,
) -> plt.Figure:
    """Pixel-grid overlay on satellite imagery — all satellites in one panel.

    Draws MODIS (250 m), Landsat-8 (30 m), and Sentinel-2 (10 m) pixel grids
    simultaneously over a satellite image of the study site, so pixel footprints
    are directly comparable in geographic context.

    Each grid is centred on the site so that the pixel containing the NSRS
    sensor is highlighted.  A 200 m scale bar is included.

    Requires ``contextily``::

        pip install contextily   # or   pip install 'lensky-py-lab[maps]'

    Args:
        out_dir: Output directory; skips saving when *None*.
        stem: File name stem without extension.
        window_m: Ground extent of the map in metres (square, centred on site).
            Default 550 m shows ~2×2 MODIS pixels, keeping L8 and S2 grids legible.

    Returns:
        The matplotlib Figure object.
    """
    ctx = _require_contextily()

    cx, cy = _to_webmercator(_SITE_LON, _SITE_LAT)
    half_win = (window_m / 2) * _MERC_SCALE

    fig, ax = plt.subplots(figsize=(9, 9))
    ax.set_xlim(cx - half_win, cx + half_win)
    ax.set_ylim(cy - half_win, cy + half_win)
    ax.set_aspect("equal")

    # Satellite imagery background
    _add_basemap(ax, ctx, satellite=True)

    # Pixel grids — drawn from coarsest (MODIS) to finest (S2) so fine grids
    # sit on top and remain visible
    legend_handles: List[mpatches.Patch] = []
    for i, (source, lw, alpha) in enumerate(_GRID_STYLE):
        px_m    = SATELLITE_NATIVE_RESOLUTION_M[source]
        px_merc = px_m * _MERC_SCALE
        color   = source_color(source.value)
        label   = f"{source.value}  —  {px_m} m pixel"
        # zorder increases so finer grids sit on top; S2 (last) is always visible
        handle  = _draw_pixel_grid(
            ax, cx, cy, px_merc, half_win, color, lw, alpha, label,
            zorder=4 + i,
        )
        legend_handles.append(handle)

    # Site centre marker
    ax.plot(cx, cy, "r*", markersize=14, zorder=10)
    legend_handles.append(
        plt.Line2D(  # type: ignore[attr-defined]
            [0], [0], marker="*", color="red", markersize=10,
            linestyle="none", label="Site centre (NSRS sensor)",
        )
    )

    _add_scalebar(ax, cx, cy, half_win, bar_ground_m=100)

    ax.set_title(
        f"Satellite pixel-size comparison — {_SITE_NAME}\n"
        f"(window: {int(window_m)} m × {int(window_m)} m)",
        fontsize=11, fontweight="bold",
    )
    ax.set_axis_off()

    leg = ax.legend(
        handles=legend_handles,
        loc="upper right",
        fontsize=9,
        framealpha=0.95,
        edgecolor="#cccccc",
    )
    leg.set_zorder(20)   # above all grid lines
    plt.tight_layout()

    if out_dir is not None:
        save_figure(fig, out_dir, stem)

    return fig
