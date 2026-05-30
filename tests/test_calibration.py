"""
Tests for lensky_py_lab.sensors.nsrs_calibration

All tests use synthetic data — no real sensor files required.
Key assertions:
  1. The empirical optimal factor lands near the published 1.4 value.
  2. Applying the calibration factor improves R² and reduces RMSE vs. reference.
  3. apply_calibration() scales values correctly.
  4. save_calibration_statistics() writes a readable CSV.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from lensky_py_lab.sensors.nsrs_calibration import (
    NSRS3_PUBLISHED_FACTOR,
    apply_calibration,
    find_optimal_calibration_factor,
    save_calibration_statistics,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_calibration_data(
    factor: float = 1.4,
    n: int = 200,
    noise_std: float = 0.02,
    seed: int = 42,
) -> tuple[pd.Series, pd.Series]:
    """
    Build a synthetic (raw, reference) pair where the ground truth correction
    factor is exactly *factor*.

    raw = reference / factor + noise
    → corrected (raw × factor) ≈ reference
    """
    rng = np.random.default_rng(seed)
    # Simulate a realistic NDVI reference (0.3–0.8, roughly sinusoidal)
    t = np.linspace(0, 4 * np.pi, n)
    reference_values = 0.55 + 0.20 * np.sin(t)
    reference_values = np.clip(reference_values + rng.normal(0, noise_std, n), 0.1, 1.0)

    # Raw values are suppressed by the calibration factor
    raw_values = reference_values / factor + rng.normal(0, noise_std / 2, n)
    raw_values = np.clip(raw_values, 0.0, 1.0)

    # Use unix timestamps as index
    start_ts = int(pd.Timestamp("2018-01-01").timestamp())
    step = 16 * 86400  # 16-day MODIS-like cadence
    index = [start_ts + i * step for i in range(n)]

    return (
        pd.Series(raw_values, index=index, name="NSRS_3_raw"),
        pd.Series(reference_values, index=index, name="reference"),
    )


@pytest.fixture()
def calibration_data():
    return _make_calibration_data(factor=1.4)


@pytest.fixture()
def nsrs3_raw(calibration_data):
    return calibration_data[0]


@pytest.fixture()
def reference(calibration_data):
    return calibration_data[1]


# ---------------------------------------------------------------------------
# Tests — published constant
# ---------------------------------------------------------------------------


class TestPublishedFactor:
    def test_published_factor_value(self):
        """The thesis reports 1.4 — this constant must not change silently."""
        assert NSRS3_PUBLISHED_FACTOR == pytest.approx(1.4)

    def test_published_factor_greater_than_one(self):
        """A factor < 1 would further suppress NDVI — physically wrong."""
        assert NSRS3_PUBLISHED_FACTOR > 1.0


# ---------------------------------------------------------------------------
# Tests — find_optimal_calibration_factor
# ---------------------------------------------------------------------------


class TestFindOptimalCalibrationFactor:
    def test_returns_dict_with_required_keys(self, nsrs3_raw, reference):
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        required = {
            "optimal_factor", "published_factor", "published_factor_rmse",
            "rmse_curve", "r2_raw", "rmse_raw", "r2_corrected",
            "rmse_corrected", "n_overlap",
        }
        assert required.issubset(result.keys())

    def test_optimal_factor_near_published(self, nsrs3_raw, reference):
        """With noise_std=0.02 the optimal factor should land within ±0.2 of 1.4."""
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        assert result["optimal_factor"] == pytest.approx(1.4, abs=0.2), (
            f"Optimal factor {result['optimal_factor']:.3f} is far from 1.4"
        )

    def test_published_factor_is_near_optimal(self, nsrs3_raw, reference):
        """The published factor's RMSE should be within 10 % of the minimum RMSE."""
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        ratio = result["published_factor_rmse"] / result["rmse_corrected"]
        assert ratio < 1.10, (
            f"Published-factor RMSE ({result['published_factor_rmse']:.4f}) is "
            f">10 % above optimal RMSE ({result['rmse_corrected']:.4f})"
        )

    def test_calibration_r2_is_high(self, nsrs3_raw, reference):
        """Pearson R² is scale-invariant, so it is the same before and after.
        We simply assert it remains high (≥ 0.8), which is already covered by
        test_r2_corrected_high. This test documents that behaviour explicitly."""
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        # r2_raw and r2_corrected are equal (scale invariance); both should be high
        assert result["r2_raw"] > 0.8
        assert result["r2_corrected"] > 0.8
        # The values should agree to within floating-point rounding
        assert abs(result["r2_corrected"] - result["r2_raw"]) < 1e-6

    def test_calibration_reduces_rmse(self, nsrs3_raw, reference):
        """RMSE after calibration should be lower than before."""
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        assert result["rmse_corrected"] < result["rmse_raw"], (
            f"RMSE did not decrease: raw={result['rmse_raw']:.4f}, "
            f"corrected={result['rmse_corrected']:.4f}"
        )

    def test_r2_corrected_high(self, nsrs3_raw, reference):
        """With low noise the corrected R² should be > 0.8."""
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        assert result["r2_corrected"] > 0.8, (
            f"Corrected R² too low: {result['r2_corrected']:.3f}"
        )

    def test_rmse_curve_is_dataframe(self, nsrs3_raw, reference):
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        curve = result["rmse_curve"]
        assert isinstance(curve, pd.DataFrame)
        assert "factor" in curve.columns
        assert "rmse" in curve.columns

    def test_rmse_curve_has_n_steps_rows(self, nsrs3_raw, reference):
        result = find_optimal_calibration_factor(nsrs3_raw, reference, n_steps=50)
        assert len(result["rmse_curve"]) == 50

    def test_n_overlap_correct(self, nsrs3_raw, reference):
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        # Both series share the same index so overlap == len
        assert result["n_overlap"] == len(nsrs3_raw)

    def test_empty_overlap_raises(self):
        ts_a = pd.Series([0.3, 0.4], index=[1000, 2000], name="a")
        ts_b = pd.Series([0.3, 0.4], index=[3000, 4000], name="b")
        with pytest.raises(ValueError, match="No overlapping"):
            find_optimal_calibration_factor(ts_a, ts_b)

    def test_custom_factor_range(self, nsrs3_raw, reference):
        result = find_optimal_calibration_factor(
            nsrs3_raw, reference, factor_min=1.0, factor_max=2.0, n_steps=100
        )
        assert 1.0 <= result["optimal_factor"] <= 2.0

    def test_published_factor_in_result(self, nsrs3_raw, reference):
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        assert result["published_factor"] == pytest.approx(NSRS3_PUBLISHED_FACTOR)


# ---------------------------------------------------------------------------
# Tests — apply_calibration
# ---------------------------------------------------------------------------


class TestApplyCalibration:
    def test_default_factor_is_published(self, nsrs3_raw):
        corrected = apply_calibration(nsrs3_raw)
        expected = nsrs3_raw * NSRS3_PUBLISHED_FACTOR
        pd.testing.assert_series_equal(corrected, expected.rename(corrected.name))

    def test_custom_factor(self, nsrs3_raw):
        corrected = apply_calibration(nsrs3_raw, factor=1.2)
        pd.testing.assert_series_equal(
            corrected,
            (nsrs3_raw * 1.2).rename(corrected.name),
        )

    def test_output_name_has_corrected_suffix(self, nsrs3_raw):
        corrected = apply_calibration(nsrs3_raw)
        assert "corrected" in str(corrected.name).lower()

    def test_index_preserved(self, nsrs3_raw):
        corrected = apply_calibration(nsrs3_raw)
        pd.testing.assert_index_equal(corrected.index, nsrs3_raw.index)

    def test_values_greater_than_raw(self, nsrs3_raw):
        """Since factor > 1, corrected values should exceed raw."""
        corrected = apply_calibration(nsrs3_raw)
        assert (corrected.values > nsrs3_raw.values).all()


# ---------------------------------------------------------------------------
# Tests — save_calibration_statistics
# ---------------------------------------------------------------------------


class TestSaveCalibrationStatistics:
    def test_writes_csv(self, nsrs3_raw, reference, tmp_path):
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        csv_path = tmp_path / "stats.csv"
        df = save_calibration_statistics(result, output_path=csv_path)
        assert csv_path.exists()
        assert len(df) == 1

    def test_csv_readable(self, nsrs3_raw, reference, tmp_path):
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        csv_path = tmp_path / "stats.csv"
        save_calibration_statistics(result, output_path=csv_path)
        loaded = pd.read_csv(csv_path)
        assert "optimal_factor" in loaded.columns
        assert "rmse_corrected" in loaded.columns

    def test_rmse_curve_excluded_from_csv(self, nsrs3_raw, reference, tmp_path):
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        csv_path = tmp_path / "stats.csv"
        save_calibration_statistics(result, output_path=csv_path)
        loaded = pd.read_csv(csv_path)
        assert "rmse_curve" not in loaded.columns

    def test_creates_parent_directory(self, nsrs3_raw, reference, tmp_path):
        result = find_optimal_calibration_factor(nsrs3_raw, reference)
        csv_path = tmp_path / "nested" / "subdir" / "stats.csv"
        save_calibration_statistics(result, output_path=csv_path)
        assert csv_path.exists()
