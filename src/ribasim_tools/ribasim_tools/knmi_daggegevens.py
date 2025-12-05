# %%
from datetime import datetime

import pandas as pd
from ribasim import Model
from ribasim.nodes import basin

from ribasim_tools import settings

DATA_DIR = settings.source_data_dir / "knmi_daggegevens"


def _validate_inputs(starttime: datetime, endtime: datetime):
    if starttime >= endtime:
        raise ValueError(f"starttime ({starttime} should be before endtime {endtime})")


def _create_node_time_table(df: pd.DataFrame, node_id: int) -> pd.DataFrame:
    df = basin.Time(df=df).df
    df["node_id"] = node_id
    return df


def update_meteo(
    model: Model,
    station_id: int,
    starttime: datetime | None = None,
    endtime: datetime | None = None,
    inplace: bool = False,
    recreate_time_table: bool = False,
):
    # create a copy of model
    if inplace:
        updated_model = model
    else:
        updated_model = model.model_copy()

    # make sure starttime and endtime are not None
    if starttime is None:
        starttime = updated_model.starttime
    if endtime is None:
        endtime = updated_model.endtime

    # make sure startime and endtime are valid and update model run period
    _validate_inputs(starttime=starttime, endtime=endtime)
    updated_model.starttime = starttime
    updated_model.endtime = endtime

    # create time-array
    time = pd.date_range(start=starttime, end=endtime, freq="D").to_numpy()

    # read json_file to df
    json_file = DATA_DIR / f"{station_id}.json"
    df = pd.read_json(json_file).set_index("date")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "time"

    # slice df by time-array
    df = df.loc[time]

    # rename to ribasim params
    df = df.rename(columns={"RH": "precipitation", "EV24": "potential_evaporation"})[
        ["precipitation", "potential_evaporation"]
    ]

    # set NaN to 0 and -1.0 (nihil precipitation) to 0
    df["precipitation"] = df["precipitation"].fillna(0)
    df["potential_evaporation"] = df["potential_evaporation"].fillna(0)
    mask = df["precipitation"] < 0
    df.loc[mask, "precipitation"] = 0

    # convert units (0.1mm/day -> m/s)
    conversion = 10000 * 86400  # 1m = 10000mm and 1 day = 86400 seconds
    df["precipitation"] = df["precipitation"] / conversion
    df["potential_evaporation"] = df["potential_evaporation"] / conversion

    # populate time_table
    if (not recreate_time_table) and (updated_model.basin.time.df is not None):  # try to update existing table
        # filter invalid times
        updated_model.basin.time.df = updated_model.basin.time.df.loc[updated_model.basin.time.df.time.isin(time)]
        expected_length = len(df) * len(updated_model.basin.node.df)
        if expected_length != len(updated_model.basin.time.df):
            raise ValueError(
                f"Invalid length of model.basin.time.df!. Length of model.basin.time ({len(updated_model.basin.time.df)}) should be timestamps ({len(df)}) X # basin nodes ({len(updated_model.basin.node.df)}) == {expected_length}"
            )
        updated_model.basin.time.df["precipitation"] = df.loc[updated_model.basin.time.df.time.to_numpy()][
            "precipitation"
        ].to_numpy()
        updated_model.basin.time.df["potential_evaporation"] = df.loc[updated_model.basin.time.df.time.to_numpy()][
            "potential_evaporation"
        ].to_numpy()
    else:  # replace basin time table
        df.reset_index(inplace=True)
        updated_model.basin.time.df = pd.concat(
            [_create_node_time_table(df, node_id) for node_id in updated_model.basin.node.df.index]
        )

    # return model if not inplace
    if inplace:
        return None
    else:
        return updated_model
