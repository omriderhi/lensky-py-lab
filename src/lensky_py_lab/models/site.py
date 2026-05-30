from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from lensky_py_lab.constants import NDVI_LOWESS_FIELD
from lensky_py_lab.models.source import DataSource


class Site:
    """Research site that aggregates NSRS ground sensors and satellite data sources.

    NSRS data is required at construction time. Satellite sources and IMS
    meteorological data are optional and can be added before calling
    :meth:`run_analysis`.

    Args:
        name: Site identifier (e.g., ``"RH_NDVI"``).
        nsrs_sources: Ground-sensor (NSRS) DataSource objects keyed by source name.
        satellite_sources: Satellite DataSource objects (MODIS, S2, L8 …) keyed by
            source name. May be supplied at construction or via :meth:`add_satellite`.
        ims_data: Optional IMS meteorological DataFrame (rainfall / temperature)
            indexed by unix timestamp, typically produced by :class:`IMSClient`.

    Example — CSV-based workflow::

        from lensky_py_lab import Site, DataSource, SourceConfig

        nsrs1 = DataSource.from_csv(
            "NSRS_1", "data/RH/NSRS_1.csv",
            SourceConfig(min_value=0.2, images_per_month=30),
        )
        modis = DataSource.from_csv(
            "MODIS", "data/RH/MODIS.csv",
            SourceConfig(max_value=0.8, average_window=0.1125, images_per_month=30),
        )
        site = Site("RH_NDVI", nsrs_sources={"NSRS_1": nsrs1},
                    satellite_sources={"MODIS": modis})
        df = site.run_analysis()

    Example — GEE-based satellite data::

        from lensky_py_lab import SatelliteSource, DataSource, SourceConfig
        from lensky_py_lab.clients.gee_client import GEEClient

        client = GEEClient(project="my-project")
        gee_df = client.get_ndvi_timeseries(
            geometry, "2018-01-01", "2023-12-31", SatelliteSource.MODIS,
        )
        modis = DataSource.from_dataframe(
            "MODIS", gee_df,
            SourceConfig(max_value=0.8, average_window=0.1125, images_per_month=30),
        )
        site = Site("RH_NDVI", nsrs_sources={"NSRS_1": nsrs1},
                    satellite_sources={"MODIS": modis})
    """

    def __init__(
        self,
        name: str,
        nsrs_sources: Dict[str, DataSource],
        satellite_sources: Optional[Dict[str, DataSource]] = None,
        ims_data: Optional[pd.DataFrame] = None,
    ) -> None:
        self.name = name
        self.nsrs_sources: Dict[str, DataSource] = nsrs_sources
        self.satellite_sources: Dict[str, DataSource] = satellite_sources or {}
        self.ims_data: Optional[pd.DataFrame] = ims_data
        self._site_df: Optional[pd.DataFrame] = None

    def add_satellite(self, source: DataSource) -> None:
        """Add or replace a satellite DataSource."""
        self._site_df = None
        self.satellite_sources[source.name] = source

    def set_ims_data(self, ims_df: pd.DataFrame) -> None:
        """Attach IMS meteorological data."""
        self._site_df = None
        self.ims_data = ims_df

    @property
    def all_sources(self) -> Dict[str, DataSource]:
        return {**self.nsrs_sources, **self.satellite_sources}

    def run_analysis(self) -> pd.DataFrame:
        """Process all sources and return the joined site DataFrame.

        The resulting DataFrame is indexed by unix timestamp and contains:

        * One ``'NDVI lowess <source_name>'`` column per source.
        * NSRS variant pairs (e.g., ``NSRS_1`` / ``NSRS_1_B``) are consolidated
          into a single column via forward-fill.
        * IMS rainfall / temperature columns, if :attr:`ims_data` is set.
        """
        series_list = [_dedup_index(src.lowess_series) for src in self.all_sources.values()]
        site_df = pd.concat(series_list, axis=1, join="outer").sort_index()
        site_df = _unify_nsrs_variants(site_df)

        if self.ims_data is not None:
            site_df = site_df.join(self.ims_data, how="outer", sort=True)

        self._site_df = site_df
        return site_df

    @property
    def site_df(self) -> pd.DataFrame:
        """Lazily computed and cached site DataFrame."""
        if self._site_df is None:
            self.run_analysis()
        return self._site_df  # type: ignore[return-value]


def _dedup_index(series: pd.Series) -> pd.Series:
    """Average values that share the same timestamp (handles duplicate dates in raw CSVs)."""
    if series.index.duplicated().any():
        series = series.groupby(level=0).mean()
    return series


def _unify_nsrs_variants(df: pd.DataFrame) -> pd.DataFrame:
    """Merge NSRS_X and NSRS_X_B variant columns via forward-fill into NSRS_X."""
    prefix = f"{NDVI_LOWESS_FIELD} "
    lowess_cols = [c for c in df.columns if c.startswith(prefix)]
    base_names = {c[len(prefix):].removesuffix("_B") for c in lowess_cols}

    for base in base_names:
        primary = f"{prefix}{base}"
        backup = f"{prefix}{base}_B"
        if primary in df.columns and backup in df.columns:
            df[primary] = df[primary].fillna(df[backup])
            df.drop(columns=[backup], inplace=True)

    return df
