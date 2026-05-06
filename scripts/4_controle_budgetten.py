import pandas as pd
from ribasim import Model

from ribasim_tools import settings


# %% [markdown]
def compare_series(model: Model, model_node_id: int, imod_node_id: int, systems: list[str]):
    # Compare primary system (drainage is positive, infiltration is negative)
    model_df = model.basin.time.df[model.basin.time.df.node_id == model_node_id].set_index("time")
    model_series = model_df["drainage"] - model_df["infiltration"]

    # Sum iMOD csv and convert m3/day -> m3/s
    mask = df["ZONE"] == imod_node_id
    imod_df = df[mask].groupby(["DATE_TIME", "ZONE"], as_index=False).sum(numeric_only=True).set_index("DATE_TIME")
    imod_series = (
        -(
            imod_df[[f"{i.upper()}_OUT" for i in systems]].sum(axis=1)
            + imod_df[[f"{i.upper()}_IN" for i in systems]].sum(axis=1)
        )
        / 86400
    )

    compare_df = pd.concat([model_series, imod_series], axis=1)
    compare_df.columns = ["Basin (drainage/infiltratie)", f"iMOD ({','.join(systems)})"]
    return compare_df


# %%
# Inlezen waterbalans


model = Model.read(settings.LHM_BA_Delwaq_toml_path)
wbal_imod_csv = settings.processed_data_dir.joinpath("wbal", "WBAL_dgeb.csv")


df = pd.read_csv(wbal_imod_csv)
df["DATE_TIME"] = pd.to_datetime(df["DATE_TIME"], format="%Y%m%d%H%M%S")

primary_node_id = 1126
primary_systems = ["bdgriv_sys1"]
secondary_systems = ["bdgriv_sys2", "bdgdrn_sys2", "bdgdrn_sys3"]  # Let op (!) "bdgpssw", "bdgqrun" missen
sr_systems = ["bdgqrunm3"]

# vinden secondary_node_id
poly = model.basin.area.df.set_index("node_id").at[primary_node_id, "geometry"]
secondary_node_id = (
    model.basin.area.df[(model.basin.area.df.geometry == poly) & (model.basin.area.df.node_id != primary_node_id)]
    .iloc[0]
    .node_id
)
# Compare primary system (drainage is positive, infiltration is negative)
compare_series(
    model=model,
    model_node_id=primary_node_id,
    imod_node_id=primary_node_id,
    systems=primary_systems,
).cumsum().plot(title=f"{primary_node_id} (hoofdsysteem)", grid=True, ylabel="cum. afvoer [m3/s]")
compare_series(
    model=model,
    model_node_id=secondary_node_id,
    imod_node_id=primary_node_id,
    systems=secondary_systems,
).cumsum().plot(title=f"{secondary_node_id} (bergend)", grid=True, ylabel="cum. afvoer [m3/s]")


compare_series(
    model=model,
    model_node_id=secondary_node_id,
    imod_node_id=primary_node_id,
    systems=sr_systems,
).cumsum().plot(title=f"{secondary_node_id} (surface runoff)", grid=True, ylabel="cum. afvoer [m3/s]")

# %%
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


imod_sum_df = df.groupby("DATE_TIME", as_index=False).sum(numeric_only=True).set_index("DATE_TIME")
primary_imod = (
    (
        -(
            imod_sum_df[[f"{i.upper()}_OUT" for i in primary_systems]].sum(axis=1)
            + imod_sum_df[[f"{i.upper()}_IN" for i in primary_systems]].sum(axis=1)
        )
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
    (
        -(
            imod_sum_df[[f"{i.upper()}_OUT" for i in secondary_systems]].sum(axis=1)
            + imod_sum_df[[f"{i.upper()}_IN" for i in secondary_systems]].sum(axis=1)
        )
    )
    * 1000
    / area
)

compare_df = pd.concat([secondary_ribasim, secondary_imod], axis=1)
compare_df.columns = ["Basin (drainage/infiltratie)", f"iMOD ({','.join(secondary_systems)})"]
compare_df.cumsum().plot(title="totaal bergend systeem", grid=True, ylabel="afvoer [mm]")


sr_imod = (
    (
        -(
            imod_sum_df[[f"{i.upper()}_OUT" for i in sr_systems]].sum(axis=1)
            + imod_sum_df[[f"{i.upper()}_IN" for i in sr_systems]].sum(axis=1)
        )
    ).abs()
    * 1000
    / area
)


sr_ribasim = (
    model.basin.time.df[model.basin.time.df.node_id.isin(secondary_basin_node_ids)][["time", "surface_runoff"]]
    .groupby("time")
    .sum()["surface_runoff"]
)

compare_df = pd.concat([sr_ribasim, sr_imod], axis=1)
compare_df.columns = ["Basin (surface_runoff)", f"iMOD ({','.join(sr_systems)})"]
compare_df.cumsum().plot(title="totaal surface_runoff", grid=True, ylabel="afvoer [mm]")
