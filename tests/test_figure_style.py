"""Tests for the reviewer-driven figure style (legend size, solid NSRS lines,
visible phenology markers, panel letters, comparable y-spans)."""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plot_config import (
    FONT_SIZE_LEGEND,
    NSRS_LINEWIDTH,
    PHENO_MARKER_SIZE,
    SATELLITE_LINEWIDTH,
)
from lensky_py_lab.plotting.plotter import plot_site
from lensky_py_lab.visualization.figure_generator import plot_decomposition_comparative
from lensky_py_lab.visualization.phenology_markers import draw_phenology_markers

_DAYS = pd.date_range("2020-09-01", "2021-08-31", freq="D")
_TS = (_DAYS.astype("int64") // 10**9).values


def _site_df() -> pd.DataFrame:
    x = np.linspace(0, 2 * np.pi, len(_TS))
    return pd.DataFrame(
        {
            "NDVI lowess MODIS": 0.5 + 0.2 * np.sin(x),
            "NDVI lowess NSRS_1": 0.4 + 0.1 * np.sin(x),
            "NDVI lowess NSRS_2": 0.6 + 0.02 * np.cos(x),
            "NDVI lowess NSRS_3": 0.5 + 0.15 * np.sin(x),
        },
        index=_TS,
    )


def test_plot_site_legend_size_and_nsrs_lines_solid():
    fig = plot_site("test", _site_df())
    ax = fig.axes[0]
    for text in ax.get_legend().get_texts():
        assert text.get_fontsize() >= FONT_SIZE_LEGEND
    by_label = {ln.get_label(): ln for ln in ax.lines}
    for name in ("NSRS_1", "NSRS_2", "NSRS_3"):
        assert by_label[name].get_linestyle() == "-"
        assert by_label[name].get_linewidth() == NSRS_LINEWIDTH
    assert by_label["MODIS"].get_linewidth() == SATELLITE_LINEWIDTH
    assert NSRS_LINEWIDTH > SATELLITE_LINEWIDTH
    plt.close(fig)


def test_phenology_markers_use_configured_size():
    fig, ax = plt.subplots()
    ax.plot(_DAYS, range(len(_DAYS)))
    df = pd.DataFrame([{
        "satellite": "MODIS", "year": 2021,
        "SoS_date": pd.Timestamp("2020-10-15"), "SoS_value": 0.3,
        "PoS_date": pd.Timestamp("2021-01-15"), "PoS_value": 0.7,
        "EoS_date": pd.Timestamp("2021-04-15"), "EoS_value": 0.3,
    }])
    draw_phenology_markers(ax, df)
    assert ax.collections
    for coll in ax.collections:
        assert float(coll.get_sizes()[0]) == PHENO_MARKER_SIZE
    plt.close(fig)


def test_decomposition_panel_letters_and_equal_spans():
    df = _site_df()
    woody = pd.Series(0.6 + 0.02 * np.cos(np.linspace(0, 6, len(_TS))), index=_TS)
    herb = pd.Series(0.2 * np.sin(np.linspace(0, 6, len(_TS))), index=_TS)
    fig = plot_decomposition_comparative("test", df, "MODIS", woody, herb)
    letters = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert {"A", "B", "C"} <= set(letters)
    lo2, hi2 = fig.axes[1].get_ylim()
    lo3, hi3 = fig.axes[2].get_ylim()
    lo1, hi1 = fig.axes[0].get_ylim()
    assert np.isclose(hi2 - lo2, hi3 - lo3)
    assert np.isclose(hi1 - lo1, hi2 - lo2)   # panel A shares the span too
    plt.close(fig)


def test_equalize_y_span_ignores_empty_panels():
    from lensky_py_lab.visualization.figure_generator import _equalize_y_span

    fig, axes = plt.subplots(3, 1)
    axes[0].plot([0, 1], [0.0, 0.1])
    axes[1].plot([0, 1], [0.5, 0.7])
    # axes[2] has no data: default (0, 1) limits must not set the span
    _equalize_y_span(axes)
    lo, hi = axes[0].get_ylim()
    assert np.isclose(hi - lo, axes[1].get_ylim()[1] - axes[1].get_ylim()[0])
    assert (hi - lo) < 0.5
    assert axes[2].get_ylim() == (0.0, 1.0)
    plt.close(fig)
