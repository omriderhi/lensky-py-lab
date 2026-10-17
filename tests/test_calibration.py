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
    create_calibration_figure,
    set_active_factor,
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
    def test_default_factor_is_active_factor(self, nsrs3_raw):
        set_active_factor(1.37)
        corrected = apply_calibration(nsrs3_raw)
        expected = nsrs3_raw * 1.37
        pd.testing.assert_series_equal(corrected, expected.rename(corrected.name))

    def test_no_factor_raises(self, nsrs3_raw, monkeypatch):
        monkeypatch.setattr("lensky_py_lab.sensors.nsrs_calibration._active_factor", None)
        with pytest.raises(ValueError, match="No calibration factor"):
            apply_calibration(nsrs3_raw)

    def test_custom_factor(self, nsrs3_raw):
        corrected = apply_calibration(nsrs3_raw, factor=1.2)
        pd.testing.assert_series_equal(
            corrected,
            (nsrs3_raw * 1.2).rename(corrected.name),
        )

    def test_output_name_has_corrected_suffix(self, nsrs3_raw):
        corrected = apply_calibration(nsrs3_raw, factor=1.4)
        assert "corrected" in str(corrected.name).lower()

    def test_index_preserved(self, nsrs3_raw):
        corrected = apply_calibration(nsrs3_raw, factor=1.4)
        pd.testing.assert_index_equal(corrected.index, nsrs3_raw.index)

    def test_values_greater_than_raw(self, nsrs3_raw):
        """Since factor > 1, corrected values should exceed raw."""
        corrected = apply_calibration(nsrs3_raw, factor=1.4)
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


# ---------------------------------------------------------------------------
# Tests — calibrate_nsrs3_sources (factor derived from data, applied to sources)
# ---------------------------------------------------------------------------


class TestCalibrateNsrs3Sources:
    def test_derives_and_applies_factor(self, nsrs3_raw, reference):
        from types import SimpleNamespace

        from lensky_py_lab.constants import NDVI_LOWESS_FIELD
        from lensky_py_lab.sensors.nsrs_calibration import (
            calibrate_nsrs3_sources,
            get_active_factor,
        )

        def src(name, series):
            df = pd.DataFrame({NDVI_LOWESS_FIELD: series})
            return SimpleNamespace(
                processed=df,
                lowess_series=df[NDVI_LOWESS_FIELD].rename(f"{NDVI_LOWESS_FIELD} {name}"),
            )

        s3 = src("NSRS_3", nsrs3_raw)
        sources = {
            "NSRS_1": src("NSRS_1", reference),
            "NSRS_2": src("NSRS_2", reference),
            "NSRS_3": s3,
        }
        before = nsrs3_raw.copy()
        result, raw = calibrate_nsrs3_sources(sources)

        factor = result["optimal_factor"]
        assert get_active_factor() == pytest.approx(factor)
        assert factor == pytest.approx(1.4, abs=0.2)
        pd.testing.assert_series_equal(raw, before.rename("NSRS_3_raw"))
        np.testing.assert_allclose(
            s3.processed[NDVI_LOWESS_FIELD].values, before.values * factor
        )


class TestCalibrationFigurePanelA:
    def _gapped_data(self):
        # two coverage windows separated by a 200-day hole
        day = 86400
        t0 = int(pd.Timestamp("2019-01-01").timestamp())
        idx = [t0 + i * day for i in range(100)] + [t0 + (300 + i) * day for i in range(100)]
        ref = pd.Series(0.55 + 0.1 * np.sin(np.arange(200) / 10), index=idx, name="ref")
        raw = (ref / 1.4).rename("raw")
        return raw, ref

    def test_panel_a_keeps_observations_and_breaks_at_gap(self, tmp_path):
        import matplotlib.pyplot as plt

        raw, ref = self._gapped_data()
        fig = create_calibration_figure(raw, ref, ref, output_dir=tmp_path)
        lines = {ln.get_label(): ln.get_ydata() for ln in fig.axes[0].get_lines()}
        for label in ("NSRS_1", "NSRS_3 raw"):
            y = np.asarray(lines[label], dtype=float)
            assert np.isfinite(y).sum() == 200          # no resampling or dropped points
            assert np.isnan(y).sum() == 1               # exactly one break (the gap)
        corrected = [v for k, v in lines.items() if k.startswith("NSRS_3 corrected")][0]
        raw_nan = np.where(np.isnan(np.asarray(lines["NSRS_3 raw"], dtype=float)))[0]
        corr_nan = np.where(np.isnan(np.asarray(corrected, dtype=float)))[0]
        assert list(raw_nan) == list(corr_nan)          # raw and corrected break together
        plt.close(fig)


class TestCalibrationIsOptional:
    @staticmethod
    def _src(name, series):
        from types import SimpleNamespace

        from lensky_py_lab.constants import NDVI_LOWESS_FIELD

        df = pd.DataFrame({NDVI_LOWESS_FIELD: series})
        return SimpleNamespace(
            processed=df,
            lowess_series=df[NDVI_LOWESS_FIELD].rename(f"{NDVI_LOWESS_FIELD} {name}"),
        )

    def test_clear_active_factor(self):
        from lensky_py_lab.sensors.nsrs_calibration import (
            clear_active_factor,
            get_active_factor,
        )

        set_active_factor(1.2)
        clear_active_factor()
        assert get_active_factor() is None

    def test_missing_sensors_raises_value_error_and_leaves_data_untouched(self, nsrs3_raw):
        from lensky_py_lab.constants import NDVI_LOWESS_FIELD
        from lensky_py_lab.sensors.nsrs_calibration import calibrate_nsrs3_sources

        s3 = self._src("NSRS_3", nsrs3_raw)
        with pytest.raises(ValueError, match="missing columns"):
            calibrate_nsrs3_sources({"NSRS_3": s3})
        pd.testing.assert_series_equal(
            s3.processed[NDVI_LOWESS_FIELD], nsrs3_raw.rename(NDVI_LOWESS_FIELD)
        )

    def test_applying_twice_is_refused(self, nsrs3_raw):
        from lensky_py_lab.sensors.nsrs_calibration import apply_nsrs3_factor

        sources = {"NSRS_3": self._src("NSRS_3", nsrs3_raw)}
        apply_nsrs3_factor(sources, 1.4)
        with pytest.raises(ValueError, match="already calibrated"):
            apply_nsrs3_factor(sources, 1.4)

    def test_logger_ndvi_uncalibrated_without_factor(self):
        from lensky_py_lab.sensors.daily_graphs import get_logger_ndvi
        from lensky_py_lab.sensors.nsrs_calibration import clear_active_factor

        clear_active_factor()
        df = pd.DataFrame({"NDVI_3_Avg": [0.2, 0.3]})
        pd.testing.assert_series_equal(
            get_logger_ndvi(df, 3), df["NDVI_3_Avg"].rename("NDVI_3_logger")
        )
