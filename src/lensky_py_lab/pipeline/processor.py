from __future__ import annotations

import pandas as pd

from lensky_py_lab.configs import SourceConfig
from lensky_py_lab.pipeline.cleaner import (
    filter_extreme_values,
    filter_outliers_sliding_window,
    filter_outliers_time_window,
)
from lensky_py_lab.pipeline.smoother import add_lowess


def process_source(df: pd.DataFrame, config: SourceConfig) -> pd.DataFrame:
    """Run the full cleaning pipeline: extreme filter → outlier filter → LOWESS.

    The outlier filter is the calendar-window one when ``config.outlier_window_days``
    is set, otherwise the observation-window one.
    """
    df = filter_extreme_values(df, config)
    if config.outlier_window_days is not None:
        df = filter_outliers_time_window(df, config)
    else:
        df = filter_outliers_sliding_window(df, config)
    df = add_lowess(df, config)
    return df


def merge_processed(
    primary_df: pd.DataFrame,
    backup_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge two processed DataFrames for a unified cleaning-pipeline figure.

    Primary timestamps are kept as-is; backup contributes only at timestamps
    not already present in primary. The result is sorted by index so the plotter
    sees a single time series with a natural gap between the two deployment periods.
    """
    extra = backup_df.index.difference(primary_df.index)
    return pd.concat([primary_df, backup_df.loc[extra]]).sort_index()
