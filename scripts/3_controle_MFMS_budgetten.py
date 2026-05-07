# %%
import pandas as pd
from ribasim import Model

from ribasim_tools import compare_series, settings

# %% [markdown]

### Inlezen model en MFMS-budgetten
#
# We vergelijken Ribasim-basinreeksen met de MFMS/iMOD-waterbalans uit `WBAL_dgeb.csv`.
# De budgetten worden gelezen per zone (`ZONE`) en per tijdstap (`DATE_TIME`).

model = Model.read(settings.LHM_BA_RVW_toml_path)
wbal_imod_csv = settings.processed_data_dir / "wbal" / "WBAL_dgeb.csv"

budgets_df = pd.read_csv(wbal_imod_csv)
budgets_df["DATE_TIME"] = pd.to_datetime(budgets_df["DATE_TIME"], format="%Y%m%d%H%M%S")

primary_node_id = 1126
primary_systems = ["bdgriv_sys1"]
secondary_systems = [
    "bdgriv_sys2",
    "bdgdrn_sys2",
    "bdgdrn_sys3",
]  # Let op: "bdgpsswm3" en "bdgqrunm3" vallen hier buiten
surface_runoff_systems = ["bdgqrunm3"]

# %% [markdown]

### Vergelijken van individuele basinreeksen
#
# Voor basin `1126` vergelijken we:
# - het hoofdsysteem (`bdgriv_sys1`)
# - het bergende systeem in hetzelfde polygoon
# - de surface runoff uit MetaSWAP

poly = model.basin.area.df.set_index("node_id").at[primary_node_id, "geometry"]
secondary_node_id = (
    model.basin.area.df[(model.basin.area.df.geometry == poly) & (model.basin.area.df.node_id != primary_node_id)]
    .iloc[0]
    .node_id
)

compare_series(
    model=model,
    budgets_df=budgets_df,
    model_node_id=primary_node_id,
    imod_node_id=primary_node_id,
    systems=primary_systems,
).cumsum().plot(title=f"{primary_node_id} (hoofdsysteem)", grid=True, ylabel="cum. afvoer [m3/s]")

compare_series(
    model=model,
    budgets_df=budgets_df,
    model_node_id=secondary_node_id,
    imod_node_id=primary_node_id,
    systems=secondary_systems,
).cumsum().plot(title=f"{secondary_node_id} (bergend)", grid=True, ylabel="cum. afvoer [m3/s]")

compare_series(
    model=model,
    budgets_df=budgets_df,
    model_node_id=secondary_node_id,
    imod_node_id=primary_node_id,
    systems=surface_runoff_systems,
    absolute=True,
    model_column="surface_runoff",
    basin_label="Basin (surface_runoff)",
).cumsum().plot(title=f"{secondary_node_id} (surface runoff)", grid=True, ylabel="cum. afvoer [m3/s]")

# %% [markdown]

### Vergelijken van totale watersysteem-budgetten
#
# We sommeren de Ribasim-reeksen voor hoofdwater/doorgaand en bergend en zetten die om naar `mm`.
# De MFMS-budgetten worden over alle zones opgeteld zodat een systeembrede vergelijking ontstaat.

area = model.basin.area.df.union_all().area
primary_basin_node_ids = model.basin.node.df[
    model.basin.node.df["meta_categorie"].isin(["hoofdwater", "doorgaand"])
].index.values
secondary_basin_node_ids = model.basin.node.df[model.basin.node.df["meta_categorie"].isin(["bergend"])].index.values

primary_drainage = (
    model.basin.time.df[model.basin.time.df.node_id.isin(primary_basin_node_ids)][["time", "drainage"]]
    .groupby("time")
    .sum()["drainage"]
)
primary_infiltration = (
    model.basin.time.df[model.basin.time.df.node_id.isin(primary_basin_node_ids)][["time", "infiltration"]]
    .groupby("time")
    .sum()["infiltration"]
)
primary_ribasim = (primary_drainage - primary_infiltration) * 86400 * 1000 / area

imod_sum_df = budgets_df.groupby("DATE_TIME", as_index=False).sum(numeric_only=True).set_index("DATE_TIME")
primary_imod = (
    -(
        imod_sum_df[[f"{system.upper()}_OUT" for system in primary_systems]].sum(axis=1)
        + imod_sum_df[[f"{system.upper()}_IN" for system in primary_systems]].sum(axis=1)
    )
    * 1000
    / area
)

compare_df = pd.concat([primary_ribasim, primary_imod], axis=1)
compare_df.columns = ["Basin (drainage/infiltratie)", f"iMOD ({','.join(primary_systems)})"]
compare_df.cumsum().plot(title="totaal hoofdsysteem", grid=True, ylabel="afvoer [mm]")

secondary_drainage = (
    model.basin.time.df[model.basin.time.df.node_id.isin(secondary_basin_node_ids)][["time", "drainage"]]
    .groupby("time")
    .sum()["drainage"]
)
secondary_infiltration = (
    model.basin.time.df[model.basin.time.df.node_id.isin(secondary_basin_node_ids)][["time", "infiltration"]]
    .groupby("time")
    .sum()["infiltration"]
)
secondary_ribasim = (secondary_drainage - secondary_infiltration) * 86400 * 1000 / area

secondary_imod = (
    -(
        imod_sum_df[[f"{system.upper()}_OUT" for system in secondary_systems]].sum(axis=1)
        + imod_sum_df[[f"{system.upper()}_IN" for system in secondary_systems]].sum(axis=1)
    )
    * 1000
    / area
)

compare_df = pd.concat([secondary_ribasim, secondary_imod], axis=1)
compare_df.columns = ["Basin (drainage/infiltratie)", f"iMOD ({','.join(secondary_systems)})"]
compare_df.cumsum().plot(title="totaal bergend systeem", grid=True, ylabel="afvoer [mm]")

surface_runoff_imod = (
    (
        imod_sum_df[[f"{system.upper()}_OUT" for system in surface_runoff_systems]].sum(axis=1)
        + imod_sum_df[[f"{system.upper()}_IN" for system in surface_runoff_systems]].sum(axis=1)
    ).abs()
    * 1000
    / area
)

surface_runoff_ribasim = (
    model.basin.time.df[model.basin.time.df.node_id.isin(secondary_basin_node_ids)][["time", "surface_runoff"]]
    .groupby("time")
    .sum()["surface_runoff"]
)

compare_df = pd.concat([surface_runoff_ribasim, surface_runoff_imod], axis=1)
compare_df.columns = ["Basin (surface_runoff)", f"iMOD ({','.join(surface_runoff_systems)})"]
compare_df.cumsum().plot(title="totaal surface_runoff", grid=True, ylabel="afvoer [mm]")
