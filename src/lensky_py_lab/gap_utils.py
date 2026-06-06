from __future__ import annotations

from typing import Generator, List, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

WIDE_GAP_SECONDS: int = 60 * 24 * 3600  # 60 days ≈ 2 months


# ---------------------------------------------------------------------------
# Core segment detection
# ---------------------------------------------------------------------------


def iter_gap_segments(
    ts_unix: np.ndarray,
    values: np.ndarray,
    max_gap_sec: float = WIDE_GAP_SECONDS,
) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
    """Yield (ts_sub, vals_sub) for each run with no inter-valid-point gap > max_gap_sec.

    NaN entries in *values* are excluded from every segment (treated as absent).
    Gap detection is performed on the supplied *values* — use raw data when possible
    to avoid false splits caused by filtering artefacts.

    Parameters
    ----------
    ts_unix : np.ndarray
        Unix timestamps (integer or float seconds).
    values : np.ndarray
        Corresponding values; NaN entries are excluded.
    max_gap_sec : float
        Maximum allowed seconds between consecutive valid points before
        starting a new segment. Default: 60 days.

    Yields
    ------
    (ts_sub, vals_sub) : tuple[np.ndarray, np.ndarray]
        Valid-only points for this segment.
    """
    mask = np.isfinite(values)
    valid_idx = np.where(mask)[0]
    if len(valid_idx) == 0:
        return

    ts_valid = ts_unix[valid_idx].astype(np.float64)
    diffs = np.diff(ts_valid)
    split_at = np.where(diffs > max_gap_sec)[0] + 1  # positions in valid_idx

    seg_starts = np.concatenate([[0], split_at])
    seg_ends = np.concatenate([split_at, [len(valid_idx)]])

    for start, end in zip(seg_starts, seg_ends):
        chunk = valid_idx[start:end]
        if len(chunk) == 0:
            continue
        yield ts_unix[chunk], values[chunk]


def boundaries_from_raw(
    ts_unix: np.ndarray,
    raw_values: np.ndarray,
    max_gap_sec: float = WIDE_GAP_SECONDS,
) -> List[Tuple[float, float]]:
    """Return (seg_start_ts, seg_end_ts) pairs derived from raw (unfiltered) data.

    Using raw data as the reference ensures that gaps introduced by quality
    filtering do not create false segment boundaries — only true collection
    pauses (where the sensor produced no readings at all) are detected.

    Parameters
    ----------
    ts_unix : np.ndarray
        Unix timestamps of the raw data.
    raw_values : np.ndarray
        Raw NDVI values; NaN entries are treated as absent readings.
    max_gap_sec : float
        Gap threshold in seconds. Default: 60 days.

    Returns
    -------
    list of (float, float)
        One ``(start_ts, end_ts)`` tuple per continuous collection period.
    """
    return [
        (float(ts_seg[0]), float(ts_seg[-1]))
        for ts_seg, _ in iter_gap_segments(ts_unix, raw_values, max_gap_sec)
    ]


def iter_segments_from_boundaries(
    ts_unix: np.ndarray,
    values: np.ndarray,
    boundaries: List[Tuple[float, float]],
) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
    """Yield valid (ts_sub, vals_sub) within each pre-computed boundary window.

    This applies the segment definitions computed from raw data to a different
    column (filtered, clean, LOWESS) so that all pipeline stages share exactly
    the same break points.

    Parameters
    ----------
    ts_unix : np.ndarray
        Unix timestamps matching *values*.
    values : np.ndarray
        Values to segment; NaN entries within a window are excluded.
    boundaries : list of (float, float)
        ``(start_ts, end_ts)`` pairs from :func:`boundaries_from_raw`.

    Yields
    ------
    (ts_sub, vals_sub) : tuple[np.ndarray, np.ndarray]
        Valid points within each boundary window. Empty windows are skipped.
    """
    for seg_start, seg_end in boundaries:
        in_seg = (ts_unix >= seg_start) & (ts_unix <= seg_end)
        ts_in = ts_unix[in_seg]
        vals_in = values[in_seg]
        valid = np.isfinite(vals_in)
        if valid.any():
            yield ts_in[valid], vals_in[valid]


# ---------------------------------------------------------------------------
# Dense interpolation helpers
# ---------------------------------------------------------------------------


def _build_dense_output(
    segments: List[Tuple[np.ndarray, np.ndarray]],
    n_points: int,
) -> Tuple[pd.DatetimeIndex, np.ndarray]:
    """Interpolate each segment onto a dense grid; join with NaN pen-lifts.

    Parameters
    ----------
    segments : list of (ts_array, vals_array)
        Each entry contains the valid (non-NaN) points for one segment.
        Both arrays must be float64-compatible.
    n_points : int
        Total output points, distributed proportionally across segments by
        their time span.

    Returns
    -------
    dates_dense : pd.DatetimeIndex
    vals_dense  : np.ndarray
    """
    if not segments:
        return pd.to_datetime(np.array([], dtype=np.int64), unit="s"), np.array([])

    spans = [float(ts[-1] - ts[0]) if len(ts) > 1 else 0.0 for ts, _ in segments]
    total_span = sum(spans)

    all_x: list = []
    all_y: list = []

    for i, ((ts_seg, vals_seg), span) in enumerate(zip(segments, spans)):
        n_valid = len(ts_seg)

        if n_valid == 1:
            seg_x = ts_seg.astype(np.float64)
            seg_y = vals_seg.astype(np.float64)
        else:
            x = ts_seg.astype(np.float64)
            y = vals_seg.astype(np.float64)
            pts = max(2, int(n_points * span / total_span)) if total_span > 0 else 2
            f = interp1d(x, y, kind="linear", bounds_error=False, fill_value=np.nan)
            seg_x = np.linspace(x[0], x[-1], pts)
            seg_y = f(seg_x)

        if i > 0 and all_x:
            # NaN separator: midpoint timestamp between previous and current segment.
            # The y-value NaN causes matplotlib to lift the pen; the x timestamp is
            # a valid integer so DatetimeIndex construction works cleanly.
            sep_ts = (all_x[-1][-1] + float(ts_seg[0])) / 2.0
            all_x.append(np.array([sep_ts]))
            all_y.append(np.array([np.nan]))

        all_x.append(seg_x)
        all_y.append(seg_y)

    x_out = np.concatenate(all_x)
    y_out = np.concatenate(all_y)
    dates_out = pd.to_datetime(x_out.astype(np.int64), unit="s")
    return dates_out, y_out


def dense_interpolate_with_gaps(
    ts_unix: np.ndarray,
    values: np.ndarray,
    max_gap_sec: float = WIDE_GAP_SECONDS,
    n_points: int = 800,
) -> Tuple[pd.DatetimeIndex, np.ndarray]:
    """Interpolate LOWESS knots onto a dense grid, inserting NaN breaks at wide gaps.

    Gap detection is performed on *values* itself. When the authoritative segment
    boundaries are already known (computed from raw data), prefer
    :func:`dense_interpolate_from_boundaries` to avoid false splits caused by
    data-quality holes in filtered or LOWESS columns.

    Parameters
    ----------
    ts_unix : np.ndarray
        Unix timestamps (integer seconds) matching *values*.
    values : np.ndarray
        NDVI values; NaN entries are ignored.
    max_gap_sec : float
        Gap threshold for segment splitting. Default: 60 days.
    n_points : int
        Total dense output points distributed proportionally across segments.

    Returns
    -------
    dates_dense : pd.DatetimeIndex
    vals_dense  : np.ndarray
    """
    segments = list(iter_gap_segments(ts_unix, values, max_gap_sec))
    return _build_dense_output(segments, n_points)


def dense_interpolate_from_boundaries(
    ts_unix: np.ndarray,
    values: np.ndarray,
    boundaries: List[Tuple[float, float]],
    n_points: int = 800,
) -> Tuple[pd.DatetimeIndex, np.ndarray]:
    """Interpolate onto a dense grid using pre-computed raw-data segment boundaries.

    Unlike :func:`dense_interpolate_with_gaps`, this function does not re-detect
    gaps from *values*. It uses the boundaries derived from raw data, so filtered
    or LOWESS columns that have data-quality holes do not produce extra breaks.

    Parameters
    ----------
    ts_unix : np.ndarray
        Unix timestamps (integer seconds) matching *values*.
    values : np.ndarray
        NDVI values; NaN entries within each boundary window are excluded.
    boundaries : list of (float, float)
        ``(start_ts, end_ts)`` pairs from :func:`boundaries_from_raw`.
    n_points : int
        Total dense output points distributed proportionally across segments.

    Returns
    -------
    dates_dense : pd.DatetimeIndex
    vals_dense  : np.ndarray
    """
    segments = list(iter_segments_from_boundaries(ts_unix, values, boundaries))
    return _build_dense_output(segments, n_points)
