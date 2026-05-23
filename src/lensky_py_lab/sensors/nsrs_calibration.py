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
    - data/results/figures/calibration/NSRS3_calibration_validation.tiff
    - data/results/figures/calibration/NSRS3_calibration_validation.pdf
    - data/results/calibration_statistics.csv

Notes
-----
The NSRS_3 sensor at Ramat Hanadiv uses a wide-angle lens. A slight shift in
sensor pole orientation caused it to capture a portion of the sky alongside
vegetation, suppressing the measured NDVI. The thesis applies a factor of
**1.4** to correct this.

    corrected_NDVI = raw_NDVI × 1.4

This module reproduces the derivation by searching for the factor that
minimizes RMSE between corrected NSRS_3 and the reference signal
(mean of NSRS_1 and NSRS_2).

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

# ---------------------------------------------------------------------------
# Published / thesis calibration constant
# ---------------------------------------------------------------------------

NSRS3_PUBLISHED_FACTOR = 1.4
"""Empirical correction factor reported in the thesis (Derhi, 2025).

The NSRS_3 sensor captured sky reflectance due to a slight pole tilt,
suppressing measured NDVI. Multiplying by 1.4 restores agreement with
NSRS_1 and NSRS_2.
"""


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
        * ``published_factor`` – thesis constant (1.4)
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


def apply_calibration(series: pd.Series, factor: float = NSRS3_PUBLISHED_FACTOR) -> pd.Series:
    """Multiply an NSRS_3 time series by the calibration factor.

    Parameters
    ----------
    series : pd.Series
        Raw NSRS_3 NDVI indexed by unix timestamp.
    factor : float
        Multiplicative correction factor. Defaults to the published value of 1.4.

    Returns
    -------
    pd.Series
        Corrected NDVI series.

    Examples
    --------
    >>> corrected = apply_calibration(nsrs3_raw)
    """
    return (series * factor).rename(str(series.name) + "_corrected")


def create_calibration_figure(
    nsrs3_raw: pd.Series,
    nsrs1: pd.Series,
    nsrs2: pd.Series,
    calibration_result: Optional[Dict] = None,
    output_dir: Path = Path("data/results/figures/calibration"),
    factor: float = NSRS3_PUBLISHED_FACTOR,
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
        Directory where TIFF and PDF figures are saved.
    factor : float
        Factor used for the corrected series (default 1.4, the thesis value).

    Returns
    -------
    matplotlib.figure.Figure

    Notes
    -----
    Uses the publication-quality style from ``plot_config.py``.
    Saved as 300 DPI TIFF and PDF using a colorblind-safe palette.

    Examples
    --------
    >>> fig = create_calibration_figure(nsrs3_raw, nsrs1, nsrs2)
    """
    try:
        from plot_config import apply_publication_style, COLORS
        apply_publication_style()
    except ImportError:
        COLORS = {
            "nsrs1": "#8c564b", "nsrs2": "#e377c2",
            "nsrs3_raw": "#bcbd22", "nsrs3_corrected": "#17becf",
        }

    nsrs3_corrected = apply_calibration(nsrs3_raw, factor)
    reference = _align_mean(nsrs1, nsrs2)

    if calibration_result is None:
        calibration_result = find_optimal_calibration_factor(nsrs3_raw, reference)

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    ax_ts, ax_raw, ax_corr, ax_rmse = axes.flat

    # ------------------------------------------------------------------ #
    # Panel A — Time series
    # ------------------------------------------------------------------ #
    dates = {
        "raw":       pd.to_datetime(nsrs3_raw.index,       unit="s"),
        "corrected": pd.to_datetime(nsrs3_corrected.index,  unit="s"),
        "nsrs1":     pd.to_datetime(nsrs1.index,            unit="s"),
        "nsrs2":     pd.to_datetime(nsrs2.index,            unit="s"),
    }
    ax_ts.plot(dates["nsrs1"],     nsrs1.values,             color=COLORS["nsrs1"],
               label="NSRS_1", linewidth=1.8)
    ax_ts.plot(dates["nsrs2"],     nsrs2.values,             color=COLORS["nsrs2"],
               label="NSRS_2", linewidth=1.8)
    ax_ts.plot(dates["raw"],       nsrs3_raw.values,         color=COLORS["nsrs3_raw"],
               label="NSRS_3 raw", linewidth=1.5, linestyle="--", alpha=0.8)
    ax_ts.plot(dates["corrected"], nsrs3_corrected.values,   color=COLORS["nsrs3_corrected"],
               label=f"NSRS_3 corrected (×{factor})", linewidth=1.8)
    ax_ts.set_title("A — Time Series Comparison")
    ax_ts.set_xlabel("Date")
    ax_ts.set_ylabel("NDVI")
    ax_ts.legend()
    _add_sky_catch_box(ax_ts)

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
                        title=f"C — Corrected NSRS_3 vs Reference (factor={factor})",
                        xlabel="Reference NDVI (mean NSRS_1, NSRS_2)",
                        ylabel="NSRS_3 corrected NDVI")

    # ------------------------------------------------------------------ #
    # Panel D — RMSE curve
    # ------------------------------------------------------------------ #
    rmse_df = calibration_result["rmse_curve"]
    ax_rmse.plot(rmse_df["factor"], rmse_df["rmse"],
                 color="#1f77b4", linewidth=2.0, label="RMSE")
    ax_rmse.axvline(factor, color="#FF0000", linestyle="--", linewidth=1.8,
                    label=f"Chosen factor = {factor}")
    opt = calibration_result["optimal_factor"]
    ax_rmse.axvline(opt, color="#FFA500", linestyle=":", linewidth=1.5,
                    label=f"Optimal factor = {opt:.2f}")
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
    for fmt in ("tiff", "pdf"):
        fig.savefig(output_dir / f"NSRS3_calibration_validation.{fmt}",
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

def _rmse(predicted: np.ndarray, actual: np.ndarray) -> float:
    diff = predicted - actual
    return float(np.sqrt(np.nanmean(diff ** 2)))


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
        ax.plot(x_line, m * x_line + b, color="#d62728", linewidth=1.5, label="Regression")

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
    ax.legend(fontsize=9)
    ax.set_xlim(lo - 0.02, hi + 0.02)
    ax.set_ylim(lo - 0.02, hi + 0.02)


def _add_sky_catch_box(ax: plt.Axes) -> None:
    """Add an explanatory text box about the sky-catch artefact."""
    ax.text(
        0.02, 0.05,
        "NSRS_3 wide-angle lens captured sky reflectance\n"
        "due to sensor pole tilt, suppressing measured NDVI.\n"
        f"Corrected by factor ×{NSRS3_PUBLISHED_FACTOR} (Derhi, 2025).",
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.85, edgecolor="#ccc"),
    )
