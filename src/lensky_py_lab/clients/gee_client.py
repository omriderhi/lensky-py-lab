"""
Module: gee_client.py
Description: Google Earth Engine client for querying NDVI time-series.
             Implements the same logic as the research GEE JavaScript script
             (code.earthengine.google.com/07dc3e333b12fd831d0a902f5453b698).
Author: Omri Derhi
Institution: Bar-Ilan University
Date: 2025

Script-to-Python mapping
------------------------
The original JS script uses:

  MODIS     → MODIS/006/MOD09GQ  daily surface reflectance; NDVI from
              sur_refl_b02 (NIR) and sur_refl_b01 (Red) bands.
              Python uses the newer Collection-6.1 equivalent (061/MOD09GQ).

  Sentinel-2 → COPERNICUS/S2_SR with CLOUD_COVERAGE_ASSESSMENT < 10.
              Python uses the harmonised collection (S2_SR_HARMONIZED) which
              is preferred for long time-series (corrects the 2022 processing
              baseline shift); cloud property is CLOUDY_PIXEL_PERCENTAGE.

  Landsat-8  → LANDSAT/LC08/C01/T1_SR with CLOUD_COVER < 10.
              Python uses Collection-2 (C02/T1_L2) which is the current USGS
              standard; scale factors (0.0000275) and offset (-0.2) applied
              before NDVI to handle the C02 signed-reflectance convention;
              QA_PIXEL cloud/shadow masking added on top of the percentage
              pre-filter.

  NDVI mask  → maskLowValues: img.updateMask(img.gte(0.35))
              Implemented as the ``ndvi_min`` parameter (default 0.35).

  Reducer    → ee.Reducer.mean() over the AOI geometry at the sensor's
              native scale (10 m for S2, 250 m for MODIS, 30 m for L8).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from lensky_py_lab.constants import NDVI_RAW_FIELD, TIMESTAMP_FIELD, SatelliteSource

# ---------------------------------------------------------------------------
# Collection registry
# ---------------------------------------------------------------------------

#: GEE asset IDs — updated from the JS script to use current-generation
#: collections where a newer version exists.
_COLLECTIONS: Dict[SatelliteSource, str] = {
    # Daily surface reflectance (250 m) — replaces the 16-day MOD13Q1 used
    # in an earlier version of this client, matching the JS script intent.
    SatelliteSource.MODIS:     "MODIS/061/MOD09GQ",
    # Harmonised S2 SR — preferred over plain S2_SR for cross-year consistency.
    SatelliteSource.SENTINEL2: "COPERNICUS/S2_SR_HARMONIZED",
    # Collection-2 L8 SR — current USGS standard.
    SatelliteSource.LANDSAT8:  "LANDSAT/LC08/C02/T1_L2",
}

#: Pre-filter: (image-property name, maximum value).
#: Matches script: CLOUD_COVERAGE_ASSESSMENT < 10 for S2, CLOUD_COVER < 10 for L8.
_CLOUD_FILTER: Dict[SatelliteSource, tuple] = {
    SatelliteSource.SENTINEL2: ("CLOUDY_PIXEL_PERCENTAGE", 10),
    SatelliteSource.LANDSAT8:  ("CLOUD_COVER", 10),
}

#: Native spatial resolution [m] used as the default reducer scale.
_DEFAULT_SCALE: Dict[SatelliteSource, int] = {
    SatelliteSource.MODIS:     250,
    SatelliteSource.SENTINEL2: 10,
    SatelliteSource.LANDSAT8:  30,
}

#: Minimum NDVI threshold — pixels below this are masked out before the
#: spatial reducer, matching maskLowValues(img.gte(0.35)) in the JS script.
_NDVI_MIN_DEFAULT: float = 0.35


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GEEClient:
    """Google Earth Engine client for NDVI time-series extraction.

    Reproduces the logic of the research JS script for MODIS (MOD09GQ daily),
    Sentinel-2 (harmonised SR), and Landsat-8 (Collection-2 SR).

    Args:
        project: GEE Cloud project ID (required for API ≥ 0.1.370).
        credentials: Optional OAuth2 credentials. If *None*, Application
            Default Credentials are used (run ``earthengine authenticate``).

    Example — single source::

        client = GEEClient(project="my-gee-project")
        geometry = ee.Geometry.Point([34.946667, 32.555806])
        df = client.get_ndvi_timeseries(
            geometry, "2018-01-01", "2022-09-01",
            source=SatelliteSource.MODIS,
        )

    Example — all sources at once (mirrors the JS script)::

        frames = client.get_ndvi_timeseries_all(
            geometry, "2018-01-01", "2022-09-01",
        )
        modis_df    = frames[SatelliteSource.MODIS]
        sentinel_df = frames[SatelliteSource.SENTINEL2]
        landsat_df  = frames[SatelliteSource.LANDSAT8]
    """

    def __init__(
        self,
        project: Optional[str] = None,
        credentials: Optional[Any] = None,
    ) -> None:
        try:
            import ee as _ee
        except ImportError:
            raise ImportError(
                "earthengine-api is required for GEEClient. "
                "Install it with: pip install earthengine-api  "
                "or: pip install 'lensky-py-lab[gee]'"
            )
        _ee.Initialize(project=project, credentials=credentials)
        self._ee = _ee

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_ndvi_timeseries(
        self,
        geometry: Any,
        start_date: Union[str, date],
        end_date: Union[str, date],
        source: SatelliteSource,
        scale: Optional[int] = None,
        ndvi_min: Optional[float] = _NDVI_MIN_DEFAULT,
        cloud_pct_max: Optional[float] = None,
    ) -> pd.DataFrame:
        """Compute mean NDVI over *geometry* for each image in *source*.

        Replicates the JS script pipeline:

        1. Filter collection by date and bounds.
        2. Apply cloud-percentage pre-filter (per-source threshold).
        3. Compute NDVI from raw reflectance bands.
        4. Mask pixels below *ndvi_min* (default 0.35 → ``img.gte(0.35)``).
        5. Reduce to mean NDVI over *geometry* at native spatial scale.

        Args:
            geometry: ``ee.Geometry`` AOI (Point, Polygon, …).
            start_date: Query window start (ISO string or ``date``).
            end_date: Query window end (ISO string or ``date``).
            source: Satellite source (MODIS, SENTINEL2, or LANDSAT8).
            scale: Spatial resolution [m] for the region reducer. Defaults
                to the sensor's native resolution (250 / 10 / 30 m).
            ndvi_min: Pixels with NDVI < *ndvi_min* are masked before
                reduction. Set to ``None`` to skip masking. Default 0.35
                matches the JS script's ``maskLowValues`` function.
            cloud_pct_max: Override the per-source cloud percentage
                threshold. Defaults to 10 % for S2 and L8 (as in the script).

        Returns:
            DataFrame indexed by unix timestamp (``TS``) with one column
            ``NDVI RAW``, ready for ``DataSource.from_dataframe()``.
        """
        if source not in _COLLECTIONS:
            supported = [s.value for s in _COLLECTIONS]
            raise ValueError(
                f"GEE source must be one of {supported}, got {source!r}"
            )

        ee = self._ee
        start_str = _fmt_date(start_date)
        end_str   = _fmt_date(end_date)
        effective_scale = scale if scale is not None else _DEFAULT_SCALE[source]

        collection = (
            ee.ImageCollection(_COLLECTIONS[source])
            .filterDate(start_str, end_str)
            .filterBounds(geometry)
        )

        # Cloud pre-filter (percentage threshold — mirrors JS script filters)
        if source in _CLOUD_FILTER:
            prop, default_max = _CLOUD_FILTER[source]
            threshold = cloud_pct_max if cloud_pct_max is not None else default_max
            collection = collection.filter(ee.Filter.lt(prop, threshold))

        # Per-image: compute NDVI → optionally mask low values → reduce
        ndvi_min_val = ndvi_min  # close over for lambda

        def _process(image: Any) -> Any:
            ndvi = _compute_ndvi(ee, image, source)
            if ndvi_min_val is not None:
                ndvi = ndvi.updateMask(ndvi.gte(ndvi_min_val))
            mean_dict = ndvi.rename("NDVI").reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=effective_scale,
                bestEffort=True,
            )
            return image.set("ndvi_mean", mean_dict.get("NDVI"))

        result = (
            collection.map(_process)
            .reduceColumns(
                ee.Reducer.toList(2),
                ["system:time_start", "ndvi_mean"],
            )
            .get("list")
            .getInfo()
        )

        return _to_dataframe(result)

    def get_ndvi_timeseries_all(
        self,
        geometry: Any,
        start_date: Union[str, date],
        end_date: Union[str, date],
        scale: Optional[int] = None,
        ndvi_min: Optional[float] = _NDVI_MIN_DEFAULT,
        cloud_pct_max: Optional[float] = None,
        sources: Optional[List[SatelliteSource]] = None,
    ) -> Dict[SatelliteSource, pd.DataFrame]:
        """Query all satellite sources and return one DataFrame per source.

        Mirrors the JS script which creates three separate time-series
        (``data_modis``, ``data_s2``, ``data_l8``) with identical parameters.
        Sources that return no data produce an empty DataFrame rather than
        raising an exception.

        Args:
            geometry: ``ee.Geometry`` AOI.
            start_date: Query window start.
            end_date: Query window end.
            scale: Override spatial resolution for all sources.
            ndvi_min: Low-NDVI pixel mask threshold (default 0.35).
            cloud_pct_max: Override cloud percentage for all sources.
            sources: Subset of sources to query. Defaults to all three
                (MODIS, SENTINEL2, LANDSAT8).

        Returns:
            ``{SatelliteSource: DataFrame}`` — same structure as repeated
            calls to :meth:`get_ndvi_timeseries`.

        Example::

            frames = client.get_ndvi_timeseries_all(
                geometry, "2018-01-01", "2022-09-01",
            )
            for src, df in frames.items():
                print(src.value, len(df), "observations")
        """
        if sources is None:
            sources = [
                SatelliteSource.MODIS,
                SatelliteSource.SENTINEL2,
                SatelliteSource.LANDSAT8,
            ]

        results: Dict[SatelliteSource, pd.DataFrame] = {}
        for src in sources:
            try:
                df = self.get_ndvi_timeseries(
                    geometry=geometry,
                    start_date=start_date,
                    end_date=end_date,
                    source=src,
                    scale=scale,
                    ndvi_min=ndvi_min,
                    cloud_pct_max=cloud_pct_max,
                )
            except Exception as exc:  # noqa: BLE001
                import warnings
                warnings.warn(
                    f"GEE query failed for {src.value}: {exc}. "
                    "Returning empty DataFrame for this source."
                )
                df = pd.DataFrame(columns=[NDVI_RAW_FIELD])
            results[src] = df

        return results

    def point_geometry(
        self,
        lon: float,
        lat: float,
    ) -> Any:
        """Convenience wrapper: create an ``ee.Geometry.Point``.

        Matches the default geometry in the JS script::

            var geometry = ee.Geometry.Point([34.946667, 32.555806]);

        Args:
            lon: Longitude (decimal degrees).
            lat: Latitude (decimal degrees).

        Returns:
            ``ee.Geometry.Point`` object.
        """
        return self._ee.Geometry.Point([lon, lat])

    def polygon_geometry(
        self,
        coords: List[List[float]],
    ) -> Any:
        """Convenience wrapper: create an ``ee.Geometry.Polygon``.

        Args:
            coords: Ring of ``[lon, lat]`` pairs, e.g.
                ``[[34.9, 32.5], [35.0, 32.5], [35.0, 32.6], [34.9, 32.6]]``.

        Returns:
            ``ee.Geometry.Polygon`` object.
        """
        return self._ee.Geometry.Polygon([coords])


# ---------------------------------------------------------------------------
# NDVI computation — one function per collection, matching the JS script
# ---------------------------------------------------------------------------


def _compute_ndvi(ee: Any, image: Any, source: SatelliteSource) -> Any:
    """Compute a single-band NDVI image from a collection image.

    Exact band formulas match the JS script:

    MODIS (MOD09GQ)
        ``NDVI = (sur_refl_b02 - sur_refl_b01) / (sur_refl_b02 + sur_refl_b01)``
        No scale factor needed — it cancels in the ratio.
        JS equivalent: ``(NIR - Red) / (NIR + Red)`` with b02=NIR, b01=Red.

    Sentinel-2 (S2_SR_HARMONIZED)
        ``NDVI = (B8 - B4) / (B8 + B4)``
        Scale (×0.0001) cancels in the ratio.
        JS equivalent: ``(NIR - Red) / (NIR + Red)`` with B8=NIR, B4=Red.

    Landsat-8 (C02 T1_L2)
        Scale factor 0.0000275 and offset −0.2 are applied before the ratio
        because the additive offset does NOT cancel:
        ``refl = DN × 0.0000275 − 0.2``
        ``NDVI = (NIR_refl − Red_refl) / (NIR_refl + Red_refl)``
        QA_PIXEL masking removes cloud and cloud-shadow pixels.
        JS used C01 (no offset) so raw ratio was sufficient there.
    """
    if source == SatelliteSource.MODIS:
        # MOD09GQ: sur_refl_b02 = NIR (841–876 nm), sur_refl_b01 = Red (620–670 nm)
        # Matches JS: image.expression('(NIR - Red)/(NIR + Red)', {NIR: b02, Red: b01})
        return image.normalizedDifference(["sur_refl_b02", "sur_refl_b01"]).rename("NDVI")

    if source == SatelliteSource.SENTINEL2:
        # S2: B8 = NIR (835 nm), B4 = Red (665 nm)
        # Matches JS: image.expression('(NIR - Red)/(NIR + Red)', {NIR: B8, Red: B4})
        return image.normalizedDifference(["B8", "B4"]).rename("NDVI")

    if source == SatelliteSource.LANDSAT8:
        # L8 C02: apply physical scale + offset before ratio (offset ≠ 0 in C02)
        # JS used C01 where offset = 0 so ratio was scale-invariant; C02 is not.
        nir = image.select("SR_B5").multiply(0.0000275).add(-0.2)
        red = image.select("SR_B4").multiply(0.0000275).add(-0.2)

        # QA_PIXEL cloud+cloud-shadow mask (bit 3 = cloud, bit 4 = cloud shadow)
        qa = image.select("QA_PIXEL")
        clear = (
            qa.bitwiseAnd(1 << 3).eq(0)
            .And(qa.bitwiseAnd(1 << 4).eq(0))
        )
        nir = nir.updateMask(clear)
        red = red.updateMask(clear)

        return nir.subtract(red).divide(nir.add(red)).rename("NDVI")

    raise ValueError(f"Unsupported source for NDVI computation: {source!r}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_dataframe(features: Any) -> pd.DataFrame:
    """Convert GEE reduceColumns result list to a pipeline-ready DataFrame.

    Args:
        features: List of ``[timestamp_ms, ndvi_value]`` pairs from
            ``.getInfo()``.

    Returns:
        DataFrame indexed by unix timestamp (integer seconds) with one
        column ``NDVI RAW``.
    """
    rows: List[Dict] = []
    for ts_ms, ndvi_val in (features or []):
        if ndvi_val is None:
            continue
        rows.append({
            TIMESTAMP_FIELD: int(ts_ms / 1000),
            NDVI_RAW_FIELD:  float(ndvi_val),
        })

    if not rows:
        return pd.DataFrame(columns=[NDVI_RAW_FIELD])

    df = pd.DataFrame(rows).sort_values(TIMESTAMP_FIELD)
    df[NDVI_RAW_FIELD] = pd.to_numeric(df[NDVI_RAW_FIELD], errors="coerce")
    df.set_index(TIMESTAMP_FIELD, inplace=True)
    return df


def _fmt_date(d: Union[str, date]) -> str:
    if isinstance(d, str):
        return d
    return d.strftime("%Y-%m-%d")
