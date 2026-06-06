"""Tests for gap-segment utilities (gap_utils.py)."""
from __future__ import annotations

import numpy as np
import pytest

from lensky_py_lab.gap_utils import (
    WIDE_GAP_SECONDS,
    boundaries_from_raw,
    dense_interpolate_from_boundaries,
    dense_interpolate_with_gaps,
    iter_gap_segments,
    iter_segments_from_boundaries,
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


# ---------------------------------------------------------------------------
# boundaries_from_raw / iter_segments_from_boundaries
# ---------------------------------------------------------------------------


def test_boundaries_from_raw_two_segments():
    ts_a = np.arange(0, 30 * ONE_DAY, ONE_DAY, dtype=float)
    ts_b = np.arange(120 * ONE_DAY, 150 * ONE_DAY, ONE_DAY, dtype=float)
    ts = np.concatenate([ts_a, ts_b])
    raw = np.ones(len(ts))
    bounds = boundaries_from_raw(ts, raw, WIDE_GAP_SECONDS)
    assert len(bounds) == 2
    assert bounds[0][0] == pytest.approx(ts_a[0])
    assert bounds[0][1] == pytest.approx(ts_a[-1])
    assert bounds[1][0] == pytest.approx(ts_b[0])


def test_iter_segments_from_boundaries_respects_windows():
    """Filtered data quality holes within a segment are not false-cut."""
    ts_raw = np.arange(0, 100 * ONE_DAY, ONE_DAY, dtype=float)
    raw_vals = np.ones(len(ts_raw))
    bounds = boundaries_from_raw(ts_raw, raw_vals, WIDE_GAP_SECONDS)
    assert len(bounds) == 1  # raw data is continuous

    # Filtered data has a 70-day quality hole mid-segment (would trigger iter_gap_segments)
    filtered_vals = raw_vals.copy()
    filtered_vals[20:90] = np.nan  # 70-day hole

    segs = list(iter_segments_from_boundaries(ts_raw, filtered_vals, bounds))
    # Should be ONE segment (the raw boundary is respected, not the filtered gap)
    assert len(segs) == 1


def test_iter_segments_from_boundaries_splits_at_collection_gap():
    """Real collection gaps (absent in raw) still split across segments."""
    ts_a = np.arange(0, 30 * ONE_DAY, ONE_DAY, dtype=float)
    ts_b = np.arange(120 * ONE_DAY, 150 * ONE_DAY, ONE_DAY, dtype=float)
    ts_raw = np.concatenate([ts_a, ts_b])
    raw_vals = np.ones(len(ts_raw))
    bounds = boundaries_from_raw(ts_raw, raw_vals, WIDE_GAP_SECONDS)
    assert len(bounds) == 2

    filtered_vals = raw_vals.copy()
    segs = list(iter_segments_from_boundaries(ts_raw, filtered_vals, bounds))
    assert len(segs) == 2


# ---------------------------------------------------------------------------
# dense_interpolate_from_boundaries
# ---------------------------------------------------------------------------


def test_dense_from_boundaries_no_extra_breaks():
    """Quality hole within a segment must NOT produce a NaN break in the output."""
    ts_raw = np.arange(0, 100 * ONE_DAY, ONE_DAY, dtype=float)
    raw_vals = np.ones(len(ts_raw))
    bounds = boundaries_from_raw(ts_raw, raw_vals, WIDE_GAP_SECONDS)

    lowess_vals = raw_vals.copy()
    lowess_vals[20:90] = np.nan  # 70-day quality hole

    dates, y = dense_interpolate_from_boundaries(ts_raw, lowess_vals, bounds)
    # Single segment → no NaN break expected
    assert not np.isnan(y).any()


def test_dense_from_boundaries_breaks_at_real_gap():
    """Real collection gap must produce exactly one NaN break."""
    ts_a = np.arange(0, 30 * ONE_DAY, ONE_DAY, dtype=float)
    ts_b = np.arange(120 * ONE_DAY, 150 * ONE_DAY, ONE_DAY, dtype=float)
    ts_raw = np.concatenate([ts_a, ts_b])
    raw_vals = np.ones(len(ts_raw))
    bounds = boundaries_from_raw(ts_raw, raw_vals, WIDE_GAP_SECONDS)

    dates, y = dense_interpolate_from_boundaries(ts_raw, raw_vals, bounds)
    assert np.isnan(y).sum() == 1
