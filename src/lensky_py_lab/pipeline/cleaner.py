from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from lensky_py_lab.configs import SourceConfig
from lensky_py_lab.constants import (
    NDVI_CLEAN_FIELD,
    NDVI_FILTERED_FIELD,
    NDVI_RAW_FIELD,
)


def filter_extreme_values(df: pd.DataFrame, config: SourceConfig) -> pd.DataFrame:
    """Apply min/max clipping; values outside [min_value, max_value] become NaN.

    If min_value or max_value is None the data's own min/max is used as the bound.
    """
    df = df.copy()
    numeric_values: List[float] = [
        float(v) for v in df[NDVI_RAW_FIELD].dropna()
        if _is_numeric(v)
    ]
    lo = config.min_value if config.min_value is not None else min(numeric_values)
    hi = config.max_value if config.max_value is not None else max(numeric_values)

    filtered: list[Optional[float]] = []
    for val in df[NDVI_RAW_FIELD]:
        try:
            v = float(val)
        except (ValueError, TypeError):
            filtered.append(None)
            continue
        filtered.append(v if lo <= v <= hi else None)

    df[NDVI_FILTERED_FIELD] = filtered
    return df


# Scale factor that makes the median absolute deviation comparable to a
# standard deviation for normally distributed noise.
_MAD_TO_SIGMA = 1.4826


def filter_outliers_sliding_window(df: pd.DataFrame, config: SourceConfig) -> pd.DataFrame:
    """Sliding-window outlier detection on ``NDVI filtered`` → ``NDVI clean``.

    For every observation the reference is the **median** of the centred window
    of ``config.outlier_window`` observations around it (at least 3 at the series
    edges). The point is removed when its residual from that median exceeds

        max(outlier_k × 1.4826 × MAD, outlier_min_threshold)

    where MAD is the median absolute residual over a wider centred window
    (``outlier_scale_window`` observations). The median keeps a spike from
    pulling its own reference, and the MAD-based threshold adapts to how noisy
    that stretch of the series is, so steep rising/falling limbs are not
    mistaken for outliers.

    The window counts *observations*, not days, so it suits dense series (daily
    ground sensors); on sparse series it spans a longer time interval.

    If ``config.outlier_window`` is None the filtered values are copied to
    ``NDVI clean`` unchanged.
    """
    df = df.copy()
    x = pd.to_numeric(df[NDVI_FILTERED_FIELD], errors="coerce")

    if config.outlier_window is None:
        df[NDVI_CLEAN_FIELD] = x
        return df

    obs = x.dropna()
    if obs.empty:
        df[NDVI_CLEAN_FIELD] = x
        return df

    w = int(config.outlier_window)
    scale_w = max(int(config.outlier_scale_window), w)
    med = obs.rolling(w, center=True, min_periods=min(3, w)).median()
    resid = obs - med
    sigma = _MAD_TO_SIGMA * resid.abs().rolling(
        scale_w, center=True, min_periods=min(7, scale_w)
    ).median()
    threshold = np.maximum(config.outlier_k * sigma.fillna(0.0), config.outlier_min_threshold)
    keep = resid.abs() <= threshold

    df[NDVI_CLEAN_FIELD] = obs.where(keep).reindex(df.index)
    return df


_SECONDS_PER_DAY = 86400
# Half-width (days) of the window over which the residual MAD is taken in the
# time-window filter; the observation-window filter uses 31 observations.
_TIME_SCALE_HALF_DAYS = 90


def filter_outliers_time_window(df: pd.DataFrame, config: SourceConfig) -> pd.DataFrame:
    """Calendar-window outlier detection on ``NDVI filtered`` -> ``NDVI clean``.

    Same test as :func:`filter_outliers_sliding_window` (residual from the window
    median against ``max(outlier_k x 1.4826 x MAD, outlier_min_threshold)``), but the
    window is every observation within ``+-config.outlier_window_days`` days, and the
    MAD is taken over ``+-90`` days. A window defined in days covers the same time span
    for daily, 5-day and 16-day series, which an observation count does not.

    With ``config.outlier_direction == "down"`` only points *below* the window median
    are removed: cloud and atmospheric contamination lower NDVI, so a high value next
    to a depressed neighbour is more likely the true signal than an outlier.

    If ``config.outlier_window_days`` is None the filtered values are copied unchanged.
    """
    if config.outlier_direction not in ("both", "down"):
        raise ValueError("outlier_direction must be 'both' or 'down'")
    df = df.copy()
    x = pd.to_numeric(df[NDVI_FILTERED_FIELD], errors="coerce")
    obs = x.dropna()
    if config.outlier_window_days is None or obs.empty:
        df[NDVI_CLEAN_FIELD] = x
        return df

    t = obs.index.values.astype(float)
    v = obs.values
    half = float(config.outlier_window_days) * _SECONDS_PER_DAY
    scale_half = _TIME_SCALE_HALF_DAYS * _SECONDS_PER_DAY
    med = np.array([np.median(v[np.abs(t - ti) <= half]) for ti in t])
    resid = v - med
    sigma = np.array([
        _MAD_TO_SIGMA * np.median(np.abs(resid[np.abs(t - ti) <= scale_half])) for ti in t
    ])
    threshold = np.maximum(config.outlier_k * sigma, config.outlier_min_threshold)
    bad = resid < -threshold if config.outlier_direction == "down" else np.abs(resid) > threshold

    df[NDVI_CLEAN_FIELD] = pd.Series(np.where(bad, np.nan, v), index=obs.index).reindex(df.index)
    return df


def _is_numeric(val: object) -> bool:
    try:
        float(val)  # type: ignore[arg-type]
        return True
    except (ValueError, TypeError):
        return False
