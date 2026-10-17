"""Data-sufficiency rules for satellite sources."""
import numpy as np
import pandas as pd

from lensky_py_lab.constants import NDVI_FILTERED_FIELD, NDVI_LOWESS_FIELD
from lensky_py_lab.pipeline.eligibility import (
    EligibilityRules, check_source_eligibility, evaluate_eligibility, reference_window)

T0 = int(pd.Timestamp("2020-01-01").timestamp())
T1 = int(pd.Timestamp("2021-12-31").timestamp())


def _proc(dates, lowess=False):
    idx = pd.DatetimeIndex(dates).astype("int64") // 10**9
    col = NDVI_LOWESS_FIELD if lowess else NDVI_FILTERED_FIELD
    return pd.DataFrame({col: 0.5, NDVI_LOWESS_FIELD: 0.5}, index=idx)


class _Src:
    def __init__(self, df):
        self.processed = df


def test_dense_source_passes_sparse_fails():
    dense = _proc(pd.date_range("2020-01-01", "2021-12-31", freq="10D"))
    sparse = _proc(pd.date_range("2020-01-01", "2021-12-31", freq="40D"))
    assert check_source_eligibility("D", dense, (T0, T1))["eligible"]
    row = check_source_eligibility("S", sparse, (T0, T1))
    assert not row["eligible"] and "valid dates" in row["reasons"]


def test_clustered_dates_fail_month_coverage_even_with_enough_dates():
    d = pd.date_range("2020-01-01", periods=60, freq="D")      # 60 dates in two months
    row = check_source_eligibility("C", _proc(d), (T0, T1))
    assert row["valid_dates_in_window"] == 60 and not row["eligible"]
    assert "month coverage" in row["reasons"]


def test_dates_outside_window_and_nans_do_not_count():
    df = _proc(pd.date_range("2018-01-01", "2019-12-31", freq="5D"))
    assert check_source_eligibility("O", df, (T0, T1))["valid_dates_in_window"] == 0
    df2 = _proc(pd.date_range("2020-01-01", "2021-12-31", freq="5D"))
    df2[NDVI_FILTERED_FIELD] = np.nan
    assert check_source_eligibility("N", df2, (T0, T1))["valid_dates_in_window"] == 0


def test_rules_configurable_and_evaluate_uses_reference_window():
    ref = {"NSRS_1": _Src(_proc(pd.date_range("2020-01-01", "2021-12-31", freq="D"), lowess=True))}
    assert reference_window(ref) == (T0, T1)
    sat = {"A": _Src(_proc(pd.date_range("2020-01-01", "2021-12-31", freq="40D")))}
    assert not evaluate_eligibility(sat, ref).loc[0, "eligible"]
    relaxed = EligibilityRules(min_valid_dates=10, min_month_coverage=0.5, min_peak_season_dates=0)
    assert evaluate_eligibility(sat, ref, relaxed).loc[0, "eligible"]


def test_peak_season_rule_catches_winter_gap_despite_enough_dates_and_months():
    # 45 dates, every month covered, but almost nothing in Dec-Mar of the complete winter 2020/21
    d = [x for x in pd.date_range("2020-01-01", "2021-12-31", freq="5D")
         if not (pd.Timestamp("2020-12-01") <= x <= pd.Timestamp("2021-03-31")) or x.day == 1 and x.month in (1, 3)]
    row = check_source_eligibility("W", _proc(d), (T0, T1), EligibilityRules(min_valid_dates=40, min_month_coverage=0.6))
    assert row["valid_dates_in_window"] >= 40 and row["month_coverage"] >= 0.6
    assert row["min_dates_in_peak_season"] < 5 and not row["eligible"]
    assert "peak season" in row["reasons"]
    assert check_source_eligibility("W", _proc(d), (T0, T1), EligibilityRules(min_peak_season_dates=0))["eligible"]


def test_peak_season_rule_skipped_without_a_complete_winter_in_window():
    short = (int(pd.Timestamp("2020-04-01").timestamp()), int(pd.Timestamp("2020-11-30").timestamp()))
    df = _proc(pd.date_range("2020-04-01", "2020-11-30", freq="2D"))
    row = check_source_eligibility("S", df, short)
    assert row["min_dates_in_peak_season"] is None and row["eligible"]
