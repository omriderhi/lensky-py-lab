import uuid
import pandas as pd
from typing import Optional

from lensky_py_lab.configs import SourceConfig
from lensky_py_lab.constants import DataState


class SourceBase:
    def __init__(
            self,
            source_name: str,
            source_id: Optional[str] = None,
            site_id: Optional[str] = None,
            source_settings: Optional[SourceConfig] = None,
            data: Optional[pd.DataFrame] = None,
            data_state: DataState = DataState.RAW
    ):
        self.name = source_name
        self.source_id = uuid.uuid4()[:6] if source_id is None else source_id
        self.site_id = site_id
        self.source_settings = source_settings
        self.data = data
        self.data_state = data_state

    def __repr__(self):
        return f"Source(name={self.name}, url={self.source_id})"

    @classmethod
    def from_file(
            cls,
            file_path: str,
            source_name: str,
            source_id: Optional[str] = None,
            site_id: Optional[str] = None,
            source_settings: Optional[SourceConfig] = None
    ):
        data = pd.read_csv(file_path)
        return cls(
            source_name=source_name,
            source_id=source_id,
            site_id=site_id,
            source_settings=source_settings,
            data=data,
        )

    @classmethod
    def from_dict(
            cls,
            source_dict: dict
    ):
        source_name = source_dict['name']
        source_id = source_dict.get('source_id')
        file_path = source_dict.get('file_path')
        source_settings = SourceConfig(source_dict.get('source_settings'))
        site_id = source_dict.get('site_id')
        if file_path is not None:
            data = pd.read_csv(file_path)
        else:
            data = pd.DataFrame(source_dict.get('data', {}))
        return cls(
            source_name=source_name,
            source_id=source_id,
            site_id=site_id,
            source_settings=source_settings,
            data=data
        )

    @property
    def relevant_field_name(self) -> str:
        return f"{self.source_settings.data_header}_{self.data_state.value}"


class SiteBase:
    def __init__(self, site_name: str, site_id: Optional[str] = None):
        self.name = site_name
        self.site_id = uuid.uuid4()[:6] if site_id is None else site_id
        self.sources = {}

    def __repr__(self):
        return f"Site(name={self.name}, url={self.site_id})"

    def add_source(self, source: SourceBase):
        if source.source_id in self.sources:
            raise ValueError(f"Source with ID {source.source_id} already exists in this site.")
        source.site_id = self.site_id
        self.sources[source.source_id] = source
