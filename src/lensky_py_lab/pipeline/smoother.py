from __future__ import annotations

import pandas as pd
import statsmodels.api as sm

from lensky_py_lab.configs import SourceConfig
from lensky_py_lab.constants import NDVI_CLEAN_FIELD, NDVI_LOWESS_FIELD, TIMESTAMP_FIELD


def add_lowess(df: pd.DataFrame, config: SourceConfig) -> pd.DataFrame:
    """Apply LOWESS smoothing to NDVI_CLEAN_FIELD and add NDVI_LOWESS_FIELD.

    Smoothing bandwidth: frac = images_per_month / N_non_null_points.
    If general_factor is set, the smoothed values are multiplied by it afterward.
    If images_per_month is None, NDVI_CLEAN_FIELD is copied to NDVI_LOWESS_FIELD unchanged.
    """
    df = df.copy()

    if config.images_per_month is None:
        df[NDVI_LOWESS_FIELD] = df[NDVI_CLEAN_FIELD]
        return df

    clean_df = df.dropna(subset=[NDVI_CLEAN_FIELD])
    if clean_df.empty:
        df[NDVI_LOWESS_FIELD] = None
        return df

    n = len(clean_df)
    x = clean_df.index.tolist()
    y = clean_df[NDVI_CLEAN_FIELD].tolist()
    frac = float(config.images_per_month) / n
    frac = min(max(frac, 1e-4), 1.0)

    lowess_result = sm.nonparametric.lowess(y, x, frac=frac)
    ts_list = [int(row[0]) for row in lowess_result]
    ndvi_list = [row[1] for row in lowess_result]

    if config.general_factor is not None:
        ndvi_list = [v * config.general_factor for v in ndvi_list]

    lowess_df = pd.DataFrame(
        {NDVI_LOWESS_FIELD: ndvi_list},
        index=pd.Index(ts_list, name=df.index.name),
    )
    return df.join(lowess_df, how="left")
