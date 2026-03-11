# %% Script om AssignOfflineBudgets uit te breiden

import imod
import numpy as np
import pandas as pd
from ribasim import Model
from ribasim_tools.get_drainage_from_modflow import AssignOfflineBudgets

from ribasim_tools import settings

modflow_budgets_path = (
    settings.source_data_dir / "GRAM3_2" / "100" / "GRAM32_BASIS1_TA-PRJ" / "RESULTS" / "BASIS1_TA-PRJ"
)
metaswap_budgets_path = modflow_budgets_path / "MSWAPINPUT"

model = Model.read(settings.LHM_BA_toml_path)

assign_offline_budgets = AssignOfflineBudgets(
    modflow_budgets_path=modflow_budgets_path, metaswap_budgets_path=metaswap_budgets_path
)


# model = assign_offline_budgets.compute_budgets(
#     model=model,
#     primary_budgets=["bdgriv_sys1"],
#     secondary_budgets=["bdgriv_sys2", "bdgdrn_sys2", "bdgdrn_sys3", "bdgpssw", "bdgqrun"],
#     ignore_budgets=["bdgdrn_sys1"],
# )

# compute_budgets functie

self = assign_offline_budgets
basin_split: str = "area"
basin_subtype: str = "state"
basin_metacol: str = "meta_categorie"
primary_budgets = ["bdgriv_sys1"]
secondary_budgets = ["bdgriv_sys2", "bdgdrn_sys2", "bdgdrn_sys3", "bdgpssw", "bdgqrun"]
ignore_budgets = ["bdgdrn_sys1"]


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
# _compute_budgets_per_node_id functie die moet worden aangepast
# sum primairy systems
primary_summed_budgets = budgets[primary_budgets].to_array("variable").sum("variable", skipna=True).rename("primair")

# sum secondary systems
secondary_summed_budgets = (
    budgets[secondary_budgets].to_array("variable").sum("variable", skipna=True).rename("secondair")
)

# sum per system and node_id
primary_budgets_per_node_id = (
    primary_summed_budgets.groupby(primary_basin_mask).sum(dim="stacked_y_x").to_dataframe().unstack(1).transpose()
)
primary_budgets_per_node_id.index = primary_budgets_per_node_id.index.droplevel(0)
primary_budgets_per_node_id = primary_budgets_per_node_id.loc[
    primary_budgets_per_node_id.index != -999, :
]  # remove non overlapping budgets

secundary_budgets_per_node_id = (
    secondary_summed_budgets.groupby(secondary_basin_mask).sum(dim="stacked_y_x").to_dataframe().unstack(1).transpose()
)
secundary_budgets_per_node_id.index = secundary_budgets_per_node_id.index.droplevel(0)
secundary_budgets_per_node_id = secundary_budgets_per_node_id.loc[
    secundary_budgets_per_node_id.index != -999, :
]  # remove non overlapping budgets

# combine dataframe's based on node_id
budgets_per_node_id = pd.concat([primary_budgets_per_node_id, secundary_budgets_per_node_id])
budgets_per_node_id.index.name = "node_id"


# %% alternative function
primary_budgets_df = (
    budgets[primary_budgets]
    .assign_coords(node_id=primary_basin_mask.rename("node_id"))
    .stack(cell=("x", "y"))
    .where(lambda ds: ds.node_id != -999, drop=True)
    .groupby("node_id")
    .sum("cell")
    .to_dataframe()
    .reorder_levels(["node_id", "time"])
    .sort_index()
)

secondary_budgets_df = (
    budgets[secondary_budgets]
    .assign_coords(node_id=secondary_basin_mask.rename("node_id"))
    .stack(cell=("x", "y"))
    .where(lambda ds: ds.node_id != -999, drop=True)
    .groupby("node_id")
    .sum("cell")
    .to_dataframe()
    .reorder_levels(["node_id", "time"])
    .sort_index()
)

# m3/day to m3/sec
primary_budgets_df /= 86400
secondary_budgets_df /= 86400

# %%
import numpy as np
import pandas as pd


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


primary_budgets_df = sum_budgets_per_basin(budgets[primary_budgets], primary_basin_mask) / 86400
secondary_budgets_df = sum_budgets_per_basin(budgets[secondary_budgets], secondary_basin_mask) / 86400
# %%
