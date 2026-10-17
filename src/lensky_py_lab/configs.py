from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class SourceConfig:
    """Per-source cleaning and smoothing parameters.

    Attributes:
        min_value: Drop values below this threshold. None = use data minimum.
        max_value: Drop values above this threshold. None = use data maximum.
        outlier_window: Number of observations in the centred sliding window used
            for outlier detection (see ``filter_outliers_sliding_window``). A point
            is removed when it deviates from the window median by more than
            ``max(outlier_k × 1.4826 × MAD, outlier_min_threshold)``.
            None = skip outlier detection.
        outlier_k: Multiplier on the robust (MAD-based) local standard deviation.
        outlier_min_threshold: Floor of the removal threshold, in NDVI units.
        outlier_scale_window: Observations in the window over which the MAD of the
            residuals is taken.
        outlier_window_days: Half-width, in days, of a centred *calendar* window for
            ``filter_outliers_time_window`` (e.g. 15). Takes precedence over
            ``outlier_window`` when set. Suited to sparse satellite series, where
            N observations span very different time intervals per source.
        outlier_direction: ``"both"`` removes points above or below the window
            median; ``"down"`` removes only low outliers (cloud/atmosphere only push
            NDVI down). Applies to the time-window filter only.
        images_per_month: LOWESS smoothing bandwidth expressed as the typical number
            of observations per month (frac = images_per_month / N_non_null_points).
            None = skip smoothing.
        general_factor: Optional multiplicative scale applied to LOWESS output.
            None = no scaling.
        wide_gap_days: Gaps larger than this (in days) between consecutive clean
            observations cause LOWESS to be computed per segment independently.
            None disables gap-based segmentation (single LOWESS over all data).
            Default: 60 days (≈ 2 months).
        lowess_min_neighbors: When set, clamps the effective LOWESS neighbourhood
            so it always uses at least this many points (overrides frac when frac
            would use fewer). None = keep frac fixed regardless of segment length.
    """

    min_value: Optional[float] = None
    max_value: Optional[float] = None
    outlier_window: Optional[int] = None
    outlier_k: float = 3.0
    outlier_min_threshold: float = 0.02
    outlier_scale_window: int = 31
    outlier_window_days: Optional[int] = None
    outlier_direction: str = "both"
    images_per_month: Optional[int] = None
    general_factor: Optional[float] = None
    wide_gap_days: Optional[int] = 60
    lowess_min_neighbors: Optional[int] = None

    @classmethod
    def from_notebook_dict(cls, d: dict) -> SourceConfig:
        """Create from the notebook's SOURCES_CONFIGURATIONS format (False means None)."""

        if "average_window" in d:
            raise ValueError(
                "'average_window' was removed (it implemented a mean-deviation rule that "
                "kept outliers and discarded ordinary values). Use 'outlier_window' "
                "(observations in the sliding window, e.g. 7)."
            )

        def _parse(v: object) -> Optional[float]:
            return None if (v is False or v is None) else float(v)

        def _parse_int(v: object, default: Optional[int]) -> Optional[int]:
            return default if (v is False or v is None) else int(v)

        return cls(
            min_value=_parse(d.get("min")),
            max_value=_parse(d.get("max")),
            outlier_window=_parse_int(d.get("outlier_window"), None),
            outlier_k=float(d.get("outlier_k", 3.0)),
            outlier_min_threshold=float(d.get("outlier_min_threshold", 0.02)),
            outlier_scale_window=int(d.get("outlier_scale_window", 31)),
            outlier_window_days=_parse_int(d.get("outlier_window_days"), None),
            outlier_direction=str(d.get("outlier_direction", "both")),
            images_per_month=int(d["images_per_month"]) if d.get("images_per_month") else None,
            general_factor=_parse(d.get("general_factor")),
            wide_gap_days=_parse_int(d.get("wide_gap_days"), 60),
            lowess_min_neighbors=_parse_int(d.get("lowess_min_neighbors"), None),
        )
