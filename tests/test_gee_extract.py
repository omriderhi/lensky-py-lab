"""GEE extraction into the data CSVs (no network: the client is a stub)."""
import json
import os
import stat

import pandas as pd
import pytest

from lensky_py_lab.io.csv_loader import load_source_csv
from lensky_py_lab.io.gee_extract import (
    MODIS_COLLECTIONS,
    PROVENANCE_FILE,
    extract_sources,
    parse_sources,
)

DAY = 86400
T0 = 1546300800  # 2019-01-01


def _frame(values, start=T0):
    return pd.DataFrame({"NDVI RAW": values}, index=pd.Index([start + i * 5 * DAY for i in range(len(values))], name="TS"))


class StubClient:
    def __init__(self, frames):
        self.frames, self.calls = frames, []

    def point_geometry(self, lon, lat):
        return (lon, lat)

    def get_ndvi_timeseries(self, geometry, start, end, source, collection=None, **kw):
        self.calls.append((source.value, start, end, collection))
        return self.frames[source.value]


def _seed(data_dir, name, n=10, value=0.5):
    pd.DataFrame({"DATE": [f"Jan {i + 1}, 2019" for i in range(n)], "NDVI_RAW": [value] * n}).to_csv(
        data_dir / f"{name}.csv", index=False)


def test_parse_sources():
    assert parse_sources(None) == [] and parse_sources("none") == []
    assert parse_sources("all") == ["MODIS", "S2", "L8"]
    assert parse_sources("s2, modis,S2") == ["S2", "MODIS"]
    with pytest.raises(ValueError, match="NSRS"):
        parse_sources("NSRS_1")


def test_only_selected_sources_are_touched(tmp_path):
    _seed(tmp_path, "S2", value=0.5)
    _seed(tmp_path, "MODIS", value=0.5)
    before = (tmp_path / "MODIS.csv").read_bytes()
    client = StubClient({"S2": _frame([0.6] * 10)})
    extract_sources(["S2"], tmp_path, client)
    assert (tmp_path / "MODIS.csv").read_bytes() == before
    assert [c[0] for c in client.calls] == ["S2"]


def test_written_in_loader_format_with_provenance(tmp_path):
    _seed(tmp_path, "S2")
    extract_sources(["S2"], tmp_path, StubClient({"S2": _frame([0.61, 0.62, 0.63, 0.64, 0.65, 0.66, 0.67, 0.68, 0.69, 0.7])}))
    header = (tmp_path / "S2.csv").read_text().splitlines()[:2]
    assert header == ["DATE,NDVI_RAW", '"Jan 1, 2019",0.61']
    assert load_source_csv(tmp_path / "S2.csv")["NDVI RAW"].iloc[0] == pytest.approx(0.61)
    log = json.loads((tmp_path / PROVENANCE_FILE).read_text())
    assert log["S2"]["rows"] == 10 and log["S2"]["window"] == ["2019-01-01", "2021-12-05"]
    assert log["S2"]["comparison_with_previous_file"]["previous_file"] is True


def test_modis_collection_choice_is_passed_on(tmp_path):
    client = StubClient({"MODIS": _frame([0.5] * 5)})
    extract_sources(["MODIS"], tmp_path, client, modis_collection="061")
    assert client.calls[0][3] == MODIS_COLLECTIONS["061"]
    with pytest.raises(ValueError):
        extract_sources(["MODIS"], tmp_path, client, modis_collection="005")


def test_empty_result_refuses_and_keeps_file(tmp_path):
    _seed(tmp_path, "S2")
    before = (tmp_path / "S2.csv").read_bytes()
    with pytest.raises(RuntimeError, match="no data"):
        extract_sources(["S2"], tmp_path, StubClient({"S2": pd.DataFrame(columns=["NDVI RAW"])}))
    assert (tmp_path / "S2.csv").read_bytes() == before
    assert not (tmp_path / PROVENANCE_FILE).exists()


def test_much_shorter_result_refused_unless_forced(tmp_path):
    _seed(tmp_path, "S2", n=10)
    short = StubClient({"S2": _frame([0.6, 0.6])})
    before = (tmp_path / "S2.csv").read_bytes()
    with pytest.raises(RuntimeError, match="refusing"):
        extract_sources(["S2"], tmp_path, short)
    assert (tmp_path / "S2.csv").read_bytes() == before
    extract_sources(["S2"], tmp_path, short, force=True)
    assert len(load_source_csv(tmp_path / "S2.csv")) == 2


def test_nothing_written_when_a_later_source_fails(tmp_path):
    _seed(tmp_path, "S2")
    _seed(tmp_path, "MODIS")
    before = {n: (tmp_path / f"{n}.csv").read_bytes() for n in ("S2", "MODIS")}
    client = StubClient({"S2": _frame([0.6] * 10), "MODIS": pd.DataFrame(columns=["NDVI RAW"])})
    with pytest.raises(RuntimeError):
        extract_sources(["S2", "MODIS"], tmp_path, client)
    assert {n: (tmp_path / f"{n}.csv").read_bytes() for n in ("S2", "MODIS")} == before


def test_unwritable_target_stops_before_anything_is_written(tmp_path):
    _seed(tmp_path, "S2")
    _seed(tmp_path, "L8")
    before = (tmp_path / "S2.csv").read_bytes()
    os.chmod(tmp_path / "L8.csv", stat.S_IREAD)
    try:
        client = StubClient({"S2": _frame([0.6] * 10), "L8": _frame([0.6] * 10)})
        with pytest.raises(RuntimeError, match="nothing was written"):
            extract_sources(["S2", "L8"], tmp_path, client)
        assert (tmp_path / "S2.csv").read_bytes() == before
        assert not (tmp_path / PROVENANCE_FILE).exists()
    finally:
        os.chmod(tmp_path / "L8.csv", stat.S_IWRITE | stat.S_IREAD)
