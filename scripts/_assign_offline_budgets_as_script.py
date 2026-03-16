# %% Script om AssignOfflineBudgets uit te breiden

from datetime import timedelta

import imod
import numpy as np
import pandas as pd
from ribasim import Model
from ribasim_tools.get_drainage_from_modflow import AssignOfflineBudgets
from ribasim_tools.knmi_daggegevens import update_meteo

from ribasim_tools import settings

modflow_budgets_path = (
    settings.source_data_dir / "GRAM3_2" / "100" / "GRAM32_BASIS1_TA-PRJ" / "RESULTS" / "BASIS1_TA-PRJ"
)
metaswap_budgets_path = modflow_budgets_path / "MSWAPINPUT"

model = Model.read(settings.LHM_BA_toml_path)
model.endtime = model.starttime + timedelta(days=365)


update_meteo(
    model,
    station_id=375,
    starttime=model.starttime,
    endtime=model.endtime,
    recreate_time_table=True,
    inplace=True,
)


assign_offline_budgets = AssignOfflineBudgets(
    modflow_budgets_path=modflow_budgets_path, metaswap_budgets_path=metaswap_budgets_path
)


self = assign_offline_budgets
basin_split: str = "area"
basin_subtype: str = "state"
basin_metacol: str = "meta_categorie"
primary_budgets = ["bdgriv_sys1"]
secondary_budgets = ["bdgriv_sys2", "bdgdrn_sys2", "bdgdrn_sys3", "bdgpssw", "bdgqrun"]
ignore_budgets = ["bdgdrn_sys1"]

# %%
# Synchronize LHM budget and model files
print("📖 read and validate budgets")
budgets, model = self._sync_files(model)

# Validate budgets
self._validate_budgets(
    budgets=budgets,
    primary_budgets=primary_budgets,
    secondary_budgets=secondary_budgets,
    ignore_budgets=ignore_budgets,
)

# Split into primary and secondary basin definition
print("🪓 split basins into primary and secondary")
primary_basin_definition, secondary_basin_definition = self.split_basin_definitions(
    model,
    basin_split=basin_split,
    basin_subtype=basin_subtype,
    basin_metacol=basin_metacol,
)

# create masks
print("▦ rasterize basins to masks")
array = budgets["bdgriv_sys1"].isel(time=0, drop=True)
primary_basin_mask = imod.prepare.rasterize(
    primary_basin_definition, column="node_id", like=array, fill=-999, dtype=np.int32
)
secondary_basin_mask = imod.prepare.rasterize(
    secondary_basin_definition, column="node_id", like=array, fill=-999, dtype=np.int32
)

# %%


def sum_budgets_per_basin(budgets, basin_mask, nodata=-999):
    if basin_mask.dims != ("x", "y"):
        basin_mask = basin_mask.transpose("x", "y")

    var_names = list(budgets.data_vars)

    arr = budgets[var_names].to_array("variable").transpose("time", "variable", "x", "y").values
    nt, nv, nx, ny = arr.shape

    arr = arr.reshape(nt, nv, nx * ny)
    mask = basin_mask.values.reshape(nx * ny)

    valid = np.isfinite(mask) & (mask != nodata)
    ids = mask[valid].astype(int)
    arr = arr[:, :, valid]

    unique_ids, inv = np.unique(ids, return_inverse=True)
    nb = len(unique_ids)

    result = np.zeros((nt, nb, nv), dtype=arr.dtype)

    for b in range(nb):
        sel = inv == b
        result[:, b, :] = arr[:, :, sel].sum(axis=2)

    index = pd.MultiIndex.from_product([unique_ids, budgets.time.values], names=["node_id", "time"])

    df = pd.DataFrame(result.transpose(1, 0, 2).reshape(nb * nt, nv), index=index, columns=var_names).sort_index()

    return df


# get a table for primary and secondary basins with budgets (columns) and node_id, time (index)
primary_budgets_df = sum_budgets_per_basin(budgets[primary_budgets], primary_basin_mask) / 86400
secondary_budgets_df = sum_budgets_per_basin(budgets[secondary_budgets], secondary_basin_mask) / 86400

# concat all budgets so we can return those for verification
budgets_df = pd.concat([primary_budgets_df, secondary_budgets_df]).sort_index()


# sum all budgets (columns) and create drainage and infiltration series
summed_budgets = pd.Series(budgets_df.sum(axis=1))
drainage = summed_budgets.clip(upper=0).abs()  # alles <0, teken opklappen (uit modflow is in ribasim)
infiltration = summed_budgets.clip(
    lower=0
)  # alles > 0 (infiltratie is in modflow, ontrekking uit ribasim, maar in ribasim positief teken)

# update basin drainage and infiltration
idx = pd.MultiIndex.from_frame(model.basin.time.df[["node_id", "time"]])
model.basin.time.df["drainage"] = idx.map(drainage)
model.basin.time.df["infiltration"] = idx.map(infiltration)

# %%
