"""
Module: daily_graphs.py
Description: Intra-day NSRS sensor analysis and visualization.
             Reads 1-minute resolution Campbell datalogger records (raw .dat
             files or the seasonal Excel workbook) and produces daily NDVI
             figures that replicate the Excel daily-graphs workbook.
Author: Omri Derhi
Institution: Bar-Ilan University
Date: 2025

Sensor architecture
-------------------
The Ramat HaNadiv NSRS setup has three sensors mounted on a pole:

  Sensor 1  — full 4-channel unit
      DownNIR_1  downwelling irradiance, NIR band  (reflected from vegetation)
      UpNIR_1    upwelling irradiance,   NIR band  (incoming from sky)
      DownRed_1  downwelling irradiance, Red band
      UpRed_1    upwelling irradiance,   Red band

  Sensors 2, 3  — 2-channel units (downwelling only)
      DownNIR_2/3  downwelling NIR (reflected from vegetation)
      DownRed_2/3  downwelling Red
      No dedicated sky-reference channels; they share Sensor 1's Up channels.

NDVI formula (identical for all three, verified against Excel values):
    rho_NIR_k = DownNIR_k / UpNIR_1          # NIR reflectance
    rho_Red_k = DownRed_k / UpRed_1          # Red reflectance
    NDVI_k    = (rho_NIR_k - rho_Red_k)
              / (rho_NIR_k + rho_Red_k)

This matches the pre-computed NDVI_k_Avg columns stored by the Campbell
datalogger to within floating-point rounding (~1e-5).

Acquisition window
------------------
"From before sunrise till noon" (per published research reports).
Implemented via DownNIR_1_Avg > 1e-4 W/m² nm⁻¹ sr⁻¹ AND hour ≤ noon.

Usage
-----
    # --- in the script (preprocessing, outside the package) ---
    from lensky_py_lab.sensors.daily_graphs import load_dat_dir
    df = load_dat_dir("path/to/RH_data_collections", recursive=True)

    # --- in the package / analysis code ---
    from lensky_py_lab.sensors.daily_graphs import (
        extract_day,
        get_logger_ndvi,
        compute_ndvi_all_sensors,
        plot_daily_ndvi,
        plot_daily_bands,
        plot_daily_summary,
        generate_daily_outputs,
    )

    day = extract_day(df, "2021-01-04")
    fig = plot_daily_ndvi(day, "2021-01-04")  # use_logger_ndvi=True by default
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Attempt to load shared plot_config from repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from plot_config import COLORS, apply_publication_style  # type: ignore[import]
    apply_publication_style()
    _HAS_PLOT_CONFIG = True
except ImportError:
    _HAS_PLOT_CONFIG = False
    COLORS: Dict[str, str] = {
        "nsrs1": "#e377c2",
        "nsrs2": "#7f7f7f",
        "nsrs3_corrected": "#17becf",
    }

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Band columns for each sensor (None = uses Sensor 1's Up channel as reference)
_BAND_COLS = {
    1: {"down_nir": "DownNIR_1_Avg", "up_nir":   "UpNIR_1_Avg",
        "down_red": "DownRed_1_Avg", "up_red":   "UpRed_1_Avg"},
    2: {"down_nir": "DownNIR_2_Avg", "up_nir":   "UpNIR_1_Avg",   # shared ref
        "down_red": "DownRed_2_Avg", "up_red":   "UpRed_1_Avg"},   # shared ref
    3: {"down_nir": "DownNIR_3_Avg", "up_nir":   "UpNIR_1_Avg",   # shared ref
        "down_red": "DownRed_3_Avg", "up_red":   "UpRed_1_Avg"},   # shared ref
}

_NDVI_COLS   = {1: "NDVI_1_Avg", 2: "NDVI_2_Avg", 3: "NDVI_3_Avg"}

_SENSOR_COLORS = {
    1: COLORS.get("nsrs1",           "#e377c2"),
    2: COLORS.get("nsrs2",           "#7f7f7f"),
    3: COLORS.get("nsrs3_corrected", "#17becf"),
}

# Semantic labels and colors matching the original research script
_SENSOR_LABELS = {1: "Herbaceous", 2: "Woody", 3: "Mixed"}
_SENSOR_COLORS_SEMANTIC = {1: "green", 2: "brown", 3: "blue"}

# Logger NDVI — pre-computed by Campbell datalogger, used as primary source
_LOGGER_NDVI_COLS = {1: "NDVI_1_Avg", 2: "NDVI_2_Avg", 3: "NDVI_3_Avg"}
_NSRS3_CALIBRATION_FACTOR = 1.4  # NSRS_3 wide-angle correction (Derhi 2025)

_DAYLIGHT_THRESHOLD   = 1e-4   # W/m² nm⁻¹ sr⁻¹ — minimum DownNIR to count as daylight
ACQUISITION_NOON_CUTOFF = 12   # last hour (inclusive) per research protocol

_SEASON_MAP = {
    1: "Winter", 2: "Winter", 3: "Spring",
    4: "Spring", 5: "Spring", 6: "Summer",
    7: "Summer", 8: "Summer", 9: "Autumn",
    10: "Autumn", 11: "Autumn", 12: "Winter",
}


# ---------------------------------------------------------------------------
# Campbell TOA5 .dat loader
# ---------------------------------------------------------------------------


def load_dat_file(dat_path: Union[str, Path]) -> pd.DataFrame:
    """Load a single Campbell TOA5 ``.dat`` file.

    TOA5 format: row 0 = station metadata, row 1 = column names,
    row 2 = units, row 3 = processing type. Data starts at row 4.

    Returns a minute-resolution DataFrame indexed by ``TIMESTAMP``.
    """
    df = pd.read_csv(
        dat_path,
        skiprows=[0, 2, 3],
        parse_dates=["TIMESTAMP"],
        quotechar='"',
        na_values=["NAN", "NaN", "nan"],
        low_memory=False,
    )
    df.columns = [c.strip().strip('"') for c in df.columns]
    return df.set_index("TIMESTAMP").sort_index()


def load_dat_dir(
    dat_dir: Union[str, Path],
    pattern: str = "*.dat",
    drop_duplicates: bool = True,
    recursive: bool = False,
) -> pd.DataFrame:
    """Load and concatenate all ``.dat`` files found in *dat_dir*.

    Parameters
    ----------
    dat_dir : str or Path
        Directory to search for Campbell ``.dat`` files.
    pattern : str
        Glob pattern (default ``"*.dat"``).
    drop_duplicates : bool
        Remove rows with duplicate TIMESTAMP (overlapping collection periods).
    recursive : bool
        When *True*, search the full directory tree (rglob). Use this when
        the data is organized across subdirectories (e.g. ``RH_data_collections``).

    Returns
    -------
    pd.DataFrame
        Combined, sorted DataFrame.

    Raises
    ------
    FileNotFoundError
        If *dat_dir* does not exist or contains no matching files.
    """
    dat_dir = Path(dat_dir)
    if not dat_dir.exists():
        raise FileNotFoundError(f"DAT directory not found: {dat_dir}")

    paths = sorted(dat_dir.rglob(pattern) if recursive else dat_dir.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No files matching '{pattern}' in {dat_dir}")

    frames = [load_dat_file(p) for p in paths]
    combined = pd.concat(frames).sort_index()
    if drop_duplicates:
        combined = combined[~combined.index.duplicated(keep="first")]
    return combined


def extract_day(
    df: pd.DataFrame,
    date: Union[str, pd.Timestamp],
    noon_cutoff: bool = True,
) -> pd.DataFrame:
    """Slice one calendar day and apply the acquisition window filter.

    Applies: daylight (DownNIR_1 > threshold) AND hour ≤ noon (if requested),
    matching the "from before sunrise till noon" protocol in the research reports.
    """
    date = pd.Timestamp(date).normalize()
    day  = df.loc[date: date + pd.Timedelta(hours=23, minutes=59, seconds=59)]

    # Daylight via irradiance proxy
    for col in ("DownNIR_1_Avg", "DownNIR_2_Avg", "DownNIR_3_Avg"):
        if col in day.columns:
            day = day[day[col].astype(float) > _DAYLIGHT_THRESHOLD]
            break

    if noon_cutoff:
        day = day[day.index.hour <= ACQUISITION_NOON_CUTOFF]

    return day


# ---------------------------------------------------------------------------
# Excel workbook loader (seasonal representative days)
# ---------------------------------------------------------------------------


def load_daily_excel(excel_path: Union[str, Path]) -> Dict[str, pd.DataFrame]:
    """Load all sheets from the seasonal daily-graphs Excel workbook.

    The Campbell datalogger splits date (TIMESTAMP) and time (TIME) into
    separate columns; they are recombined here into a minute-resolution index.
    Column names with surrounding quotes are stripped automatically.

    Returns
    -------
    dict of str → pd.DataFrame
        Sheet name → cleaned DataFrame with datetime index.
    """
    raw: Dict[str, pd.DataFrame] = pd.read_excel(
        Path(excel_path), sheet_name=None, header=0
    )
    cleaned: Dict[str, pd.DataFrame] = {}
    for sheet_name, df in raw.items():
        df = df.copy()
        df.columns = [c.strip().strip('"') for c in df.columns]

        if "TIMESTAMP" in df.columns and "TIME" in df.columns:
            date_part = pd.to_datetime(df["TIMESTAMP"], errors="coerce").dt.normalize()
            time_str  = df["TIME"].astype(str).str.strip()
            df.index  = pd.to_datetime(
                date_part.dt.strftime("%Y-%m-%d ") + time_str, errors="coerce"
            )
        elif "TIMESTAMP" in df.columns:
            df.index = pd.to_datetime(df["TIMESTAMP"], errors="coerce")
        elif "TIME" in df.columns:
            try:
                day = pd.to_datetime(sheet_name, format="%d_%m_%Y")
            except ValueError:
                day = pd.Timestamp.today().normalize()
            df.index = pd.to_datetime(
                day.strftime("%Y-%m-%d ") + df["TIME"].astype(str).str.strip(),
                errors="coerce",
            )

        drop_cols = [c for c in ("TIMESTAMP",) if c in df.columns]
        df = df.drop(columns=drop_cols).sort_index()

        if "TIME" in df.columns:
            df["TIME"] = df["TIME"].astype(str).str.strip().str[:5]

        cleaned[sheet_name] = df
    return cleaned


# ---------------------------------------------------------------------------
# NDVI computation — the formula from the Excel workbook
# ---------------------------------------------------------------------------


def compute_ndvi_from_bands(
    df: pd.DataFrame,
    sensor: int,
) -> Optional[pd.Series]:
    """Compute NDVI for one sensor from raw band irradiance columns.

    Implements the formula confirmed against the Excel daily-graph workbook
    (matches pre-computed NDVI_k_Avg to <1e-5):

        rho_NIR = DownNIR_k / UpNIR_1   (k = sensor number; sensors 2 & 3
        rho_Red = DownRed_k / UpRed_1    share Sensor 1's sky reference)
        NDVI    = (rho_NIR - rho_Red) / (rho_NIR + rho_Red)

    Parameters
    ----------
    df : pd.DataFrame
        Single-day or multi-day DataFrame from loader functions.
    sensor : int
        Sensor number: 1, 2, or 3.

    Returns
    -------
    pd.Series or None
        NDVI series, or *None* if any required column is absent.
    """
    cols = _BAND_COLS.get(sensor)
    if cols is None:
        return None

    required = [cols["down_nir"], cols["up_nir"], cols["down_red"], cols["up_red"]]
    if any(c not in df.columns for c in required):
        return None

    down_nir = df[cols["down_nir"]].astype(float)
    up_nir   = df[cols["up_nir"]].astype(float)
    down_red = df[cols["down_red"]].astype(float)
    up_red   = df[cols["up_red"]].astype(float)

    # Avoid division by zero or near-zero irradiance
    valid = (up_nir.abs() > 1e-12) & (up_red.abs() > 1e-12)
    rho_nir = (down_nir / up_nir).where(valid)
    rho_red = (down_red / up_red).where(valid)

    denom = rho_nir + rho_red
    ndvi  = ((rho_nir - rho_red) / denom.where(denom.abs() > 1e-12)).clip(-1.0, 1.0)
    ndvi.name = f"NDVI_{sensor}_computed"
    return ndvi


def compute_ndvi_all_sensors(df: pd.DataFrame) -> pd.DataFrame:
    """Compute NDVI for all three sensors and return as a single DataFrame.

    Each column is named ``NDVI_<k>_computed``.  Any sensor whose required
    columns are absent is silently omitted.

    Parameters
    ----------
    df : pd.DataFrame
        Single-day or multi-day DataFrame from loader functions.

    Returns
    -------
    pd.DataFrame
        Columns: ``NDVI_1_computed``, ``NDVI_2_computed``, ``NDVI_3_computed``
        (only those that could be computed).
    """
    series = {}
    for sensor in (1, 2, 3):
        ndvi = compute_ndvi_from_bands(df, sensor)
        if ndvi is not None:
            series[ndvi.name] = ndvi
    return pd.DataFrame(series, index=df.index)


def get_logger_ndvi(
    df: pd.DataFrame,
    sensor: int,
    apply_calibration: bool = True,
) -> Optional[pd.Series]:
    """Return the pre-computed ``NDVI_k_Avg`` column stored by the Campbell datalogger.

    This is the primary NDVI source — the values the logger computes on-device
    from raw band irradiance every minute.  NSRS_3 (Mixed sensor) is multiplied
    by ``_NSRS3_CALIBRATION_FACTOR`` (1.4) to correct for wide-angle lens tilt
    (Derhi 2025).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame from ``load_dat_file`` / ``load_dat_dir``.
    sensor : int
        Sensor number: 1, 2, or 3.
    apply_calibration : bool
        Apply ×1.4 correction to sensor 3 (default *True*).

    Returns
    -------
    pd.Series or None
        Logger NDVI series named ``NDVI_<k>_logger``, or *None* if the column
        is absent in *df*.
    """
    col = _LOGGER_NDVI_COLS.get(sensor)
    if col is None or col not in df.columns:
        return None
    s = df[col].astype(float).copy()
    if sensor == 3 and apply_calibration:
        s = s * _NSRS3_CALIBRATION_FACTOR
    s.name = f"NDVI_{sensor}_logger"
    return s


# ---------------------------------------------------------------------------
# Daylight helpers
# ---------------------------------------------------------------------------


def _daylight_mask(df: pd.DataFrame) -> pd.Series:
    """Boolean Series — True when DownNIR irradiance exceeds threshold."""
    for col in ("DownNIR_1_Avg", "DownNIR_2_Avg", "DownNIR_3_Avg", "UpNIR_1_Avg"):
        if col in df.columns:
            return df[col].astype(float) > _DAYLIGHT_THRESHOLD
    # Fallback: use pre-computed NDVI non-NaN as proxy
    for col in _NDVI_COLS.values():
        if col in df.columns:
            return df[col].notna()
    return pd.Series(True, index=df.index)


def _apply_noon(df: pd.DataFrame, noon_cutoff: bool) -> pd.DataFrame:
    if noon_cutoff:
        return df[df.index.hour <= ACQUISITION_NOON_CUTOFF]
    return df


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def plot_daily_ndvi(
    df: pd.DataFrame,
    label: str,
    figsize: Optional[Tuple[float, float]] = None,
    daylight_only: bool = True,
    noon_cutoff: bool = True,
    use_logger_ndvi: bool = True,
    acquisition_time: Optional[str] = "10:00",
) -> plt.Figure:
    """Plot NDVI time series for all three sensors over the acquisition window.

    When *use_logger_ndvi* is *True* (default): primary series are the logger's
    pre-computed ``NDVI_k_Avg`` columns (solid), labelled Herbaceous / Woody /
    Mixed.  Band-computed NDVI is shown as a dashed validation overlay.

    When *use_logger_ndvi* is *False*: the formula-computed NDVI from raw band
    irradiance is the primary series (original behaviour).

    Parameters
    ----------
    df : pd.DataFrame
        Single-day DataFrame indexed by ``datetime``.
    label : str
        Date label for title lookup (``"28_10_2019"`` or ``"2019-10-28"``).
    figsize : tuple, optional
    daylight_only : bool
        Restrict to rows where DownNIR_1 > irradiance threshold.
    noon_cutoff : bool
        Restrict to hours ≤ noon ("from before sunrise till noon").
    use_logger_ndvi : bool
        Use pre-computed logger ``NDVI_k_Avg`` as primary source (default *True*).
    """
    fig, ax = plt.subplots(figsize=figsize or (14, 5))

    sub = df[_daylight_mask(df)] if daylight_only else df
    sub = _apply_noon(sub, noon_cutoff)

    ndvi_computed = compute_ndvi_all_sensors(sub)

    for sensor in (1, 2, 3):
        col_c = f"NDVI_{sensor}_computed"

        if use_logger_ndvi:
            color = _SENSOR_COLORS_SEMANTIC[sensor]
            lbl   = _SENSOR_LABELS[sensor]
            # Logger NDVI — primary (solid)
            s_log = get_logger_ndvi(sub, sensor)
            if s_log is not None:
                s_log = s_log.dropna()
                if not s_log.empty:
                    ax.plot(s_log.index, s_log.values,
                            label=lbl, color=color, linewidth=1.8)
            # Band-computed NDVI — validation overlay (dashed)
            if col_c in ndvi_computed.columns:
                s_c = ndvi_computed[col_c].dropna()
                if not s_c.empty:
                    ax.plot(s_c.index, s_c.values,
                            color=color, linewidth=0.9, linestyle="--",
                            alpha=0.45, label=f"{lbl} (computed)")
        else:
            color = _SENSOR_COLORS[sensor]
            # Computed NDVI (solid — primary)
            if col_c in ndvi_computed.columns:
                s = ndvi_computed[col_c].dropna()
                if not s.empty:
                    ax.plot(s.index, s.values,
                            label=f"NSRS_{sensor}",
                            color=color, linewidth=1.8)
            # Pre-computed logger NDVI (dashed — validation)
            col_p = _NDVI_COLS[sensor]
            if col_p in sub.columns:
                s2 = sub[col_p].dropna()
                if not s2.empty:
                    ax.plot(s2.index, s2.values,
                            color=color, linewidth=0.9, linestyle="--",
                            alpha=0.45, label=f"NSRS_{sensor} (logger)")

    # Acquisition time marker
    if acquisition_time:
        try:
            _h, _m = map(int, acquisition_time.split(":"))
            _acq_dt = pd.Timestamp(label).normalize() + pd.Timedelta(hours=_h, minutes=_m)
            ax.axvline(_acq_dt, color="black", linewidth=1.5, linestyle=":",
                       alpha=0.75, zorder=5, label=f"Acquisition {acquisition_time}")
        except (ValueError, AttributeError):
            pass

    window_note = "sunrise → noon" if noon_cutoff else "full daylight"
    ax.annotate(f"Acquisition window: {window_note}",
                xy=(0.01, 0.02), xycoords="axes fraction",
                fontsize=7, color="gray", ha="left", va="bottom")

    title_date, title_season = _title_parts(label)
    ax.set_title(f"{title_date} — {title_season}  |  Intra-day NDVI",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Time of day", fontsize=11)
    ax.set_ylabel("NDVI", fontsize=11)
    ax.set_ylim(0, 1)
    # Deduplicate legend (computed sensors only)
    handles, labels_leg = ax.get_legend_handles_labels()
    seen, h_out, l_out = set(), [], []
    for h, l in zip(handles, labels_leg):
        if l not in seen:
            seen.add(l); h_out.append(h); l_out.append(l)
    ax.legend(h_out, l_out, loc="upper left", fontsize=9, framealpha=0.9)
    _format_time_axis(ax)
    fig.tight_layout()
    return fig


def plot_daily_bands(
    df: pd.DataFrame,
    label: str,
    sensor: int = 1,
    figsize: Optional[Tuple[float, float]] = None,
    daylight_only: bool = True,
    noon_cutoff: bool = True,
    use_logger_ndvi: bool = True,
) -> plt.Figure:
    """Two-panel figure: NIR (top) and Red (bottom) irradiance for one sensor.

    Both downwelling (vegetation-facing) and upwelling (sky-facing, if available)
    channels are shown.  Overlays NDVI on a secondary y-axis; when
    *use_logger_ndvi* is *True* uses the logger ``NDVI_k_Avg`` column (with
    NSRS_3 ×1.4 calibration), otherwise uses the band-computed formula.
    """
    cols = _BAND_COLS.get(sensor, {})
    sub  = df[_daylight_mask(df)] if daylight_only else df
    sub  = _apply_noon(sub, noon_cutoff)

    fig, (ax_nir, ax_red) = plt.subplots(2, 1, figsize=figsize or (14, 7), sharex=True)

    for ax, band, col_keys in [
        (ax_nir, "NIR", ("down_nir", "up_nir")),
        (ax_red, "Red", ("down_red", "up_red")),
    ]:
        for col_key in col_keys:
            col = cols.get(col_key)
            if col and col in sub.columns:
                vals  = sub[col].astype(float)
                valid = vals.notna()
                if valid.any():
                    direction = "Down" if "down" in col_key else "Up"
                    ax.plot(sub.index[valid], vals[valid],
                            label=f"{direction} {band}", linewidth=1.4)

        ax.set_ylabel(f"{band} irradiance (W m⁻² nm⁻¹ sr⁻¹)", fontsize=9)
        if ax.get_lines():
            ax.legend(fontsize=9)

        # Overlay NDVI on secondary axis
        if use_logger_ndvi:
            ndvi = get_logger_ndvi(sub, sensor)
        else:
            ndvi = compute_ndvi_from_bands(sub, sensor)
        if ndvi is not None and ndvi.notna().any():
            ax2 = ax.twinx()
            s = ndvi.dropna()
            ax2.plot(s.index, s.values, color="black",
                     linewidth=1.2, linestyle=":", alpha=0.6, label="NDVI")
            ax2.set_ylabel("NDVI", fontsize=8)
            ax2.set_ylim(0, 1)
            ax2.legend(fontsize=8, loc="upper right")

    ax_red.set_xlabel("Time of day", fontsize=10)
    title_date, title_season = _title_parts(label)
    fig.suptitle(
        f"NSRS_{sensor} Band Irradiance — {title_date} ({title_season})",
        fontsize=13, fontweight="bold",
    )
    _format_time_axis(ax_red)
    fig.tight_layout()
    return fig


def plot_daily_summary(
    sheets: Dict[str, pd.DataFrame],
    figsize: Optional[Tuple[float, float]] = None,
    noon_cutoff: bool = True,
    use_logger_ndvi: bool = True,
    acquisition_time: Optional[str] = "10:00",
) -> plt.Figure:
    """Grid figure: one subplot per seasonal representative day.

    Panels are arranged in a square grid (2×2 for four seasons).  All panels
    share the same time-of-day x-axis range so seasonal differences are directly
    comparable.  A vertical dotted line marks the satellite image acquisition time
    (default ``"10:00"``; pass *None* to suppress).

    When *use_logger_ndvi* is *True* (default): uses the pre-computed logger
    ``NDVI_k_Avg`` columns (Herbaceous / Woody / Mixed) with NSRS_3 ×1.4.
    When *False*: uses NDVI computed from raw band irradiance.
    """
    n = len(sheets)
    if n == 0:
        return plt.figure()

    nrows = math.ceil(math.sqrt(n))
    ncols = math.ceil(n / nrows)
    fig, axes = plt.subplots(nrows, ncols,
                             figsize=figsize or (5 * ncols, 5 * nrows),
                             squeeze=False)
    axes_flat = np.array(axes).flatten()

    # Hide unused cells in the grid
    for ax in axes_flat[n:]:
        ax.set_visible(False)

    active: List[Tuple[plt.Axes, str]] = []  # (ax, label) — used for x alignment

    for ax, (label, df) in zip(axes_flat[:n], sheets.items()):
        sub = df[_daylight_mask(df)]
        sub = _apply_noon(sub, noon_cutoff)

        if not use_logger_ndvi:
            ndvi_computed = compute_ndvi_all_sensors(sub)

        plotted = False
        for sensor in (1, 2, 3):
            if use_logger_ndvi:
                s = get_logger_ndvi(sub, sensor)
                if s is None:
                    continue
                s = s.dropna()
                color = _SENSOR_COLORS_SEMANTIC[sensor]
                lbl   = _SENSOR_LABELS[sensor]
            else:
                col = f"NDVI_{sensor}_computed"
                if col not in ndvi_computed.columns:
                    continue
                s = ndvi_computed[col].dropna()
                color = _SENSOR_COLORS[sensor]
                lbl   = f"NSRS_{sensor}"

            if s.empty:
                continue
            ax.plot(s.index, s.values, label=lbl, color=color, linewidth=1.5)
            plotted = True

        # Acquisition time marker
        if acquisition_time:
            try:
                _h, _m = map(int, acquisition_time.split(":"))
                _acq_dt = pd.Timestamp(label).normalize() + pd.Timedelta(hours=_h, minutes=_m)
                ax.axvline(_acq_dt, color="black", linewidth=1.5, linestyle=":",
                           alpha=0.75, zorder=5, label=f"Acquisition {acquisition_time}")
            except (ValueError, AttributeError):
                pass

        title_date, title_season = _title_parts(label)
        ax.set_title(f"{title_season}\n{title_date}", fontsize=11, fontweight="bold")
        ax.set_xlabel("Time", fontsize=9)
        ax.set_ylabel("NDVI", fontsize=9)
        ax.set_ylim(0, 1)
        if plotted:
            ax.legend(fontsize=8)
        _format_time_axis(ax, interval=2)
        active.append((ax, label))

    # Align all panels to the same time-of-day window
    if len(active) > 1:
        time_lims = []
        for ax, _ in active:
            lo = mdates.num2date(ax.get_xlim()[0])
            hi = mdates.num2date(ax.get_xlim()[1])
            time_lims.append((lo.hour + lo.minute / 60 + lo.second / 3600,
                               hi.hour + hi.minute / 60 + hi.second / 3600))
        global_lo = min(t[0] for t in time_lims) - 0.25  # 15 min padding
        global_hi = max(t[1] for t in time_lims) + 0.25
        for ax, label in active:
            date_ts = pd.Timestamp(label).normalize()
            ax.set_xlim(
                mdates.date2num(date_ts + pd.Timedelta(hours=global_lo)),
                mdates.date2num(date_ts + pd.Timedelta(hours=global_hi)),
            )

    window = "sunrise → noon" if noon_cutoff else "full daylight"
    fig.suptitle(f"Intra-day NDVI — Seasonal Representative Days  ({window})",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Output generators
# ---------------------------------------------------------------------------


def generate_daily_graph_outputs(
    excel_path: Union[str, Path],
    output_dir: Union[str, Path],
    dpi: int = 150,
    noon_cutoff: bool = True,
) -> List[Path]:
    """Generate all daily-graph figures from the seasonal Excel workbook.

    Produces (per acquisition window — sunrise → noon):
    * ``daily_ndvi_summary.png``   — 4-panel seasonal overview
    * ``<date>_ndvi.png``          — per-day NDVI (computed + logger)
    * ``<date>_bands_sensor1.png`` — NIR/Red irradiance for sensor 1
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sheets = load_daily_excel(excel_path)
    saved: List[Path] = []

    fig = plot_daily_summary(sheets, noon_cutoff=noon_cutoff)
    p   = output_dir / "daily_ndvi_summary.png"
    fig.savefig(p, dpi=dpi, bbox_inches="tight"); plt.close(fig); saved.append(p)

    for label, df in sheets.items():
        fig = plot_daily_ndvi(df, label, noon_cutoff=noon_cutoff)
        p   = output_dir / f"{label}_ndvi.png"
        fig.savefig(p, dpi=dpi, bbox_inches="tight"); plt.close(fig); saved.append(p)

        fig = plot_daily_bands(df, label, sensor=1, noon_cutoff=noon_cutoff)
        p   = output_dir / f"{label}_bands_sensor1.png"
        fig.savefig(p, dpi=dpi, bbox_inches="tight"); plt.close(fig); saved.append(p)

    return saved


def _pick_seasonal_dates(df: pd.DataFrame) -> List[pd.Timestamp]:
    """Pick one representative day per season from *df*'s actual date range.

    Only considers dates that have at least one non-null logger NDVI value
    (NDVI_1_Avg / NDVI_2_Avg / NDVI_3_Avg), so old files that predate the
    logger NDVI columns are automatically skipped.  Falls back to all dates
    if none have logger NDVI (e.g. data collected with raw bands only).

    Within each season, picks the date closest to its seasonal midpoint
    (Feb 1, Apr 15, Jul 15, Oct 15).
    """
    if df.empty or not hasattr(df.index, "date"):
        return []

    dti = pd.DatetimeIndex(df.index)

    # Restrict to dates that have at least one non-null logger NDVI row
    ndvi_cols = [c for c in _LOGGER_NDVI_COLS.values() if c in df.columns]
    if ndvi_cols:
        has_ndvi = df[ndvi_cols].notna().any(axis=1)
        dti = dti[has_ndvi.values]

    available_dates = sorted({d for d in dti.normalize().unique()})
    if not available_dates:
        return []

    _MONTH_SEASON = {
        12: "Winter", 1: "Winter", 2: "Winter",
        3: "Spring",  4: "Spring", 5: "Spring",
        6: "Summer",  7: "Summer", 8: "Summer",
        9: "Autumn", 10: "Autumn", 11: "Autumn",
    }
    # Midpoint of each season (month, day) — used to pick the closest date
    _SEASON_MID = {
        "Winter": (2, 1),
        "Spring": (4, 15),
        "Summer": (7, 15),
        "Autumn": (10, 15),
    }

    # Group available dates by season
    by_season: dict = {}
    for d in available_dates:
        season = _MONTH_SEASON[d.month]
        by_season.setdefault(season, []).append(d)

    picks = []
    for season in ["Winter", "Spring", "Summer", "Autumn"]:
        candidates = by_season.get(season)
        if not candidates:
            continue
        # Pick the candidate closest to the seasonal midpoint (any year)
        mid_month, mid_day = _SEASON_MID[season]
        def _dist(d):
            try:
                mid = d.replace(month=mid_month, day=mid_day)
            except ValueError:
                mid = d.replace(month=mid_month, day=28)
            return abs((d - mid).days)
        picks.append(min(candidates, key=_dist))

    if not picks:
        picks = [available_dates[len(available_dates) // 2]]
    return picks


def generate_daily_outputs(
    df: pd.DataFrame,
    output_dir: Union[str, Path],
    dates: Optional[List[Union[str, pd.Timestamp]]] = None,
    dpi: int = 150,
    noon_cutoff: bool = True,
    use_logger_ndvi: bool = True,
    acquisition_time: Optional[str] = "10:00",
) -> List[Path]:
    """Generate intra-day NDVI figures from a pre-loaded sensor DataFrame.

    Accepts a minute-resolution DataFrame (already loaded by the caller) and
    writes per-day NDVI figures plus a seasonal summary.  Loading raw ``.dat``
    files is the caller's responsibility — use ``load_dat_dir`` or build the
    DataFrame however suits your pipeline.

    If *dates* is omitted, representative days are auto-selected from the data
    (one per season, prioritising dates with valid logger NDVI).

    Parameters
    ----------
    df : pd.DataFrame
        Minute-resolution NSRS DataFrame indexed by ``datetime``.
    output_dir : str or Path
        Destination directory for output figures.
    dates : list, optional
        Calendar dates (strings or Timestamps) to plot.
    dpi : int
    noon_cutoff : bool
        Apply the "sunrise → noon" acquisition window (default *True*).
    use_logger_ndvi : bool
        Use pre-computed logger ``NDVI_k_Avg`` as primary NDVI source (default *True*).
    acquisition_time : str or None
        Time string ``"HH:MM"`` for the satellite image acquisition marker drawn
        on each daily figure (default ``"10:00"``).  Pass *None* to suppress.

    Returns
    -------
    list of Path
    """
    import warnings

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df_all = df

    if dates is None:
        dates = _pick_seasonal_dates(df)

    saved: List[Path] = []
    day_sheets: Dict[str, pd.DataFrame] = {}

    for date in dates:
        ts  = pd.Timestamp(date)
        day = extract_day(df_all, ts, noon_cutoff=noon_cutoff)

        if day.empty:
            warnings.warn(f"No data found for {ts.date()} — skipping.")
            continue

        label = ts.strftime("%Y-%m-%d")
        day_sheets[label] = day

        # NDVI figure
        fig = plot_daily_ndvi(day, label, noon_cutoff=False,
                              use_logger_ndvi=use_logger_ndvi,
                              acquisition_time=acquisition_time)
        p   = output_dir / f"{label}_ndvi.png"
        fig.savefig(p, dpi=dpi, bbox_inches="tight"); plt.close(fig); saved.append(p)

        # Band irradiance + NDVI overlay
        fig = plot_daily_bands(day, label, sensor=1, noon_cutoff=False,
                               use_logger_ndvi=use_logger_ndvi)
        p   = output_dir / f"{label}_bands_sensor1.png"
        fig.savefig(p, dpi=dpi, bbox_inches="tight"); plt.close(fig); saved.append(p)

    if day_sheets:
        fig = plot_daily_summary(day_sheets, noon_cutoff=False,
                                 use_logger_ndvi=use_logger_ndvi,
                                 acquisition_time=acquisition_time)
        p   = output_dir / "daily_ndvi_summary_dat.png"
        fig.savefig(p, dpi=dpi, bbox_inches="tight"); plt.close(fig); saved.append(p)

    return saved


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_time_axis(ax: plt.Axes, interval: int = 2) -> None:
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=interval))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)


def _title_parts(label: str) -> Tuple[str, str]:
    """Parse date label in any common format → (human date string, season)."""
    for fmt in ("%d_%m_%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            dt = pd.to_datetime(label, format=fmt)
            return dt.strftime("%b %d, %Y"), _SEASON_MAP.get(dt.month, "")
        except (ValueError, TypeError):
            continue
    try:
        dt = pd.to_datetime(label)
        return dt.strftime("%b %d, %Y"), _SEASON_MAP.get(dt.month, "")
    except Exception:
        return label, ""
