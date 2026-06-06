"""
Module: phenolopy_integration.py
Description: Phenological marker extraction (SoS, PoS, EoS) from NDVI time series.
             Implements the seasonal-amplitude method natively using scipy/numpy.
             Also implements the Helman (2015) woody/herbaceous decomposition.
Author: Omri Derhi
Institution: Bar-Ilan University
Date: 2025

Usage:
    from lensky_py_lab.phenology import extract_phenology, decompose_woody_herbaceous

Outputs:
    - data/results/phenology_markers.csv

Notes
-----
The seasonal-amplitude method locates SoS and EoS as the points where NDVI
rises above / falls back below ``base + factor × amplitude``, where:
  - base      = mean of the left and right minima flanking the seasonal peak
  - amplitude = peak_NDVI − base
  - factor    = user-supplied threshold fraction (default 0.2)

SoS is found on the *left* (ascending) side of the peak; EoS on the *right*
(descending) side.  Both are guaranteed to be earlier/later in time than the
peak by construction.

Marker colours used throughout this project:
  - SoS (Start of Season): onset of herbaceous green-up after autumn rain — orange #FF7F00
  - PoS (Peak of Season):  maximum NDVI, typically January — red #E41A1C
  - EoS (End of Season):   dry-season senescence, typically March–April — purple #984EA3

The Helman (2015) method decomposes NDVI into:
  - Woody component   = mean NDVI during June–August (dry season)
  - Herbaceous component = NDVI minus woody baseline

References
----------
Helman, D. et al. (2015). "Soil moisture as a key factor in carbon flux
partitioning in a dryland forest ecosystem". Remote Sensing of Environment.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_phenology(
    site_df: pd.DataFrame,
    source_columns: Optional[List[str]] = None,
    site_name: str = "unnamed",
    factor: float = 0.2,
    output_csv: Optional[Path] = None,
) -> pd.DataFrame:
    """Extract SoS, PoS, EoS for each year and source from a site DataFrame.

    Iterates over each data source column and each hydrological year
    (September Y-1 → August Y) to produce one row of phenology metrics
    per (site, satellite, year) combination.

    Parameters
    ----------
    site_df : pd.DataFrame
        Output of ``Site.run_analysis()`` — timestamp-indexed DataFrame
        with ``'NDVI lowess <source>'`` columns.
    source_columns : list of str, optional
        Subset of ``site_df`` columns to process. Defaults to all
        ``'NDVI lowess'`` columns.
    site_name : str
        Label for the ``site`` column in the output CSV.
    factor : float
        Amplitude fraction threshold (0–1). Lower = earlier SoS/later EoS.
    output_csv : Path, optional
        If provided, save the results DataFrame to this CSV path.

    Returns
    -------
    pd.DataFrame
        Columns: ``[site, satellite, year, SoS_date, PoS_date, EoS_date,
        PoS_value, SoS_doy, PoS_doy, EoS_doy]``

    Notes
    -----
    A hydrological year Y covers September (Y-1) through August Y, matching
    the Mediterranean growing season that straddles the calendar boundary.

    Examples
    --------
    >>> df = site.run_analysis()
    >>> pheno = extract_phenology(df, site_name="RH_NDVI")
    >>> pheno.head()
    """
    if source_columns is None:
        source_columns = [c for c in site_df.columns if c.startswith("NDVI lowess")]

    rows: List[dict] = []
    for col in source_columns:
        series = site_df[col].dropna()
        if series.empty:
            continue
        satellite = col.replace("NDVI lowess ", "").strip()
        years = _hydrological_years(series)
        for year in years:
            year_series = _slice_hydrological_year(series, year)
            if year_series.dropna().shape[0] < 8:
                continue
            result = _extract_markers(year_series, factor)
            if result is None:
                continue
            rows.append({
                "site":      site_name,
                "satellite": satellite,
                "year":      year,
                **result,
            })

    _OUTPUT_COLS = [
        "site", "satellite", "year",
        "SoS_date", "PoS_date", "EoS_date",
        "SoS_value", "PoS_value", "EoS_value",
        "SoS_doy", "PoS_doy", "EoS_doy",
    ]
    if rows:
        out = pd.DataFrame(rows)[_OUTPUT_COLS]
    else:
        out = pd.DataFrame(columns=_OUTPUT_COLS)

    if output_csv is not None:
        Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(output_csv, index=False)

    return out


def decompose_woody_herbaceous(
    series: pd.Series,
    woody_months: Tuple[int, ...] = (6, 7, 8),
    min_dry_seasons: int = 2,
) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
    """Decompose NDVI time series into woody and herbaceous components.

    Implements the Helman (2015) three-step method:

    1. Average NDVI during the dry season (June–August) for each year
       represents the **woody baseline** (herbaceous vegetation is
       dormant in summer).
    2. A linear regression through the annual dry-season averages produces
       a smooth woody trend across the study period.
    3. Subtracting the woody trend from the full time series yields the
       **herbaceous component**.

    Parameters
    ----------
    series : pd.Series
        NDVI time series indexed by unix timestamp (seconds).
        Typically the ``'NDVI lowess <source>'`` column from
        ``Site.run_analysis()``.
    woody_months : tuple of int
        Calendar months considered dry season. Defaults to ``(6, 7, 8)``
        (June, July, August) for Mediterranean sites.
    min_dry_seasons : int
        Minimum number of dry-season annual means required to fit a
        meaningful woody trend. Defaults to ``2``. If fewer are available
        the decomposition is scientifically unreliable and ``(None, None)``
        is returned.

    Returns
    -------
    woody_series : pd.Series or None
        Smooth woody baseline, same index as *series*.
        ``None`` if fewer than *min_dry_seasons* dry seasons are covered.
    herbaceous_series : pd.Series or None
        Herbaceous component (series − woody), same index.
        ``None`` if fewer than *min_dry_seasons* dry seasons are covered.

    Notes
    -----
    Follows Helman et al. (2015). The linear regression through annual
    summer minima is consistent with the thesis implementation using three
    consecutive summer minima (2019, 2020, 2021).

    Examples
    --------
    >>> woody, herb = decompose_woody_herbaceous(site_df["NDVI lowess MODIS"])
    >>> if woody is None:
    ...     print("Insufficient dry seasons — decomposition skipped")
    """
    times = pd.to_datetime(series.index, unit="s")
    df = pd.DataFrame({"ndvi": series.values}, index=times)

    # Step 1: annual dry-season mean
    dry = df[df.index.month.isin(woody_months)]
    annual_woody = dry.groupby(dry.index.year)["ndvi"].mean().dropna()

    if annual_woody.empty:
        warnings.warn(
            f"decompose_woody_herbaceous: '{series.name}' has no dry-season data "
            f"(months {woody_months}) — skipping decomposition."
        )
        return None, None

    if len(annual_woody) < min_dry_seasons:
        warnings.warn(
            f"decompose_woody_herbaceous: '{series.name}' has only "
            f"{len(annual_woody)} dry season(s) — need {min_dry_seasons} "
            f"for a reliable woody trend. Skipping decomposition."
        )
        return None, None

    years = annual_woody.index.values.astype(float)
    vals = annual_woody.values

    # Step 2: linear regression across years for smooth woody trend
    if len(years) >= 2:
        slope, intercept = np.polyfit(years, vals, 1)
        woody_trend = slope * times.year.values.astype(float) + intercept
    else:
        woody_trend = np.full(len(df), vals[0])

    woody_series = pd.Series(
        woody_trend, index=series.index, name=f"{series.name}_woody"
    )
    herbaceous_series = pd.Series(
        series.values - woody_trend,
        index=series.index,
        name=f"{series.name}_herbaceous",
    )
    return woody_series, herbaceous_series


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hydrological_years(series: pd.Series) -> List[int]:
    """Return list of hydrological years present in *series*.

    A hydrological year Y spans Sep (Y-1) through Aug Y.
    """
    times = pd.to_datetime(series.index, unit="s")
    hyd_years = times.year + (times.month >= 9).astype(int)
    return sorted(hyd_years.unique().tolist())


def _slice_hydrological_year(series: pd.Series, year: int) -> pd.Series:
    """Return the slice of *series* covering hydrological year *year*."""
    times = pd.to_datetime(series.index, unit="s")
    mask = (
        (times >= f"{year - 1}-09-01") &
        (times <  f"{year}-09-01")
    )
    return series[np.asarray(mask)]


def _extract_markers(series: pd.Series, factor: float = 0.2) -> Optional[Dict]:
    """Extract SoS, PoS, EoS using the seasonal-amplitude method.

    Interpolates the series to a daily grid, smooths with Savitzky-Golay,
    then locates the peak and the amplitude-threshold crossings on each side.

    SoS and EoS are anchored relative to the peak in *time* (sos_ts < pos_ts
    < eos_ts by construction). Calendar DOY values are derived separately and
    may not follow the same ordering for Mediterranean seasons where the peak
    falls in January (DOY ≈ 15) while SoS falls in autumn (DOY ≈ 280).

    Parameters
    ----------
    series : pd.Series
        NDVI time series indexed by unix timestamps, covering one hydro-year.
    factor : float
        Amplitude fraction (0–1).

    Returns
    -------
    dict or None
        Phenology metrics dict, or None if insufficient data or no clear peak.
    """
    clean = series.dropna()
    if len(clean) < 8:
        return None

    ts_arr = clean.index.to_numpy(dtype=float)
    vals_arr = clean.values.astype(float)

    # Interpolate to daily grid for uniform spacing
    ts_daily = np.arange(ts_arr[0], ts_arr[-1] + 86400, 86400)
    try:
        interp_fn = interp1d(ts_arr, vals_arr, kind="linear", fill_value="extrapolate")
        vals_daily = interp_fn(ts_daily).clip(
            vals_arr.min() - 0.05, vals_arr.max() + 0.05
        )
    except Exception:
        return None

    # Savitzky-Golay smoothing — window ~ 1 month, polynomial order 3
    n = len(vals_daily)
    window = min(31, n)
    if window < 5:
        window = 5
    if window % 2 == 0:
        window -= 1
    try:
        smooth = savgol_filter(vals_daily, window_length=window, polyorder=min(3, window - 1))
    except Exception:
        smooth = vals_daily

    # PoS
    pos_idx = int(np.argmax(smooth))
    pos_value = float(smooth[pos_idx])
    pos_ts = float(ts_daily[pos_idx])

    # Base = mean of left and right minima
    left_min = float(smooth[: pos_idx + 1].min()) if pos_idx > 0 else pos_value
    right_min = float(smooth[pos_idx:].min()) if pos_idx < n - 1 else pos_value
    base_value = (left_min + right_min) / 2.0
    amplitude = pos_value - base_value

    if amplitude <= 0:
        return None

    threshold = base_value + factor * amplitude

    # SoS — leftmost ascending crossing of threshold before the peak
    left_side = smooth[: pos_idx + 1]
    sos_candidates = np.where(left_side >= threshold)[0]
    sos_idx = int(sos_candidates[0]) if len(sos_candidates) > 0 else 0
    sos_ts = float(ts_daily[sos_idx])

    # EoS — rightmost descending crossing of threshold after the peak
    right_side = smooth[pos_idx:]
    eos_candidates = np.where(right_side >= threshold)[0]
    eos_rel_idx = int(eos_candidates[-1]) if len(eos_candidates) > 0 else len(right_side) - 1
    eos_idx = pos_idx + eos_rel_idx
    eos_ts = float(ts_daily[eos_idx])

    def _ts_to_date(ts: float) -> pd.Timestamp:
        return pd.Timestamp(int(ts), unit="s")

    def _ts_to_doy(ts: float) -> int:
        return _ts_to_date(ts).dayofyear

    sos_value = float(interp_fn(sos_ts).clip(vals_arr.min() - 0.05, vals_arr.max() + 0.05))
    eos_value = float(interp_fn(eos_ts).clip(vals_arr.min() - 0.05, vals_arr.max() + 0.05))

    return {
        "SoS_date":  _ts_to_date(sos_ts),
        "PoS_date":  _ts_to_date(pos_ts),
        "EoS_date":  _ts_to_date(eos_ts),
        "SoS_value": sos_value,
        "PoS_value": pos_value,
        "EoS_value": eos_value,
        "SoS_doy":   _ts_to_doy(sos_ts),
        "PoS_doy":   _ts_to_doy(pos_ts),
        "EoS_doy":   _ts_to_doy(eos_ts),
    }


def _doy_to_date(year: int, doy: int) -> pd.Timestamp:
    """Convert year + day-of-year to a Timestamp."""
    try:
        return pd.Timestamp(f"{year}") + pd.Timedelta(days=int(doy) - 1)
    except Exception:
        return pd.NaT
