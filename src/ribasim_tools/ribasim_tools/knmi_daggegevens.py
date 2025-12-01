# %%
import pandas as pd
from ribasim import Model

from ribasim_tools import settings

DATA_DIR = settings.source_data_dir / "knmi_daggegevens"
station = 375
model = Model.read(settings.processed_data_dir.joinpath("hsa_model_clipped", "ribasim.toml"))
update_time_table: bool = True
# read json_file
json_file = DATA_DIR / f"{station}.json"
df = pd.read_json(json_file).set_index("date")
df.index = pd.to_datetime(df.index).tz_localize(None)

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

# update model.basin.time.df with values
if update_time_table:
    time_df = df.reindex(pd.to_datetime(model.basin.time.df.time.to_numpy()))
    model.basin.time.df["precipitation"] = time_df["precipitation"].to_numpy()
    model.basin.time.df["potential_evaporation"] = time_df["potential_evaporation"].to_numpy()
else:
    print("haal empty table uit ribasim-nl en vul deze")
# %%
