"""
Script: nsrs_calibration.py
Description: NSRS_3 sensor calibration — derives and validates the empirical
             correction factor for the wide-angle sky-contamination bias.
             Produces the 4-panel calibration figure for thesis Section 3.
Author: Omri Derhi
Institution: Bar-Ilan University
Date: 2025

Usage:
    from lensky_py_lab.sensors.nsrs_calibration import (
        find_optimal_calibration_factor,
        apply_calibration,
        create_calibration_figure,
    )

Outputs:
    - data/results/figures/calibration/NSRS3_calibration_validation.png
    - data/results/calibration_statistics.csv

Notes
-----
The NSRS_3 sensor at Ramat Hanadiv uses a wide-angle lens. A slight shift in
sensor pole orientation caused it to capture a portion of the sky alongside
vegetation, suppressing the measured NDVI.

    corrected_NDVI = raw_NDVI × factor

The factor is derived from the data: it is the value that minimizes RMSE
between corrected NSRS_3 and the reference signal (mean of NSRS_1 and NSRS_2).
The thesis reports 1.4 (``NSRS3_PUBLISHED_FACTOR``), kept only for comparison.

Dependencies:
    - numpy, pandas, matplotlib, scipy
    - plot_config.py (shared figure style)
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Dict, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

from lensky_py_lab.constants import NDVI_LOWESS_FIELD
from lensky_py_lab.gap_utils import boundaries_from_raw, iter_segments_from_boundaries
from lensky_py_lab.metrics import rmse as _rmse

# ---------------------------------------------------------------------------
# Thesis reference value (comparison only — never applied to data)
# ---------------------------------------------------------------------------

NSRS3_PUBLISHED_FACTOR = 1.4
"""Correction factor reported in the thesis (Derhi, 2025), kept for comparison.

The factor actually applied is derived from the data by
:func:`calibrate_nsrs3_sources` and held by :func:`get_active_factor`.
"""

# ---------------------------------------------------------------------------
# Active (data-derived) factor — set once per run
# ---------------------------------------------------------------------------

_active_factor: Optional[float] = None


def set_active_factor(factor: float) -> None:
    """Register the data-derived NSRS_3 factor for the rest of the run."""
    global _active_factor
    _active_factor = float(factor)


def get_active_factor() -> Optional[float]:
    """Return the registered NSRS_3 factor, or *None* if calibration is not in use."""
    return _active_factor


def clear_active_factor() -> None:
    """Forget any registered factor, so a new run starts uncalibrated."""
    global _active_factor
    _active_factor = None


# ---------------------------------------------------------------------------
# Core calibration functions
# ---------------------------------------------------------------------------

def find_optimal_calibration_factor(
    nsrs3_raw: pd.Series,
    reference: pd.Series,
    factor_min: float = 0.5,
    factor_max: float = 2.5,
    n_steps: int = 200,
) -> Dict:
    """Find the multiplicative factor that best aligns NSRS_3 with a reference.

    Searches a grid of candidate factors and selects the one that minimises
    RMSE between ``nsrs3_raw × factor`` and ``reference`` on overlapping
    timestamps.

    Parameters
    ----------
    nsrs3_raw : pd.Series
        Raw (uncorrected) NSRS_3 NDVI time series indexed by unix timestamp.
    reference : pd.Series
        Reference NDVI — typically the mean of NSRS_1 and NSRS_2, same index.
    factor_min : float
        Lower bound of the search range.
    factor_max : float
        Upper bound of the search range.
    n_steps : int
        Number of candidate factors to evaluate.

    Returns
    -------
    dict
        Keys:

        * ``optimal_factor``  – factor minimising RMSE
        * ``published_factor`` – thesis value (1.4), for comparison only
        * ``published_factor_rmse`` – RMSE at the thesis factor
        * ``rmse_curve``  – DataFrame with ``factor`` and ``rmse`` columns
        * ``r2_raw``      – Pearson R² before calibration
        * ``rmse_raw``    – RMSE before calibration
        * ``r2_corrected``   – Pearson R² using optimal factor
        * ``rmse_corrected`` – RMSE using optimal factor
        * ``n_overlap``      – number of matched timestamps

    Notes
    -----
    Follows Helman (2015) and thesis Section 3.3. The result should
    confirm the published factor of 1.4 is near-optimal.

    Examples
    --------
    >>> result = find_optimal_calibration_factor(nsrs3, reference)
    >>> print(result["optimal_factor"])
    1.41
    """
    # Align on shared timestamps
    df = pd.DataFrame({"raw": nsrs3_raw, "ref": reference}).dropna()
    if df.empty:
        raise ValueError("No overlapping non-NaN timestamps between NSRS_3 and reference.")

    raw = df["raw"].values
    ref = df["ref"].values
    n = len(df)

    factors = np.linspace(factor_min, factor_max, n_steps)
    rmse_values = np.array([
        _rmse(raw * f, ref) for f in factors
    ])

    opt_idx = int(np.argmin(rmse_values))
    optimal_factor = float(factors[opt_idx])

    r2_raw, rmse_raw = _pearson_r2(raw, ref), _rmse(raw, ref)
    corrected_opt = raw * optimal_factor
    r2_corrected = _pearson_r2(corrected_opt, ref)
    rmse_corrected = float(rmse_values[opt_idx])

    published_rmse = _rmse(raw * NSRS3_PUBLISHED_FACTOR, ref)

    return {
        "optimal_factor":       optimal_factor,
        "published_factor":     NSRS3_PUBLISHED_FACTOR,
        "published_factor_rmse": float(published_rmse),
        "rmse_curve":           pd.DataFrame({"factor": factors, "rmse": rmse_values}),
        "r2_raw":               r2_raw,
        "rmse_raw":             float(rmse_raw),
        "r2_corrected":         r2_corrected,
        "rmse_corrected":       rmse_corrected,
        "n_overlap":            n,
    }


def apply_calibration(series: pd.Series, factor: Optional[float] = None) -> pd.Series:
    """Multiply an NSRS_3 time series by the calibration factor.

    Parameters
    ----------
    series : pd.Series
        Raw NSRS_3 NDVI indexed by unix timestamp.
    factor : float, optional
        Multiplicative correction factor. Defaults to the data-derived factor
        registered by :func:`calibrate_nsrs3_sources`; raises if none exists.

    Returns
    -------
    pd.Series
        Corrected NDVI series.

    Examples
    --------
    >>> corrected = apply_calibration(nsrs3_raw, factor=1.36)
    """
    if factor is None:
        factor = get_active_factor()
    if factor is None:
        raise ValueError(
            "No calibration factor: pass factor= or run calibrate_nsrs3_sources() first."
        )
    return (series * factor).rename(str(series.name) + "_corrected")


_FACTOR_ATTR = "nsrs3_factor"


def apply_nsrs3_factor(
    nsrs_sources: Dict,
    factor: float,
    nsrs3_names: Tuple[str, ...] = ("NSRS_3", "NSRS_3_B"),
) -> None:
    """Multiply *factor* into the LOWESS column of the NSRS_3 sources and register it.

    Calibration is optional: skip this (and :func:`calibrate_nsrs3_sources`) to leave
    NSRS_3 uncalibrated. Applying twice would silently double-scale, so a source that
    was already calibrated raises ``ValueError``.
    """
    targets = [nsrs_sources[n] for n in nsrs3_names if n in nsrs_sources]
    if any(_FACTOR_ATTR in src.processed.attrs for src in targets):
        raise ValueError("NSRS_3 sources are already calibrated; refusing to scale twice.")
    for src in targets:
        src.processed[NDVI_LOWESS_FIELD] = src.processed[NDVI_LOWESS_FIELD] * factor
        src.processed.attrs[_FACTOR_ATTR] = float(factor)
    set_active_factor(factor)


def calibrate_nsrs3_sources(
    nsrs_sources: Dict,
    nsrs3_names: Tuple[str, ...] = ("NSRS_3", "NSRS_3_B"),
) -> Tuple[Dict, pd.Series]:
    """Derive the NSRS_3 factor from the data and apply it to the NSRS_3 sources.

    Optional step: nothing in the package requires it. The sources must be
    processed *without* a ``general_factor``. The raw
    (unscaled) merged NSRS_3 LOWESS series is compared with the mean of NSRS_1
    and NSRS_2; the RMSE-minimising factor is multiplied into the LOWESS column
    of every NSRS_3 source and registered via :func:`set_active_factor`.

    Returns
    -------
    (dict, pd.Series)
        The result of :func:`find_optimal_calibration_factor` and the unscaled
        merged NSRS_3 series (for validation figures).
    """
    from lensky_py_lab.models.site import Site

    site_df = Site(name="nsrs3_calibration", nsrs_sources=nsrs_sources).run_analysis()
    cols = {n: f"{NDVI_LOWESS_FIELD} {n}" for n in ("NSRS_1", "NSRS_2", "NSRS_3")}
    missing = [c for c in cols.values() if c not in site_df.columns]
    if missing:
        raise ValueError(f"Cannot derive NSRS_3 factor — missing columns: {missing}")

    nsrs3_raw = site_df[cols["NSRS_3"]].dropna().rename("NSRS_3_raw")
    reference = _align_mean(site_df[cols["NSRS_1"]].dropna(), site_df[cols["NSRS_2"]].dropna())
    result = find_optimal_calibration_factor(nsrs3_raw, reference)
    factor = result["optimal_factor"]

    apply_nsrs3_factor(nsrs_sources, factor, nsrs3_names)
    return result, nsrs3_raw


def create_calibration_figure(
    nsrs3_raw: pd.Series,
    nsrs1: pd.Series,
    nsrs2: pd.Series,
    calibration_result: Optional[Dict] = None,
    output_dir: Path = Path("data/results/figures/calibration"),
    factor: Optional[float] = None,
) -> plt.Figure:
    """Create the 4-panel NSRS_3 calibration validation figure.

    Panel A — Time series: NSRS_3 raw, NSRS_3 corrected, NSRS_1, NSRS_2.
    Panel B — Scatter: raw NSRS_3 vs reference mean (should be offset below 1:1).
    Panel C — Scatter: corrected NSRS_3 vs reference mean (should align on 1:1).
    Panel D — RMSE curve across candidate factors with the chosen factor marked.

    Parameters
    ----------
    nsrs3_raw : pd.Series
        Uncorrected NSRS_3 NDVI indexed by unix timestamp.
    nsrs1 : pd.Series
        NSRS_1 NDVI indexed by unix timestamp.
    nsrs2 : pd.Series
        NSRS_2 NDVI indexed by unix timestamp.
    calibration_result : dict, optional
        Output of :func:`find_optimal_calibration_factor`. Computed
        automatically if not supplied.
    output_dir : Path
        Directory where PNG figures are saved.
    factor : float, optional
        Factor used for the corrected series. Defaults to the optimal factor
        in ``calibration_result``.

    Returns
    -------
    matplotlib.figure.Figure

    Notes
    -----
    Uses the publication-quality style from ``plot_config.py``.
    Saved as 300 DPI PNG using a colorblind-safe palette.

    Examples
    --------
    >>> fig = create_calibration_figure(nsrs3_raw, nsrs1, nsrs2)
    """
    try:
        from plot_config import apply_publication_style, COLORS
        apply_publication_style()
    except ImportError:
        COLORS = {
            "nsrs1": "#5BAA3C", "nsrs2": "#6B3E1A",
            "nsrs3_raw": "#999999", "nsrs3_corrected": "#7D7226",
        }

    reference = _align_mean(nsrs1, nsrs2)

    if calibration_result is None:
        calibration_result = find_optimal_calibration_factor(nsrs3_raw, reference)
    if factor is None:
        factor = calibration_result["optimal_factor"]
    factor = float(factor)
    nsrs3_corrected = apply_calibration(nsrs3_raw, factor)

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    ax_ts, ax_raw, ax_corr, ax_rmse = axes.flat

    # ------------------------------------------------------------------ #
    # Panel A — Time series
    # ------------------------------------------------------------------ #
    # Break lines at wide data gaps (same 60-day rule as every other time-series
    # figure) instead of drawing straight lines across missing seasons. The
    # observations themselves are plotted, not resampled. Raw and corrected NSRS_3
    # share one set of segment boundaries so they always break at the same place.
    nsrs3_bounds = _segment_boundaries(nsrs3_raw)

    for series, bounds, key, label, extra in (
        (nsrs1, None, "nsrs1", "NSRS_1", {}),
        (nsrs2, None, "nsrs2", "NSRS_2", {}),
        (nsrs3_raw, nsrs3_bounds, "nsrs3_raw", "NSRS_3 raw", {"alpha": 0.85}),
        (nsrs3_corrected, nsrs3_bounds, "nsrs3_corrected",
         f"NSRS_3 corrected (×{factor:.3f})", {}),
    ):
        d, v = _gapped_xy(series, bounds)
        ax_ts.plot(d, v, color=COLORS[key], label=label, linewidth=1.8, **extra)
    ax_ts.set_title("A — Time Series Comparison")
    ax_ts.set_xlabel("Date")
    ax_ts.set_ylabel("NDVI")
    # Headroom above the data so the (large) legend never covers a curve
    y_lo, y_hi = ax_ts.get_ylim()
    ax_ts.set_ylim(y_lo, y_hi + 0.3 * (y_hi - y_lo))
    ax_ts.legend(loc="upper center", ncol=2)
    _add_sky_catch_box(ax_ts, factor)

    # ------------------------------------------------------------------ #
    # Panel B — Scatter: raw vs reference
    # ------------------------------------------------------------------ #
    df_raw = pd.DataFrame({"x": reference, "y": nsrs3_raw}).dropna()
    _scatter_with_stats(ax_raw, df_raw["x"], df_raw["y"],
                        color=COLORS["nsrs3_raw"],
                        title="B — Raw NSRS_3 vs Reference",
                        xlabel="Reference NDVI (mean NSRS_1, NSRS_2)",
                        ylabel="NSRS_3 raw NDVI")

    # ------------------------------------------------------------------ #
    # Panel C — Scatter: corrected vs reference
    # ------------------------------------------------------------------ #
    df_corr = pd.DataFrame({"x": reference, "y": nsrs3_corrected}).dropna()
    _scatter_with_stats(ax_corr, df_corr["x"], df_corr["y"],
                        color=COLORS["nsrs3_corrected"],
                        title=f"C — Corrected NSRS_3 vs Reference (factor={factor:.3f})",
                        xlabel="Reference NDVI (mean NSRS_1, NSRS_2)",
                        ylabel="NSRS_3 corrected NDVI")

    # ------------------------------------------------------------------ #
    # Panel D — RMSE curve
    # ------------------------------------------------------------------ #
    rmse_df = calibration_result["rmse_curve"]
    ax_rmse.plot(rmse_df["factor"], rmse_df["rmse"],
                 color=COLORS["nsrs3_corrected"], linewidth=2.0, label="RMSE")
    ax_rmse.axvline(factor, color=COLORS["nsrs1"], linestyle="--", linewidth=1.8,
                    label=f"Applied factor = {factor:.3f}")
    opt = calibration_result["optimal_factor"]
    ax_rmse.axvline(opt, color=COLORS["nsrs2"], linestyle=":", linewidth=1.5,
                    label=f"Optimal factor = {opt:.3f}")
    ax_rmse.set_title("D — RMSE vs Correction Factor")
    ax_rmse.set_xlabel("Correction factor")
    ax_rmse.set_ylabel("RMSE")
    ax_rmse.legend()

    fig.suptitle(
        "NSRS_3 Sensor Calibration Validation — Ramat Hanadiv",
        fontsize=16, fontweight="bold",
    )
    fig.tight_layout()

    # Save
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / "NSRS3_calibration_validation.png",
                dpi=300, bbox_inches="tight")

    return fig


def save_calibration_statistics(
    calibration_result: Dict,
    output_path: Path = Path("data/results/calibration_statistics.csv"),
) -> pd.DataFrame:
    """Save calibration metrics to CSV.

    Parameters
    ----------
    calibration_result : dict
        Output of :func:`find_optimal_calibration_factor`.
    output_path : Path
        Destination CSV file.

    Returns
    -------
    pd.DataFrame
        Single-row summary statistics table.
    """
    row = {k: v for k, v in calibration_result.items() if k != "rmse_curve"}
    df = pd.DataFrame([row])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _segment_boundaries(series: pd.Series):
    """(start, end) unix-second windows of continuous coverage (60-day gap rule)."""
    s = series.dropna()
    return boundaries_from_raw(s.index.values.astype(np.int64), s.values.astype(float))


def _gapped_xy(series: pd.Series, boundaries=None):
    """Dates and values of *series* with a NaN pen-lift between coverage segments.

    Original observations are kept as-is (no resampling). Pass *boundaries* to
    reuse another series' segmentation; by default they come from *series* itself.
    """
    s = series.dropna()
    ts = s.index.values.astype(np.int64)
    vals = s.values.astype(float)
    if boundaries is None:
        boundaries = boundaries_from_raw(ts, vals)
    xs, ys = [], []
    for i, (t, v) in enumerate(iter_segments_from_boundaries(ts, vals, boundaries)):
        if i:
            xs.append(np.array([(xs[-1][-1] + t[0]) / 2.0]))
            ys.append(np.array([np.nan]))
        xs.append(t.astype(float))
        ys.append(v)
    if not xs:
        return pd.to_datetime(np.array([], dtype=np.int64), unit="s"), np.array([])
    return pd.to_datetime(np.concatenate(xs).astype(np.int64), unit="s"), np.concatenate(ys)


def _pearson_r2(x: np.ndarray, y: np.ndarray) -> float:
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 3:
        return float("nan")
    r, _ = pearsonr(x[mask], y[mask])
    return float(r ** 2)


def _align_mean(*series: pd.Series) -> pd.Series:
    """Return the mean of two or more time series on their shared index."""
    df = pd.concat(series, axis=1).dropna()
    return df.mean(axis=1)


def _scatter_with_stats(
    ax: plt.Axes,
    x: pd.Series,
    y: pd.Series,
    color: str,
    title: str,
    xlabel: str,
    ylabel: str,
) -> None:
    """Draw scatter plot with 1:1 line, regression line, R² and RMSE."""
    ax.scatter(x, y, color=color, alpha=0.5, s=25, edgecolors="none", label="Observations")
    lo = min(x.min(), y.min())
    hi = max(x.max(), y.max())
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=1.2, label="1:1 line")

    # Regression line
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() >= 3:
        m, b = np.polyfit(x[mask], y[mask], 1)
        x_line = np.linspace(lo, hi, 100)
        ax.plot(x_line, m * x_line + b, color="#D55E00", linewidth=1.5, label="Regression")

        r2 = _pearson_r2(x.values, y.values)
        rmse = _rmse(y.values, x.values)
        ax.text(
            0.05, 0.92,
            f"R² = {r2:.3f}\nRMSE = {rmse:.4f}",
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend(fontsize=plt.rcParams["legend.fontsize"])
    ax.set_xlim(lo - 0.02, hi + 0.02)
    ax.set_ylim(lo - 0.02, hi + 0.02)


def _add_sky_catch_box(ax: plt.Axes, factor: float) -> None:
    """Add an explanatory text box about the sky-catch artefact."""
    ax.text(
        0.02, 0.05,
        "NSRS_3 wide-angle lens captured sky reflectance\n"
        "due to sensor pole tilt, suppressing measured NDVI.\n"
        f"Corrected by data-derived factor ×{factor:.3f}.",
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.85, edgecolor="#ccc"),
    )
