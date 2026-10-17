from __future__ import annotations

import pandas as pd

from lensky_py_lab.configs import SourceConfig
from lensky_py_lab.pipeline.cleaner import filter_extreme_values, filter_outliers_sliding_window
from lensky_py_lab.pipeline.smoother import add_lowess


def process_source(df: pd.DataFrame, config: SourceConfig) -> pd.DataFrame:
    """Run the full cleaning pipeline: extreme filter → sliding-window outlier filter → LOWESS."""
    df = filter_extreme_values(df, config)
    df = filter_outliers_sliding_window(df, config)
    df = add_lowess(df, config)
    return df
