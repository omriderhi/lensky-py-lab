"""Rules deciding whether a satellite source takes part in the analysis.

A source is judged against a reference window (the period the NSRS ground sensors
observed), using only how much valid data it has there. The rules look at the data
after the extreme-value filter and before the outlier filter, so the verdict does
not depend on the outlier-filter settings or on any phenology result.

Rules (all must hold; thresholds are judgment calls, see ``EligibilityRules``):

1. ``min_valid_dates`` - distinct valid observation dates inside the reference window.
2. ``min_month_coverage`` - fraction of calendar months in the window with at least
   one valid observation.
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
    These are judgment calls, chosen once the RH data had been seen; state them in
    the Methods and change them only with a reason, not to rescue a source.
    """

    min_valid_dates: int = 40
    min_month_coverage: float = 0.60


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

    reasons = []
    if n_dates < rules.min_valid_dates:
        reasons.append(f"{n_dates} valid dates in window < {rules.min_valid_dates}")
    if coverage < rules.min_month_coverage:
        reasons.append(f"month coverage {coverage:.2f} < {rules.min_month_coverage:.2f}")
    return {
        "source": name,
        "valid_dates_in_window": n_dates,
        "month_coverage": round(float(coverage), 3),
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
