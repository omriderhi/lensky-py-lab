"""Calendar-window outlier filter (satellite option) and its config plumbing."""
import numpy as np
import pandas as pd
import pytest

from lensky_py_lab import SourceConfig
from lensky_py_lab.constants import NDVI_CLEAN_FIELD, NDVI_FILTERED_FIELD, NDVI_LOWESS_FIELD, NDVI_RAW_FIELD
from lensky_py_lab.pipeline.cleaner import filter_outliers_time_window
from lensky_py_lab.pipeline.processor import process_source


def _frame(values, step_days=5, start="2020-01-01"):
    idx = pd.date_range(start, periods=len(values), freq=f"{step_days}D").astype("int64") // 10**9
    return pd.DataFrame({NDVI_RAW_FIELD: values, NDVI_FILTERED_FIELD: values}, index=idx)


def _cfg(**kw):
    return SourceConfig(outlier_window_days=15, **kw)


def test_low_spike_removed_by_both_directions():
    v = 0.5 + 0.001 * np.arange(60)
    v[30] = 0.1
    out = filter_outliers_time_window(_frame(v), _cfg())[NDVI_CLEAN_FIELD]
    assert np.isnan(out.iloc[30]) and out.drop(out.index[30]).notna().all()


def test_high_spike_kept_when_down_only():
    v = 0.5 + 0.001 * np.arange(60)
    v[30] = 0.9
    both = filter_outliers_time_window(_frame(v), _cfg())[NDVI_CLEAN_FIELD]
    down = filter_outliers_time_window(_frame(v), _cfg(outlier_direction="down"))[NDVI_CLEAN_FIELD]
    assert np.isnan(both.iloc[30])
    assert down.iloc[30] == pytest.approx(0.9)


def test_window_is_in_days_not_observations():
    # same ramp sampled every 5 and every 16 days: a real step is kept at both cadences
    for step in (5, 16):
        v = np.r_[np.full(20, 0.4), np.full(20, 0.7)]
        out = filter_outliers_time_window(_frame(v, step), _cfg())[NDVI_CLEAN_FIELD]
        assert out.notna().all()


def test_none_window_is_passthrough_and_bad_direction_raises():
    df = _frame(0.5 + 0.01 * np.arange(10))
    out = filter_outliers_time_window(df, SourceConfig())[NDVI_CLEAN_FIELD]
    assert out.equals(df[NDVI_FILTERED_FIELD])
    with pytest.raises(ValueError):
        filter_outliers_time_window(df, _cfg(outlier_direction="up"))


def test_from_notebook_dict_and_processor_dispatch():
    cfg = SourceConfig.from_notebook_dict(
        {"outlier_window_days": 15, "outlier_direction": "down", "images_per_month": 5})
    assert (cfg.outlier_window_days, cfg.outlier_direction) == (15, "down")
    v = 0.5 + 0.001 * np.arange(60)
    v[30] = 0.1
    out = process_source(_frame(v), cfg)
    assert np.isnan(out[NDVI_CLEAN_FIELD].iloc[30]) and NDVI_LOWESS_FIELD in out


def test_average_same_date_collapses_pairs_and_config_flag(tmp_path):
    from lensky_py_lab import DataSource
    from lensky_py_lab.io.csv_loader import average_same_date, load_source_csv
    csv = tmp_path / "L8.csv"
    csv.write_text("DATE,NDVI_RAW\n\"Jan 7, 2018\",0.60\n\"Jan 7, 2018\",0.58\n\"Jan 23, 2018\",0.50\n")
    raw = load_source_csv(csv)
    assert len(raw) == 3
    out = average_same_date(raw)
    assert len(out) == 2 and out[NDVI_RAW_FIELD].iloc[0] == pytest.approx(0.59)
    assert len(DataSource.from_csv("L8", csv, SourceConfig()).raw_data) == 3
    assert len(DataSource.from_csv("L8", csv, SourceConfig(average_same_date=True)).raw_data) == 2
    assert SourceConfig.from_notebook_dict({"average_same_date": True}).average_same_date
