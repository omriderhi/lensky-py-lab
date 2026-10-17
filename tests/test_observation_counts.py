"""Observations per sensor per month (Table S1)."""
from datetime import datetime

import pandas as pd
import pytest

from lensky_py_lab.constants import (
    DATE_FIELD, NDVI_CLEAN_FIELD, NDVI_FILTERED_FIELD, NDVI_LOWESS_FIELD)
from lensky_py_lab.pipeline.observation_counts import observations_per_month

W0 = int(datetime(2019, 10, 1).timestamp())
W1 = int(datetime(2021, 3, 31, 23, 59, 59).timestamp())


class _Src:
    def __init__(self, df):
        self.processed = df


def _src(dates, clean=0.5, filtered=0.5, utc_shift_hours=0):
    d = pd.DatetimeIndex(dates)
    idx = [int(x.to_pydatetime().timestamp()) - utc_shift_hours * 3600 for x in d]
    return _Src(pd.DataFrame({
        DATE_FIELD: d, NDVI_CLEAN_FIELD: clean, NDVI_FILTERED_FIELD: filtered,
        NDVI_LOWESS_FIELD: 0.5}, index=idx))


def _cell(tbl, month, col):
    return int(tbl.loc[tbl["month"] == month, col].iloc[0])


def test_month_comes_from_date_not_timestamp():
    # first of March, but the timestamp is 21:00 UTC on 29 Feb
    tbl = observations_per_month({"MODIS": _src(["2020-03-01"], utc_shift_hours=3)}, (W0, W1), order=("MODIS",))
    assert _cell(tbl, "2020-03", "MODIS") == 1 and _cell(tbl, "2020-02", "MODIS") == 0


def test_backup_file_merged_one_sensor():
    src = {"NSRS_1": _src(["2020-01-01", "2020-01-02"]), "NSRS_1_B": _src(["2020-01-02", "2020-01-03"])}
    tbl = observations_per_month(src, (W0, W1), order=("NSRS_1",))
    assert list(tbl.columns) == ["month", "NSRS_1"]
    assert _cell(tbl, "Total", "NSRS_1") == 3


def test_same_date_counts_once():
    tbl = observations_per_month({"S2": _src(["2020-01-05", "2020-01-05"])}, (W0, W1), order=("S2",))
    assert _cell(tbl, "2020-01", "S2") == 1


def test_null_clean_counts_only_for_filtered_field():
    src = {"S2": _src(["2020-01-05"], clean=float("nan"))}
    assert _cell(observations_per_month(src, (W0, W1), order=("S2",)), "Total", "S2") == 0
    tbl = observations_per_month(src, (W0, W1), order=("S2",), field=NDVI_FILTERED_FIELD)
    assert _cell(tbl, "Total", "S2") == 1


def test_window_and_empty_months():
    tbl = observations_per_month({"S2": _src(["2019-09-30", "2020-01-05", "2021-04-01"])}, (W0, W1), order=("S2",))
    months = tbl["month"][tbl["month"].str.fullmatch(r"\d{4}-\d{2}")].tolist()
    assert months[0] == "2019-10" and months[-1] == "2021-03" and len(months) == 18
    assert _cell(tbl, "Total", "S2") == 1 and _cell(tbl, "2019-11", "S2") == 0


def test_summary_rows():
    d = ["2019-12-01", "2020-03-31", "2020-04-01", "2020-12-15", "2021-02-01"]
    tbl = observations_per_month({"S2": _src(d)}, (W0, W1), order=("S2",))
    months = tbl["month"].str.fullmatch(r"\d{4}-\d{2}")
    assert tbl.loc[months, "S2"].sum() == _cell(tbl, "Total", "S2") == 5
    assert _cell(tbl, "Dec 2019 – Mar 2020", "S2") == 2
    assert _cell(tbl, "Dec 2020 – Mar 2021", "S2") == 2
    assert not any(m.startswith("Dec 2018") for m in tbl["month"])


def test_incomplete_season_gets_no_row():
    short = int(datetime(2021, 2, 28).timestamp())
    tbl = observations_per_month({"S2": _src(["2020-12-15"])}, (W0, short), order=("S2",))
    assert "Dec 2020 – Mar 2021" not in tbl["month"].tolist()


def test_excluded_label_and_missing_source():
    with pytest.warns(UserWarning, match="MODIS"):
        tbl = observations_per_month({"L8": _src(["2020-01-05"])}, (W0, W1), order=("MODIS", "L8"), excluded=["L8"])
    assert list(tbl.columns) == ["month", "L8 (excluded)"]
