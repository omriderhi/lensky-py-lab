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


def _is_numeric(val: object) -> bool:
    try:
        float(val)  # type: ignore[arg-type]
        return True
    except (ValueError, TypeError):
        return False
