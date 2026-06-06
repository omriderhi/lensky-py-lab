from __future__ import annotations

import pandas as pd
import statsmodels.api as sm

from lensky_py_lab.configs import SourceConfig
from lensky_py_lab.constants import NDVI_CLEAN_FIELD, NDVI_LOWESS_FIELD, NDVI_RAW_FIELD, TIMESTAMP_FIELD
from lensky_py_lab.gap_utils import boundaries_from_raw, iter_segments_from_boundaries


def add_lowess(df: pd.DataFrame, config: SourceConfig) -> pd.DataFrame:
    """Apply LOWESS smoothing to NDVI_CLEAN_FIELD and add NDVI_LOWESS_FIELD.

    When config.wide_gap_days is set, segment boundaries are derived from the
    raw data column (NDVI RAW) so that only genuine collection pauses create
    separate LOWESS fits. Data-quality holes in the filtered/clean data do not
    produce false splits. LOWESS is then computed independently per segment to
    prevent cross-gap contamination near gap boundaries.

    Bandwidth per segment: frac = images_per_month / n_segment_points.
    If config.lowess_min_neighbors is set, frac is clamped so that at least
    that many neighbours are always used (prevents over-smoothing on short
    segments).

    If general_factor is set, smoothed values are multiplied by it afterward.
    If images_per_month is None, NDVI_CLEAN_FIELD is copied to NDVI_LOWESS_FIELD.
    """
    df = df.copy()

    if config.images_per_month is None:
        df[NDVI_LOWESS_FIELD] = df[NDVI_CLEAN_FIELD]
        return df

    clean_df = df.dropna(subset=[NDVI_CLEAN_FIELD])
    if clean_df.empty:
        df[NDVI_LOWESS_FIELD] = None
        return df

    ts_all = clean_df.index.values
    vals_all = clean_df[NDVI_CLEAN_FIELD].values

    if config.wide_gap_days is not None:
        max_gap_sec = config.wide_gap_days * 24 * 3600
        if NDVI_RAW_FIELD in df.columns:
            # Detect gaps from raw data: only genuine collection pauses create segments.
            # Filtering artefacts (data-quality holes) are ignored.
            raw_bounds = boundaries_from_raw(df.index.values, df[NDVI_RAW_FIELD].values, max_gap_sec)
            segments = list(iter_segments_from_boundaries(ts_all, vals_all, raw_bounds))
        else:
            # Fallback when raw column is unavailable (e.g. GEE-derived sources)
            from lensky_py_lab.gap_utils import iter_gap_segments
            segments = list(iter_gap_segments(ts_all, vals_all, max_gap_sec))
    else:
        segments = [(ts_all, vals_all)]

    if not segments:
        df[NDVI_LOWESS_FIELD] = None
        return df

    lowess_ts: list = []
    lowess_vals: list = []

    for ts_seg, vals_seg in segments:
        n = len(ts_seg)
        frac = float(config.images_per_month) / n
        if config.lowess_min_neighbors is not None:
            min_frac = float(config.lowess_min_neighbors) / n
            frac = max(frac, min_frac)
        frac = min(max(frac, 1e-4), 1.0)

        result = sm.nonparametric.lowess(vals_seg.tolist(), ts_seg.tolist(), frac=frac)
        lowess_ts.extend(int(row[0]) for row in result)
        lowess_vals.extend(row[1] for row in result)

    if config.general_factor is not None:
        lowess_vals = [v * config.general_factor for v in lowess_vals]

    lowess_df = pd.DataFrame(
        {NDVI_LOWESS_FIELD: lowess_vals},
        index=pd.Index(lowess_ts, name=df.index.name),
    )
    return df.join(lowess_df, how="left")
