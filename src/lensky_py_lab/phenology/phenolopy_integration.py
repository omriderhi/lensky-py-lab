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
  - SoS (Start of Season): onset of herbaceous green-up after autumn rain — yellow #F0E442
  - PoS (Peak of Season):  maximum NDVI, typically January — vermillion #D55E00
  - EoS (End of Season):   dry-season senescence, typically March–April — sky blue #56B4E9

The Helman (2015) method decomposes NDVI, per seasonal year (Sep–Aug), into:
  - Woody component NDVI_W = mean NDVI during June–August (dry season). Helman
    (2015) also take the wet-season minimum when it is lower (abrupt-loss rule);
    that rule is off by default here (``wet_min_rule=False``), as in Helman &
    Mussery (2020), because at an evergreen site it fires on the normal autumn
    low. The woody series is NDVI_W interpolated linearly between dry seasons
    (``woody_interp="linear"``, default) instead of Helman's yearly steps.
  - Herbaceous / seasonal component NDVI_Seas = NDVI minus NDVI_W; its yearly
    maximum is NDVI_H
The marker extraction above does not depend on the decomposition.

References
----------
Helman, D., Lensky, I. M., Tessler, N., & Osem, Y. (2015). "A phenology-based
method for monitoring woody and herbaceous vegetation in Mediterranean forests
from NDVI time series". Remote Sensing, 7(9), 12314-12335.
doi:10.3390/rs70912314
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
        SoS_value, PoS_value, EoS_value, SoS_doy, PoS_doy, EoS_doy, EoS_censored]``.
        ``EoS_censored`` is True when the record ends before the curve falls below
        the threshold; ``EoS_date`` / ``EoS_value`` / ``EoS_doy`` are then NaT / NaN
        ("end of season not reached") rather than the last day of data.

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
        "SoS_doy", "PoS_doy", "EoS_doy", "EoS_censored",
    ]
    if rows:
        out = pd.DataFrame(rows)[_OUTPUT_COLS]
    else:
        out = pd.DataFrame(columns=_OUTPUT_COLS)

    if output_csv is not None:
        Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(output_csv, index=False)

    return out


def _seasonal_year(times: pd.DatetimeIndex) -> np.ndarray:
    """Seasonal year Y runs September (Y-1) through August Y."""
    return np.asarray(times.year + (times.month >= 9).astype(int))


def _woody_from_table(
    series: pd.Series,
    table: pd.DataFrame,
    woody_interp: str = "linear",
    anchor: Tuple[int, int] = (7, 16),
) -> pd.Series:
    """Woody NDVI at every date of *series* from the per-seasonal-year NDVI_W.

    ``woody_interp="linear"`` (default): each seasonal year's NDVI_W is placed
    at its *anchor* date (month, day; default 16 July, the middle of
    June–August) and the woody series is interpolated linearly between
    successive anchors, so it changes gradually instead of jumping on
    1 September. Before the first and after the last anchor it is held at the
    nearest NDVI_W, but only inside the seasonal years that have an NDVI_W;
    dates outside that span are NaN (nothing is extrapolated beyond them). A
    missing seasonal year between two others is bridged by the interpolation.

    ``woody_interp="step"``: NDVI_W is held constant within its seasonal year
    (Helman et al. 2015 as published); seasonal years without NDVI_W are NaN.
    """
    times = pd.to_datetime(series.index, unit="s")
    sy = _seasonal_year(times)
    if woody_interp == "step":
        return pd.Series(sy, index=series.index).map(table["NDVI_W"]).astype(float)
    if woody_interp != "linear":
        raise ValueError(f"unknown woody_interp {woody_interp!r}; use 'linear' or 'step'")
    years = table.index.to_numpy(dtype=int)
    anchor_t = np.array(
        [pd.Timestamp(year=int(y), month=anchor[0], day=anchor[1]).value // 10 ** 9 for y in years],
        dtype=float,
    )
    w = np.interp(np.asarray(series.index, dtype=float), anchor_t, table["NDVI_W"].to_numpy(dtype=float))
    inside = (sy >= years.min()) & (sy <= years.max())
    return pd.Series(np.where(inside, w, np.nan), index=series.index)


def helman_annual_table(
    series: pd.Series,
    woody_months: Tuple[int, ...] = (6, 7, 8),
    min_dry_obs: int = 2,
    wet_months: Tuple[int, ...] = (10, 11, 12, 1, 2, 3, 4),
    wet_min_rule: bool = False,
    woody_interp: str = "linear",
) -> pd.DataFrame:
    """Per-seasonal-year NDVI_W and NDVI_H, after Helman et al. (2015) Sec. 2.3.

    A seasonal year Y runs September (Y-1) through August Y.

    1. ``NDVI_W`` = mean NDVI over the dry season (*woody_months*, default
       Jun–Aug) of that seasonal year. With ``wet_min_rule=True`` (Helman
       2015 as published), the minimum of the wet-season values
       (*wet_months*, default Oct–Apr) replaces the mean when it is lower, so
       an abrupt loss mid-year (fire, clearing) is not hidden. The rule is off
       by default: on a smoothed series at an evergreen site it fires on the
       normal early-autumn low. Whether it *would* fire is always reported
       (``wet_min_below_mean``).
    2. ``NDVI_Seas`` = NDVI − woody series, where the woody series is NDVI_W
       interpolated between dry seasons (``woody_interp="linear"``, default)
       or held constant within the seasonal year (``"step"``); see
       :func:`decompose_woody_herbaceous`.
    3. ``NDVI_H`` = maximum ``NDVI_Seas`` of the seasonal year.

    Parameters
    ----------
    series : pd.Series
        NDVI indexed by unix timestamp (seconds).
    woody_months : tuple of int
        Calendar months forming the dry season.
    min_dry_obs : int
        Seasonal years with fewer dry-season observations are left out
        (no NDVI_W is reported for them).
    wet_months : tuple of int
        Calendar months searched for the minimum in the abrupt-loss rule
        (and for the ``wet_min`` diagnostic).
    wet_min_rule : bool
        Apply Helman's abrupt-loss rule (default ``False``).
    woody_interp : {"linear", "step"}
        How the woody series used for ``NDVI_H`` is built (default ``"linear"``).

    Returns
    -------
    pd.DataFrame
        Indexed by seasonal year; columns ``NDVI_W``, ``NDVI_H``,
        ``used_min_fallback`` (bool: the rule was applied and changed NDVI_W),
        ``n_dry_obs``, ``dry_mean``, ``wet_min``, ``wet_min_date``,
        ``wet_min_below_mean`` (bool: the rule would fire). Empty if no
        seasonal year qualifies.
    """
    clean = series.dropna()
    times = pd.to_datetime(clean.index, unit="s")
    frame = pd.DataFrame({
        "sy": _seasonal_year(times),
        "t": times,
        "v": clean.to_numpy(dtype=float),
        "dry": np.asarray(times.month.isin(woody_months)),
        "wet": np.asarray(times.month.isin(wet_months)),
    })

    rows = []
    for sy, grp in frame.groupby("sy"):
        dry = grp.loc[grp["dry"], "v"]
        if len(dry) < max(min_dry_obs, 1):
            continue
        dry_mean = float(dry.mean())
        wet = grp.loc[grp["wet"]]
        if len(wet):
            i_min = wet["v"].idxmin()
            wet_min = float(wet.at[i_min, "v"])
            wet_min_date = wet.at[i_min, "t"].strftime("%Y-%m-%d")
        else:
            wet_min, wet_min_date = float("nan"), ""
        below = bool(len(wet) and wet_min < dry_mean)
        fallback = bool(wet_min_rule and below)
        rows.append({
            "seasonal_year": int(sy),
            "NDVI_W": wet_min if fallback else dry_mean,
            "used_min_fallback": fallback,
            "n_dry_obs": int(len(dry)),
            "dry_mean": dry_mean,
            "wet_min": wet_min,
            "wet_min_date": wet_min_date,
            "wet_min_below_mean": below,
        })

    cols = ["NDVI_W", "NDVI_H", "used_min_fallback", "n_dry_obs",
            "dry_mean", "wet_min", "wet_min_date", "wet_min_below_mean"]
    if not rows:
        return pd.DataFrame(columns=cols, index=pd.Index([], name="seasonal_year"))
    table = pd.DataFrame(rows).set_index("seasonal_year")
    woody = _woody_from_table(clean, table, woody_interp)
    seas = pd.Series(frame["v"].to_numpy() - woody.to_numpy(), index=frame["sy"].to_numpy())
    table["NDVI_H"] = seas.groupby(level=0).max().reindex(table.index)
    return table[cols]


def decompose_woody_herbaceous(
    series: pd.Series,
    woody_months: Tuple[int, ...] = (6, 7, 8),
    min_dry_seasons: int = 2,
    min_dry_obs: int = 2,
    method: str = "helman2015",
    wet_months: Tuple[int, ...] = (10, 11, 12, 1, 2, 3, 4),
    wet_min_rule: bool = False,
    woody_interp: str = "linear",
) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
    """Decompose NDVI time series into woody and herbaceous components.

    ``method="helman2015"`` (default) builds on Helman et al. (2015) Sec. 2.3,
    per seasonal year (Sep–Aug):

    1. Woody NDVI (``NDVI_W``) of each seasonal year is the mean NDVI over the
       dry season (June–August), when herbaceous vegetation is dormant.
       Helman's abrupt-loss rule (use the October–April minimum when it is
       lower) is applied only with ``wet_min_rule=True``; it is off by
       default, as in Helman & Mussery (2020).
    2. The woody series is NDVI_W interpolated linearly between successive
       dry seasons (each NDVI_W placed at 16 July), so it changes gradually
       instead of jumping on 1 September (``woody_interp="linear"``, default;
       a slowly varying woody level as in Lu et al. 2003). ``"step"`` holds
       NDVI_W constant within its seasonal year, as Helman (2015) does.
    3. The herbaceous / seasonal component (``NDVI_Seas``) is NDVI minus the
       woody series.

    Dates outside the span of seasonal years that have an NDVI_W (e.g. a
    record that ends in November, after the last dry season) get NaN for both
    components; nothing is extrapolated beyond that span. A seasonal year
    with fewer than *min_dry_obs* dry-season observations gets no NDVI_W. The
    per-year peak ``NDVI_H`` is available from :func:`helman_annual_table`.

    ``method="linear_trend"`` is the earlier repo behaviour, kept only to
    reproduce older results: a linear regression through the calendar-year
    dry-season means. It is not part of Helman (2015).

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
        ``linear_trend`` only: minimum number of annual dry-season means
        needed to fit the trend.
    min_dry_obs : int
        ``helman2015`` only: minimum dry-season observations a seasonal year
        needs to get a woody value. Judgment call (sparse sources such as S2
        have few dates in a summer).
    method : {"helman2015", "linear_trend"}
    wet_months : tuple of int
        ``helman2015`` only: months searched for the abrupt-loss minimum
        (Oct–Apr in the paper).
    wet_min_rule : bool
        ``helman2015`` only: apply the abrupt-loss rule (default ``False``).
    woody_interp : {"linear", "step"}
        ``helman2015`` only: interpolate NDVI_W between dry seasons
        (default) or hold it constant within each seasonal year.

    Returns
    -------
    woody_series : pd.Series or None
        Woody series, same index as *series* (NaN outside the span of
        seasonal years with an NDVI_W). ``None`` if no seasonal year qualifies.
    herbaceous_series : pd.Series or None
        Herbaceous component (series − woody), same index; ``None`` as above.

    Examples
    --------
    >>> woody, herb = decompose_woody_herbaceous(site_df["NDVI lowess MODIS"])
    >>> if woody is None:
    ...     print("Insufficient dry seasons — decomposition skipped")
    """
    if method == "linear_trend":
        return _decompose_linear_trend(series, woody_months, min_dry_seasons)
    if method != "helman2015":
        raise ValueError(f"unknown method {method!r}; use 'helman2015' or 'linear_trend'")

    table = helman_annual_table(series, woody_months, min_dry_obs, wet_months,
                                wet_min_rule, woody_interp)
    if table.empty:
        warnings.warn(
            f"decompose_woody_herbaceous: '{series.name}' has no seasonal year with "
            f">= {min_dry_obs} dry-season observations (months {woody_months}) — "
            "skipping decomposition."
        )
        return None, None

    woody_series = _woody_from_table(series, table, woody_interp).rename(f"{series.name}_woody")
    herbaceous_series = (series - woody_series).rename(f"{series.name}_herbaceous")
    return woody_series, herbaceous_series


def _decompose_linear_trend(
    series: pd.Series,
    woody_months: Tuple[int, ...],
    min_dry_seasons: int,
) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
    """Earlier repo method: linear trend through calendar-year dry-season means."""
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

    The Savitzky-Golay-smoothed curve is used only to *locate* each event
    (peak index, threshold crossings) robustly. The *value* reported for
    every marker is read back from the plain linearly-interpolated curve
    (``interp_fn``) at that timestamp, matching the curve that gets drawn by
    ``dense_interpolate_with_gaps`` in the plotting layer — otherwise PoS
    would be reported from the smoothed curve while SoS/EoS come from the
    unsmoothed one, and the markers would not land on the plotted line.

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

    # PoS — located on the smoothed curve, but its value is read back from
    # the unsmoothed interpolant so it matches the plotted LOWESS curve.
    pos_idx = int(np.argmax(smooth))
    pos_ts = float(ts_daily[pos_idx])

    # Base = mean of left and right minima (on the smoothed curve, used only
    # for locating threshold crossings — not reported as a marker value)
    smooth_pos_value = float(smooth[pos_idx])
    left_min = float(smooth[: pos_idx + 1].min()) if pos_idx > 0 else smooth_pos_value
    right_min = float(smooth[pos_idx:].min()) if pos_idx < n - 1 else smooth_pos_value
    base_value = (left_min + right_min) / 2.0
    amplitude = smooth_pos_value - base_value

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
    # The curve is still above the threshold on the last day of data: the record
    # ends before senescence does, so no EoS can be reported (right-censored).
    eos_censored = eos_idx >= n - 2

    def _ts_to_date(ts: float) -> pd.Timestamp:
        return pd.Timestamp(int(ts), unit="s")

    def _ts_to_doy(ts: float) -> int:
        return _ts_to_date(ts).dayofyear

    def _value_at(ts: float) -> float:
        return float(interp_fn(ts).clip(vals_arr.min() - 0.05, vals_arr.max() + 0.05))

    sos_value = _value_at(sos_ts)
    pos_value = _value_at(pos_ts)
    eos_value = _value_at(eos_ts)

    if eos_censored:
        return {
            "SoS_date":  _ts_to_date(sos_ts),
            "PoS_date":  _ts_to_date(pos_ts),
            "EoS_date":  pd.NaT,
            "SoS_value": sos_value,
            "PoS_value": pos_value,
            "EoS_value": np.nan,
            "SoS_doy":   _ts_to_doy(sos_ts),
            "PoS_doy":   _ts_to_doy(pos_ts),
            "EoS_doy":   np.nan,
            "EoS_censored": True,
        }

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
        "EoS_censored": False,
    }


def _doy_to_date(year: int, doy: int) -> pd.Timestamp:
    """Convert year + day-of-year to a Timestamp."""
    try:
        return pd.Timestamp(f"{year}") + pd.Timedelta(days=int(doy) - 1)
    except Exception:
        return pd.NaT
