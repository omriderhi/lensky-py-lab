from __future__ import annotations

from typing import List, Optional

import pandas as pd

from lensky_py_lab.configs import SourceConfig
from lensky_py_lab.constants import (
    AVERAGE_GROUP_SIZE,
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


def filter_by_average_groups(
    df: pd.DataFrame,
    config: SourceConfig,
    group_size: int = AVERAGE_GROUP_SIZE,
) -> pd.DataFrame:
    """Outlier-emphasis filter from the original research pipeline.

    Retains a value when its absolute deviation from the **global** mean of all
    filtered values is >= average_window; discards it otherwise.

    This matches the notebook's actual (accidental) behaviour: the original loop
    used a Unix timestamp as the positional variable ``i``, so ``i - i - 3``
    always evaluated to ``-3`` (clamped to index 1) and ``i + 3`` always exceeded
    ``len(df)`` (clamped to len), making the "local window" span the entire
    series.  The effective reference was therefore the global series mean, not a
    ±3-row neighbourhood.  Using a true local window was significantly more
    aggressive and produced far fewer surviving points than expected.

    If average_window is None, NDVI_FILTERED_FIELD is copied to NDVI_CLEAN_FIELD
    without modification.
    """
    df = df.copy()

    if config.average_window is None:
        df[NDVI_CLEAN_FIELD] = df[NDVI_FILTERED_FIELD]
        return df

    filtered_values: List[Optional[float]] = list(df[NDVI_FILTERED_FIELD])
    non_null = [v for v in filtered_values if v is not None and not (isinstance(v, float) and pd.isna(v))]

    if not non_null:
        df[NDVI_CLEAN_FIELD] = [None] * len(filtered_values)
        return df

    global_mean = sum(non_null) / len(non_null)
    clean: list[Optional[float]] = []

    for val in filtered_values:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            clean.append(None)
            continue
        if abs(global_mean - float(val)) >= config.average_window:
            clean.append(float(val))
        else:
            clean.append(None)

    df[NDVI_CLEAN_FIELD] = clean
    return df


def _is_numeric(val: object) -> bool:
    try:
        float(val)  # type: ignore[arg-type]
        return True
    except (ValueError, TypeError):
        return False
