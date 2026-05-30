from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class SourceConfig:
    """Per-source cleaning and smoothing parameters.

    Attributes:
        min_value: Drop values below this threshold. None = use data minimum.
        max_value: Drop values above this threshold. None = use data maximum.
        average_window: Outlier-emphasis filter tolerance. Values whose absolute
            deviation from their local neighbourhood mean is >= this threshold are
            retained; others are discarded. None = skip this filter step.
        images_per_month: LOWESS smoothing bandwidth expressed as the typical number
            of observations per month (frac = images_per_month / N_non_null_points).
            None = skip smoothing.
        general_factor: Optional multiplicative scale applied to LOWESS output.
            None = no scaling.
    """

    min_value: Optional[float] = None
    max_value: Optional[float] = None
    average_window: Optional[float] = None
    images_per_month: Optional[int] = None
    general_factor: Optional[float] = None

    @classmethod
    def from_notebook_dict(cls, d: dict) -> SourceConfig:
        """Create from the notebook's SOURCES_CONFIGURATIONS format (False means None)."""

        def _parse(v: object) -> Optional[float]:
            return None if (v is False or v is None) else float(v)

        return cls(
            min_value=_parse(d.get("min")),
            max_value=_parse(d.get("max")),
            average_window=_parse(d.get("average_window")),
            images_per_month=int(d["images_per_month"]) if d.get("images_per_month") else None,
            general_factor=_parse(d.get("general_factor")),
        )
