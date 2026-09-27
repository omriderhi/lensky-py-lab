"""
Tests for lensky_py_lab.visualization.phenology_markers

Verifies SoS/PoS/EoS markers are drawn as scatter points (not axvline spans).
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from lensky_py_lab.visualization.phenology_markers import draw_phenology_markers


def _make_phenology_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "satellite": "MODIS",
            "year": 2020,
            "SoS_date": pd.Timestamp("2020-10-15"),
            "PoS_date": pd.Timestamp("2021-01-15"),
            "EoS_date": pd.Timestamp("2021-04-15"),
            "SoS_value": 0.35,
            "PoS_value": 0.75,
            "EoS_value": 0.30,
        }
    ])


def test_draw_phenology_markers_uses_scatter_not_axvline():
    fig, ax = plt.subplots()
    ax.plot(
        pd.date_range("2020-09-01", "2021-06-01", freq="D"),
        range(len(pd.date_range("2020-09-01", "2021-06-01", freq="D"))),
    )
    n_lines_before = len(ax.lines)

    draw_phenology_markers(ax, _make_phenology_df())

    assert len(ax.lines) == n_lines_before, "no axvline/plot lines should be added"
    assert len(ax.collections) >= 3, "expected one scatter point per SoS/PoS/EoS marker"
    plt.close(fig)


def test_draw_phenology_markers_filters_by_source_and_year():
    fig, ax = plt.subplots()
    ax.plot(
        pd.date_range("2020-09-01", "2021-06-01", freq="D"),
        range(len(pd.date_range("2020-09-01", "2021-06-01", freq="D"))),
    )

    draw_phenology_markers(ax, _make_phenology_df(), source="Sentinel2")
    assert len(ax.collections) == 0, "non-matching source should draw nothing"

    draw_phenology_markers(ax, _make_phenology_df(), source="MODIS", year=2020)
    assert len(ax.collections) >= 3
    plt.close(fig)
