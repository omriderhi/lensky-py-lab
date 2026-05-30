from logging import Logger
from typing import Dict, Optional
import pandas as pd
import statsmodels.api as sm
from lensky_py_lab.base_entities import SourceBase
from lensky_py_lab.constants import DataState


def filter_extreme_values(
        source: SourceBase,
        logger: Optional[Logger] = None
) -> None:
    df = source.data
    configs = source.source_settings
    filtered_data_field_name = f'{configs.data_header}_{DataState.FILTERED.value}'
    ndvi_values = [ndvi_value for _, ndvi_value in df[configs.data_header].items() if ndvi_value]

    possible_min = \
        min(ndvi_values) if configs.relevant_min is None else configs.relevant_min
    possible_max = \
        max(ndvi_values) if configs.relevant_max is None else configs.relevant_max

    filtered_values = []

    for i, row in df.iterrows():
        raw_ndvi = row[configs.data_header]
        try:
            raw_ndvi = float(raw_ndvi)
        except ValueError:
            if logger:
                logger.warning(f'can not convert this value: {raw_ndvi} from {row[0]} - Skipping')
            continue
        except TypeError:
            if logger:
                logger.warning(f'can not convert this value: {raw_ndvi} from {row[0]} - Skipping')
            continue

        if possible_min <= raw_ndvi <= possible_max:
            filtered_values.append(raw_ndvi)
        else:
            filtered_values.append(None)
    df.insert(len(df.keys()), filtered_data_field_name, filtered_values)
    source.data_state = DataState.FILTERED


def clean_by_outlier(
        source: SourceBase,
        logger: Optional[Logger] = None
) -> None:
    if not source.data_state == DataState.FILTERED and logger is not None:
        logger.warning(
            f'Data extremes should be filtered before outlier filtering.'
            f'current data state: {source.data_state.value}'
        )
    df = source.data
    configs = source.source_settings
    cleaned_data_field_name = f'{configs.data_header}_{DataState.CLEAN.value}'
    if configs.outlier_window is None:
        df[cleaned_data_field_name] = df[f'{configs.data_header}_{DataState.FILTERED.value}']
        return

    cdf = df.fillna(False)

    filtered_field_ind = cdf.columns.get_loc(source.relevant_field_name)
    one_side_group_distance = configs.outlier_window // 2

    clean_ndvi = []
    for i, row in cdf.iterrows():
        if not row[source.relevant_field_name]:
            clean_ndvi.append(None)
            continue
        inspected_ndvi = row[source.relevant_field_name]
        first_in_group = i - i - one_side_group_distance
        if first_in_group <= 0:
            first_in_group = 1
        last_in_group = i + one_side_group_distance
        if last_in_group > len(cdf.index):
            last_in_group = len(df.index)
        test_group = [test_value for test_value in
                      df.iloc[first_in_group:last_in_group, filtered_field_ind].dropna(axis=0)]

        test_average = sum(test_group) / len(test_group)
        if abs(test_average - inspected_ndvi) >= float(configs.outlier_window):
            clean_ndvi.append(inspected_ndvi)
        else:
            clean_ndvi.append(None)

    cdf[cleaned_data_field_name] = clean_ndvi
    source.data_state = DataState.CLEAN


def add_loess_column(
        source: SourceBase,
        y_field_name: str,
        x_field_name: str = 'DATE',
        logger: Optional[Logger] = None,
) -> None:
    """
    alpha(smoothing "frac" parameter) = Nwin / Npts
    """
    if not source.data_state == DataState.CLEAN:
        logger.warning(f"Data should be cleaned before applying lowess. Current data state: {source.data_state.value}")
    lowess_factor = source_configurations.get('images_per_month')
    if not lowess_factor:
        df[NDVI_LOWESS_FIELD_NAME] = df[NDVI_CLEAN_FIELD_NAME]
        return df

    dropped_df = df.dropna(axis=0)
    dropped_n = len(dropped_df)
    x = dropped_df.index
    y = dropped_df[y_field_name].to_list()
    loess_factor_fraction = lowess_factor / dropped_n

    lowess = sm.nonparametric.lowess(y, x, frac=loess_factor_fraction)
    tss = [int(i) for i in list(zip(*lowess))[0]]
    ndvi_lowess = list(list(zip(*lowess))[1])
    general_factor = source_configurations.get('general_factor')
    if general_factor:
        for i, ndvi in enumerate(ndvi_lowess):
            ndvi_lowess[i] = ndvi * general_factor
    tmp_dict = {
        'ts': tss,
        NDVI_LOWESS_FIELD_NAME: ndvi_lowess
    }
    tmp_df = pd.DataFrame(tmp_dict)
    tmp_df.set_index('ts', inplace=True)
    lowess_df = df.join(tmp_df, how='left')

    return lowess_df
