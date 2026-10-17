"""Sliding-window outlier filter, config migration and censored end-of-season."""
import numpy as np
import pandas as pd
import pytest

from lensky_py_lab import DataSource, SourceConfig
from lensky_py_lab.constants import NDVI_CLEAN_FIELD, NDVI_FILTERED_FIELD, NDVI_RAW_FIELD
from lensky_py_lab.phenology import extract_phenology
from lensky_py_lab.pipeline.cleaner import filter_outliers_sliding_window


def _frame(values, start="2020-01-01"):
    idx = (pd.date_range(start, periods=len(values), freq="D").astype("int64") // 10**9)
    df = pd.DataFrame({NDVI_RAW_FIELD: values, NDVI_FILTERED_FIELD: values}, index=idx)
    return df


def _cfg(**kw):
    return SourceConfig(outlier_window=7, **kw)


def test_smooth_seasonal_ramp_is_fully_kept():
    # a steep rise through the series mean: the old mean-deviation rule dropped this
    t = np.linspace(0, 1, 120)
    df = _frame(0.3 + 0.4 * np.sin(np.pi * t))
    out = filter_outliers_sliding_window(df, _cfg())
    assert out[NDVI_CLEAN_FIELD].notna().all()


def test_isolated_spike_is_removed_and_neighbours_kept():
    values = 0.4 + 0.001 * np.arange(60)
    values[30] = 0.05
    out = filter_outliers_sliding_window(_frame(values), _cfg())
    clean = out[NDVI_CLEAN_FIELD]
    assert np.isnan(clean.iloc[30])
    assert clean.drop(clean.index[30]).notna().all()


def test_series_edges_are_kept():
    values = 0.4 + 0.002 * np.arange(40)
    clean = filter_outliers_sliding_window(_frame(values), _cfg())[NDVI_CLEAN_FIELD]
    assert clean.iloc[0:3].notna().all() and clean.iloc[-3:].notna().all()


def test_existing_nans_stay_nan_and_short_series_do_not_crash():
    values = np.array([0.4, np.nan, 0.41, 0.42])
    clean = filter_outliers_sliding_window(_frame(values), _cfg())[NDVI_CLEAN_FIELD]
    assert np.isnan(clean.iloc[1]) and clean.iloc[[0, 2, 3]].notna().all()


def test_none_window_copies_filtered_values():
    df = _frame(np.array([0.3, 0.9, 0.31]))
    out = filter_outliers_sliding_window(df, SourceConfig(outlier_window=None))
    assert out[NDVI_CLEAN_FIELD].tolist() == [0.3, 0.9, 0.31]


def test_pipeline_lowess_reaches_end_of_record():
    t = np.linspace(0, 1, 150)
    values = 0.3 + 0.3 * np.sin(np.pi * t)
    ds = DataSource.from_dataframe(
        "NSRS_X", _frame(values)[[NDVI_RAW_FIELD]], SourceConfig(outlier_window=7, images_per_month=30)
    ).process()
    lw = ds.lowess_series.dropna()
    assert lw.index.max() == ds.raw_data.index.max()


def test_average_window_is_rejected_with_a_clear_message():
    with pytest.raises(ValueError, match="outlier_window"):
        SourceConfig.from_notebook_dict({"min": 0.2, "average_window": 0.05, "images_per_month": 30})


def test_notebook_dict_accepts_outlier_window():
    cfg = SourceConfig.from_notebook_dict({"min": 0.2, "outlier_window": 7, "images_per_month": 30})
    assert cfg.outlier_window == 7 and cfg.outlier_k == 3.0


# ── censored end of season ───────────────────────────────────────────────────

def _site_df(end):
    idx = pd.date_range("2020-09-15", end, freq="D")
    doy = np.arange(len(idx))
    vals = 0.3 + 0.4 * np.exp(-((doy - 130) / 55.0) ** 2)
    ts = idx.astype("int64") // 10**9
    return pd.DataFrame({"NDVI lowess X": vals}, index=ts)


def test_eos_is_censored_when_record_ends_before_senescence():
    out = extract_phenology(_site_df("2021-02-20"), site_name="t")
    row = out.iloc[0]
    assert bool(row["EoS_censored"]) is True
    assert pd.isna(row["EoS_date"]) and pd.isna(row["EoS_value"]) and pd.isna(row["EoS_doy"])
    assert pd.notna(row["PoS_date"])


def test_eos_is_reported_when_record_covers_senescence():
    out = extract_phenology(_site_df("2021-08-31"), site_name="t")
    row = out.iloc[0]
    assert bool(row["EoS_censored"]) is False
    assert pd.notna(row["EoS_date"])
