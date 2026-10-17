"""GEEClient construction (no network: ``ee`` is replaced by a stub)."""
import sys
import types

import pytest

from lensky_py_lab.clients.gee_client import _CLOUD_FILTER
from lensky_py_lab.constants import SatelliteSource


@pytest.fixture
def fake_ee(monkeypatch):
    calls = {}
    mod = types.ModuleType("ee")
    mod.Initialize = lambda **kw: calls.update(kw)
    monkeypatch.setitem(sys.modules, "ee", mod)
    return calls


def test_default_credentials_use_stored_login(fake_ee):
    from lensky_py_lab.clients.gee_client import GEEClient

    GEEClient(project="p")
    # None would mean "no credentials" to ee.Initialize and fail to authenticate.
    assert fake_ee["credentials"] == "persistent"


def test_explicit_credentials_passed_through(fake_ee):
    from lensky_py_lab.clients.gee_client import GEEClient

    sentinel = object()
    GEEClient(project="p", credentials=sentinel)
    assert fake_ee["credentials"] is sentinel


def test_s2_cloud_property_matches_research_script():
    assert _CLOUD_FILTER[SatelliteSource.SENTINEL2] == ("CLOUD_COVERAGE_ASSESSMENT", 10)
