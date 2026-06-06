from __future__ import annotations

from typing import Generator, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

WIDE_GAP_SECONDS: int = 60 * 24 * 3600  # 60 days ≈ 2 months


def iter_gap_segments(
    ts_unix: np.ndarray,
    values: np.ndarray,
    max_gap_sec: float = WIDE_GAP_SECONDS,
) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
    """Yield (ts_sub, vals_sub) for each run with no inter-valid-point gap > max_gap_sec.

    NaN entries in *values* are excluded from every segment (treated as absent).

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


def dense_interpolate_with_gaps(
    ts_unix: np.ndarray,
    values: np.ndarray,
    max_gap_sec: float = WIDE_GAP_SECONDS,
    n_points: int = 800,
) -> Tuple[pd.DatetimeIndex, np.ndarray]:
    """Interpolate LOWESS knots onto a dense grid, inserting NaN breaks at wide gaps.

    Each continuous segment (separated by a gap > *max_gap_sec*) gets its own
    proportional share of *n_points* and is joined to adjacent segments with a
    single NaN y-value so matplotlib lifts the pen between them.

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
            # NaN separator: midpoint timestamp (valid int for DatetimeIndex, NaN y breaks line)
            sep_ts = (all_x[-1][-1] + float(ts_seg[0])) / 2.0
            all_x.append(np.array([sep_ts]))
            all_y.append(np.array([np.nan]))

        all_x.append(seg_x)
        all_y.append(seg_y)

    x_out = np.concatenate(all_x)
    y_out = np.concatenate(all_y)
    dates_out = pd.to_datetime(x_out.astype(np.int64), unit="s")
    return dates_out, y_out
