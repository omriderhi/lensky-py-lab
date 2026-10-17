#!/usr/bin/env python
"""
Script: fov_canopy_fraction.py
Description: Reviewer comment [18] — what fraction of the NSRS_3 signal comes
             from the pine crown?  NSRS_3 is a downward-looking hemispherical
             (180 deg FOV, cosine-response) sensor.  For a cosine-response sensor
             viewing a horizontal surface, a ground patch contributes in
             proportion to its *projected solid angle*:

                 w(theta) dOmega = cos(theta) sin(theta) dtheta dphi / pi

             so the fraction of the signal coming from all directions with view
             zenith < theta0 is sin^2(theta0).  The crown is modelled as a
             horizontal disk (radius R, top at height h_crown) whose centre is a
             horizontal distance d from the point directly below the sensor
             (sensor height H).  The azimuth integral is analytic, leaving a
             1-D numerical integral over the view zenith.

Status: FIELD INPUTS STILL NEEDED (P5 item [9]) — the defaults below are
        placeholders, not measurements.  Do not quote the output until the
        numbers are replaced with the measured values.

Usage:
    python scripts/fov_canopy_fraction.py --sensor-height 6 --crown-top 5 \
        --crown-diameter 6 --offset 1.5
Author: Omri Derhi
Institution: Bar-Ilan University
"""
from __future__ import annotations

import argparse

import numpy as np


def crown_fraction(sensor_height: float, crown_top: float, crown_diameter: float,
                   offset: float = 0.0, n: int = 200_000) -> float:
    """Cosine-weighted fraction of a 180-deg downward FOV filled by the crown disk.

    The problem is axisymmetric about the sensor axis, so the azimuth integral is
    analytic: a ring of radius rho on the crown plane meets the disk (radius R,
    centre ``offset`` away) over an arc of angle ``2 * arccos((rho^2 + d^2 - R^2) / (2 rho d))``.
    Substituting u = sin^2(theta) (du = 2 cos sin dtheta) leaves a smooth 1-D integral

        f = 1 / (2 pi) * integral_0^1 arc(rho(u)) du,   rho = dz * sqrt(u / (1 - u)).
    """
    dz = sensor_height - crown_top
    if dz <= 0:
        raise ValueError("sensor must be mounted above the crown top")
    R, d = crown_diameter / 2, abs(offset)
    u = (np.arange(n) + 0.5) / n
    rho = dz * np.sqrt(u / (1 - u))
    if d == 0:
        arc = np.where(rho <= R, 2 * np.pi, 0.0)
    else:
        c = (rho ** 2 + d ** 2 - R ** 2) / (2 * rho * d)
        arc = 2 * np.arccos(np.clip(c, -1.0, 1.0))
    return float(arc.sum() / n / (2 * np.pi))


def closed_form_centred(sensor_height: float, crown_top: float, crown_diameter: float) -> float:
    """Check value for offset = 0: sin^2(atan(R/dz)) = R^2 / (R^2 + dz^2)."""
    R, dz = crown_diameter / 2, sensor_height - crown_top
    return R ** 2 / (R ** 2 + dz ** 2)


_PLACEHOLDERS = {"sensor_height": 6.0, "crown_top": 5.0, "crown_diameter": 6.0}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sensor-height", type=float, help="NSRS_3 height above ground [m] (placeholder if omitted)")
    p.add_argument("--crown-top", type=float, help="height of the crown top [m] (placeholder if omitted)")
    p.add_argument("--crown-diameter", type=float, help="crown diameter [m] (placeholder if omitted)")
    p.add_argument("--offset", type=float, default=0.0, help="horizontal sensor-to-crown-centre distance [m]")
    a = p.parse_args()

    used_placeholder = [k for k in _PLACEHOLDERS if getattr(a, k) is None]
    vals = {k: (_PLACEHOLDERS[k] if getattr(a, k) is None else getattr(a, k)) for k in _PLACEHOLDERS}

    if used_placeholder:
        print("!" * 70)
        print("PLACEHOLDER INPUTS, NOT MEASUREMENTS: " + ", ".join(used_placeholder))
        print("Do not quote this result. Supply the measured values with the flags above.")
        print("!" * 70)
    print(f"Inputs: sensor height {vals['sensor_height']} m, crown top {vals['crown_top']} m, "
          f"crown diameter {vals['crown_diameter']} m, offset {a.offset} m")

    f = crown_fraction(vals["sensor_height"], vals["crown_top"], vals["crown_diameter"], a.offset)
    print(f"Crown share of NSRS_3 signal: {100 * f:.1f} %  (cosine-weighted, 180 deg FOV)")
    if a.offset == 0:
        cf = closed_form_centred(vals["sensor_height"], vals["crown_top"], vals["crown_diameter"])
        print(f"closed-form check (offset 0): {100 * cf:.1f} %")
