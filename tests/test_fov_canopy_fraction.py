"""Tests for scripts/fov_canopy_fraction.py (crown share of the NSRS_3 field of view)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

_SPEC = importlib.util.spec_from_file_location(
    "fov_canopy_fraction", Path(__file__).parents[1] / "scripts" / "fov_canopy_fraction.py"
)
fov = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fov)


def test_centred_matches_closed_form():
    f = fov.crown_fraction(6, 5, 6)
    assert f == pytest.approx(fov.closed_form_centred(6, 5, 6), abs=1e-4)
    assert f == pytest.approx(0.9, abs=1e-3)


def test_offset_reference_value():
    assert fov.crown_fraction(6, 5, 6, offset=2.0) == pytest.approx(0.777, abs=1e-3)


def test_monotone_in_offset_and_bounded():
    vals = [fov.crown_fraction(6, 5, 6, offset=d) for d in (0, 1, 2, 4, 8)]
    assert all(0 <= v <= 1 for v in vals)
    assert vals == sorted(vals, reverse=True)


def test_sensor_below_crown_top_raises():
    with pytest.raises(ValueError):
        fov.crown_fraction(5, 5, 6)


def test_matches_brute_force_grid():
    # independent 2-D check of the analytic azimuth integral
    n = 1500
    theta = (np.arange(n) + 0.5) / n * (np.pi / 2)
    phi = (np.arange(n) + 0.5) / n * (2 * np.pi)
    T, P = np.meshgrid(theta, phi, indexing="ij")
    rho = 1.0 * np.tan(T)
    inside = (rho * np.cos(P) - 1.5) ** 2 + (rho * np.sin(P)) ** 2 <= 3.0 ** 2
    brute = (np.cos(T) * np.sin(T) / np.pi * inside).sum() * (np.pi / 2 / n) * (2 * np.pi / n)
    assert fov.crown_fraction(6, 5, 6, offset=1.5) == pytest.approx(brute, abs=2e-3)
