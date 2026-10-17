"""Shared error metrics — the single RMSE implementation used across the package."""

from __future__ import annotations

import numpy as np


def rmse(predicted, actual) -> float:
    """Root-mean-square error, ignoring positions where either input is NaN."""
    diff = np.asarray(predicted, dtype=float) - np.asarray(actual, dtype=float)
    return float(np.sqrt(np.nanmean(diff ** 2)))
