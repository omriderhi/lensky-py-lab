"""Rules deciding whether a satellite source takes part in the analysis.

A source is judged against a reference window (the period the NSRS ground sensors
observed), using only how much valid data it has there. The rules look at the data
after the extreme-value filter and before the outlier filter, so the verdict does
not depend on the outlier-filter settings or on any phenology result.

Rules (all must hold; thresholds are judgment calls, see ``EligibilityRules``):

1. ``min_valid_dates`` - distinct valid observation dates inside the reference window.
2. ``min_month_coverage`` - fraction of calendar months in the window with at least
   one valid observation.
3. ``min_peak_season_dates`` - in every peak season (1 Dec - 31 Mar) that lies wholly
   inside the window, at least this many distinct valid dates. Rules 1-2 count dates and
   months, not whether the season that carries the seasonal maximum is sampled; a source
   with enough dates overall but almost none in winter (e.g. Landsat-8 behind a < 10 %
   cloud filter) would otherwise pass and produce peak markers that are not seasonal
   peaks. Not evaluated when no complete peak season lies inside the window.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from lensky_py_lab.constants import NDVI_FILTERED_FIELD, NDVI_LOWESS_FIELD


@dataclass(frozen=True)
class EligibilityRules:
    """Thresholds for :func:`check_source_eligibility`.

    Defaults: at least 40 valid dates in the window (about 1.5 per month over the
    two-year RH NSRS record, enough to follow a seasonal curve and to form paired
    comparisons with the ground sensors) and valid data in at least 60 % of months.
    The peak-season rule needs at least 5 valid dates in each 1 Dec - 31 Mar of the
    window; RH counts (2019/20, 2020/21) were MODIS 59 / 79, S2 8 / 11, L8 2 / 3, so 5
    sits between S2 and L8 without being close to either - but it was set after seeing
    them. These are judgment calls, chosen once the RH data had been seen; state them in
    the Methods and change them only with a reason, not to rescue a source.
    """

    min_valid_dates: int = 40
    min_month_coverage: float = 0.60
    min_peak_season_dates: int = 5   # 0 switches rule 3 off


def reference_window(reference_sources: Dict[str, "object"]) -> Tuple[int, int]:
    """First and last timestamp at which any reference (NSRS) source has a smoothed value."""
    stamps = []
    for src in reference_sources.values():
        s = src.processed[NDVI_LOWESS_FIELD].dropna()
        if len(s):
            stamps += [int(s.index.min()), int(s.index.max())]
    if not stamps:
        raise ValueError("reference sources contain no smoothed values")
    return min(stamps), max(stamps)


def check_source_eligibility(
    name: str,
    processed: pd.DataFrame,
    window: Tuple[int, int],
    rules: EligibilityRules = EligibilityRules(),
) -> dict:
    """Evaluate one processed source; returns a row of measures, verdicts and reasons."""
    t0, t1 = window
    v = pd.to_numeric(processed[NDVI_FILTERED_FIELD], errors="coerce").dropna()
    v = v[(v.index >= t0) & (v.index <= t1)]
    n_dates = int(len(pd.unique(v.index)))
    months = pd.period_range(pd.to_datetime(t0, unit="s"), pd.to_datetime(t1, unit="s"), freq="M")
    have = set(pd.to_datetime(v.index, unit="s").to_period("M"))
    coverage = len(have & set(months)) / len(months)

    # rule 3: distinct valid dates in each complete peak season (1 Dec - 31 Mar) inside the window
    w0, w1 = pd.to_datetime(t0, unit="s"), pd.to_datetime(t1, unit="s")
    day = pd.DatetimeIndex(pd.to_datetime(v.index, unit="s").normalize()).unique()
    season_counts = []
    for y in range(w0.year - 1, w1.year + 1):
        s0, s1 = pd.Timestamp(y, 12, 1), pd.Timestamp(y + 1, 3, 31, 23, 59, 59)
        if s0 >= w0 and s1 <= w1:
            season_counts.append(int(((day >= s0) & (day <= s1)).sum()))
    peak_min = min(season_counts) if season_counts else None

    reasons = []
    if rules.min_peak_season_dates and peak_min is not None and peak_min < rules.min_peak_season_dates:
        reasons.append(
            f"only {peak_min} valid dates in the sparsest peak season (1 Dec - 31 Mar) < {rules.min_peak_season_dates}")
    if n_dates < rules.min_valid_dates:
        reasons.append(f"{n_dates} valid dates in window < {rules.min_valid_dates}")
    if coverage < rules.min_month_coverage:
        reasons.append(f"month coverage {coverage:.2f} < {rules.min_month_coverage:.2f}")
    return {
        "source": name,
        "valid_dates_in_window": n_dates,
        "month_coverage": round(float(coverage), 3),
        "min_dates_in_peak_season": peak_min,
        "eligible": not reasons,
        "reasons": "; ".join(reasons),
    }


def evaluate_eligibility(
    sources: Dict[str, "object"],
    reference_sources: Dict[str, "object"],
    rules: EligibilityRules = EligibilityRules(),
) -> pd.DataFrame:
    """One row per source in ``sources``, judged over the reference sources' window."""
    window = reference_window(reference_sources)
    rows = [check_source_eligibility(n, s.processed, window, rules) for n, s in sources.items()]
    return pd.DataFrame(rows)
