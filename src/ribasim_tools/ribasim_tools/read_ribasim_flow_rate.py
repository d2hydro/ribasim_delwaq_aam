import pandas as pd
from ribasim import Model
import xarray as xr

def read_flow_rate(model:Model, link_id: int,    starttime: pd.Timestamp | None = None,endtime: pd.Timestamp | None = None)-> pd.Series:
    with xr.open_dataset(model.toml_path.parent.joinpath("results", "flow.nc")) as ds:
        # select link
        ds_sel = ds.sel(link_id=link_id)
        
        # slice time
        if starttime or endtime:
            ds_sel = ds_sel.sel(time=slice(starttime, endtime))


        df = ds_sel.to_dataframe().reset_index()
    return df.set_index("time")["flow_rate"]