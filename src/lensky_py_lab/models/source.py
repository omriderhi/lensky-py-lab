from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from lensky_py_lab.configs import SourceConfig
from lensky_py_lab.constants import NDVI_LOWESS_FIELD
from lensky_py_lab.io.csv_loader import load_source_csv
from lensky_py_lab.pipeline.processor import process_source


@dataclass
class DataSource:
    """A single measurement source — either a satellite (MODIS, S2, L8 …) or an
    NSRS ground sensor.

    Attributes:
        name: Short identifier used as a column-name suffix in the site DataFrame
            (e.g., ``"MODIS"``, ``"NSRS_1"``).
        config: Per-source cleaning / smoothing parameters.
        raw_data: Unprocessed DataFrame as returned by the CSV loader or a GEE query.
    """

    name: str
    config: SourceConfig
    raw_data: pd.DataFrame
    _processed: Optional[pd.DataFrame] = field(default=None, repr=False, compare=False)

    @classmethod
    def from_csv(
        cls,
        name: str,
        path: Union[str, Path],
        config: SourceConfig,
    ) -> DataSource:
        """Load a source from a CSV file (same format as the original research CSVs)."""
        return cls(name=name, config=config, raw_data=load_source_csv(path))

    @classmethod
    def from_dataframe(
        cls,
        name: str,
        df: pd.DataFrame,
        config: SourceConfig,
    ) -> DataSource:
        """Create a source from an already-loaded DataFrame (e.g., from GEEClient)."""
        return cls(name=name, config=config, raw_data=df)

    def process(self) -> DataSource:
        """Run the full cleaning pipeline and cache the result."""
        self._processed = process_source(self.raw_data.copy(), self.config)
        return self

    @property
    def processed(self) -> pd.DataFrame:
        """Processed DataFrame (computed lazily on first access)."""
        if self._processed is None:
            self.process()
        return self._processed  # type: ignore[return-value]

    @property
    def lowess_series(self) -> pd.Series:
        """LOWESS column extracted as a named Series for joining into a Site DataFrame."""
        return self.processed[NDVI_LOWESS_FIELD].rename(f"{NDVI_LOWESS_FIELD} {self.name}")
