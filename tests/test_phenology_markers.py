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


def test_degenerate_seasons_are_not_drawn():
    """Truncated seasons (SoS == PoS, or a <60-day span) are skipped when plotting."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    fig, ax = plt.subplots()
    ax.plot(pd.date_range("2020-09-01", "2021-12-31", freq="D"), [0.5] * 487)
    df = pd.DataFrame([
        {"satellite": "X", "year": 2021,
         "SoS_date": pd.Timestamp("2020-11-01"), "SoS_value": 0.4,
         "PoS_date": pd.Timestamp("2021-02-01"), "PoS_value": 0.7,
         "EoS_date": pd.Timestamp("2021-05-01"), "EoS_value": 0.4},
        {"satellite": "X", "year": 2022,
         "SoS_date": pd.Timestamp("2021-09-01"), "SoS_value": 0.4,
         "PoS_date": pd.Timestamp("2021-09-01"), "PoS_value": 0.4,
         "EoS_date": pd.Timestamp("2021-09-11"), "EoS_value": 0.4},
    ])
    draw_phenology_markers(ax, df)
    drawn = [c for c in ax.collections if len(c.get_offsets())]
    assert len(drawn) == 3   # one complete season only
    plt.close(fig)


def _row(sos, pos, eos, year=2021):
    def t(d):
        return pd.Timestamp(d) if d else pd.NaT

    return {"satellite": "X", "year": year,
            "SoS_date": t(sos), "SoS_value": 0.4,
            "PoS_date": t(pos), "PoS_value": 0.7,
            "EoS_date": t(eos), "EoS_value": 0.4}


def _n_drawn(df, **kw):
    fig, ax = plt.subplots()
    ax.plot(pd.date_range("2020-09-01", "2021-12-31", freq="D"), [0.5] * 487)
    draw_phenology_markers(ax, df, **kw)
    n = sum(len(c.get_offsets()) for c in ax.collections)
    plt.close(fig)
    return n


def test_peak_and_end_days_apart_is_degenerate():
    # SoS far from PoS, but PoS and EoS 3 days apart (NSRS_2 2020 pattern)
    assert _n_drawn(pd.DataFrame([_row("2020-11-01", "2021-04-22", "2021-04-25")])) == 0


def test_partial_row_with_sos_equal_pos_is_degenerate():
    assert _n_drawn(pd.DataFrame([_row("2021-01-05", "2021-01-05", None)])) == 0


def test_partial_row_in_order_is_still_drawn():
    assert _n_drawn(pd.DataFrame([_row("2020-11-01", "2021-02-01", None)])) == 2


def test_skip_degenerate_can_be_disabled_and_thresholds_overridden():
    df = pd.DataFrame([_row("2020-11-01", "2021-04-22", "2021-04-25")])
    assert _n_drawn(df, skip_degenerate=False) == 3
    assert _n_drawn(df, min_peak_to_end_days=2) == 3


def test_suppressed_season_is_logged(caplog):
    import logging

    df = pd.DataFrame([_row("2021-09-01", "2021-09-01", "2021-09-11", year=9999)])
    with caplog.at_level(logging.WARNING):
        _n_drawn(df)
    assert any("9999" in r.message for r in caplog.records)
