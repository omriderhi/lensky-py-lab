"""Tests for gap-segment utilities (gap_utils.py)."""
from __future__ import annotations

import numpy as np
import pytest

from lensky_py_lab.gap_utils import (
    WIDE_GAP_SECONDS,
    dense_interpolate_with_gaps,
    iter_gap_segments,
)

ONE_DAY = 24 * 3600


# ---------------------------------------------------------------------------
# iter_gap_segments
# ---------------------------------------------------------------------------


def test_no_gap_yields_one_segment():
    ts = np.arange(0, 30 * ONE_DAY, ONE_DAY, dtype=float)
    vals = np.ones(30)
    segs = list(iter_gap_segments(ts, vals, max_gap_sec=WIDE_GAP_SECONDS))
    assert len(segs) == 1
    assert len(segs[0][0]) == 30


def test_wide_gap_yields_two_segments():
    ts_a = np.arange(0, 30 * ONE_DAY, ONE_DAY, dtype=float)
    ts_b = np.arange(120 * ONE_DAY, 150 * ONE_DAY, ONE_DAY, dtype=float)  # 90-day gap
    ts = np.concatenate([ts_a, ts_b])
    vals = np.ones(len(ts))
    segs = list(iter_gap_segments(ts, vals, max_gap_sec=WIDE_GAP_SECONDS))
    assert len(segs) == 2
    assert len(segs[0][0]) == 30
    assert len(segs[1][0]) == 30


def test_small_gap_not_split():
    ts_a = np.arange(0, 30 * ONE_DAY, ONE_DAY, dtype=float)
    ts_b = np.arange(50 * ONE_DAY, 80 * ONE_DAY, ONE_DAY, dtype=float)  # 20-day gap
    ts = np.concatenate([ts_a, ts_b])
    vals = np.ones(len(ts))
    segs = list(iter_gap_segments(ts, vals, max_gap_sec=WIDE_GAP_SECONDS))
    assert len(segs) == 1


def test_nan_values_excluded_from_segments():
    ts = np.arange(0, 10 * ONE_DAY, ONE_DAY, dtype=float)
    vals = np.ones(10)
    vals[3] = np.nan
    segs = list(iter_gap_segments(ts, vals, max_gap_sec=WIDE_GAP_SECONDS))
    assert len(segs) == 1
    assert len(segs[0][0]) == 9


def test_all_nan_yields_nothing():
    ts = np.arange(0, 5 * ONE_DAY, ONE_DAY, dtype=float)
    vals = np.full(5, np.nan)
    segs = list(iter_gap_segments(ts, vals, max_gap_sec=WIDE_GAP_SECONDS))
    assert segs == []


def test_nan_spanning_gap_creates_two_segments():
    """NaN values inside a wide gap don't prevent correct segment detection."""
    ts_a = np.arange(0, 10 * ONE_DAY, ONE_DAY, dtype=float)
    ts_b = np.arange(120 * ONE_DAY, 130 * ONE_DAY, ONE_DAY, dtype=float)
    ts = np.concatenate([ts_a, ts_b])
    vals = np.ones(len(ts))
    vals[5] = np.nan  # NaN inside segment A
    segs = list(iter_gap_segments(ts, vals, max_gap_sec=WIDE_GAP_SECONDS))
    assert len(segs) == 2


# ---------------------------------------------------------------------------
# dense_interpolate_with_gaps
# ---------------------------------------------------------------------------


def test_single_segment_no_nan_in_output():
    ts = np.arange(0, 30 * ONE_DAY, ONE_DAY, dtype=float)
    vals = np.linspace(0.3, 0.7, 30)
    dates, y = dense_interpolate_with_gaps(ts, vals, max_gap_sec=WIDE_GAP_SECONDS)
    assert not np.isnan(y).any()
    assert len(y) > 1


def test_two_segments_have_nan_break():
    ts_a = np.arange(0, 10 * ONE_DAY, ONE_DAY, dtype=float)
    ts_b = np.arange(120 * ONE_DAY, 130 * ONE_DAY, ONE_DAY, dtype=float)
    ts = np.concatenate([ts_a, ts_b])
    vals = np.ones(len(ts))
    dates, y = dense_interpolate_with_gaps(ts, vals, max_gap_sec=WIDE_GAP_SECONDS)
    assert np.isnan(y).any(), "Expected at least one NaN break between segments"


def test_empty_input():
    ts = np.array([], dtype=float)
    vals = np.array([], dtype=float)
    dates, y = dense_interpolate_with_gaps(ts, vals, max_gap_sec=WIDE_GAP_SECONDS)
    assert len(dates) == 0
    assert len(y) == 0


def test_single_point():
    ts = np.array([ONE_DAY * 10], dtype=float)
    vals = np.array([0.5])
    dates, y = dense_interpolate_with_gaps(ts, vals, max_gap_sec=WIDE_GAP_SECONDS)
    assert len(dates) == 1
    assert y[0] == pytest.approx(0.5)


def test_output_points_distributed_across_segments():
    """Each segment should contribute points proportional to its time span."""
    ts_a = np.arange(0, 100 * ONE_DAY, ONE_DAY, dtype=float)
    ts_b = np.arange(200 * ONE_DAY, 300 * ONE_DAY, ONE_DAY, dtype=float)
    ts = np.concatenate([ts_a, ts_b])
    vals = np.ones(len(ts))
    dates, y = dense_interpolate_with_gaps(ts, vals, n_points=100, max_gap_sec=WIDE_GAP_SECONDS)
    # Segments are equal span → roughly equal point counts (plus 1 NaN separator)
    nan_count = int(np.isnan(y).sum())
    assert nan_count == 1
    assert len(y) > 10
