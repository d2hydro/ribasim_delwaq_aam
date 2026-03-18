# %%

from datetime import timedelta

import pandas as pd
from ribasim import Model
from ribasim.delwaq import generate, parse
from ribasim.nodes import basin, level_boundary
from ribasim_tools.check_model import check_level_boundaries_for_delwaq
from ribasim_tools.plot_fractions import plot_fraction, plot_fractional_flow
from ribasim_tools.read_delwaq_fractions import check_nodes_continuity

from ribasim_tools import run_delwaq, run_ribasim, settings

# %% [markdown]
period: timedelta | None = timedelta(days=365)
period = None
## Inlezen model met randvoorwaarden

# inlezen en concentratie aanzetten
model = Model.read(settings.LHM_BA_RVW_toml_path)
if period is not None:
    model.endtime = model.starttime + period
model.experimental.concentration = True
check_level_boundaries_for_delwaq(model)

# %% [markdown]

## Toevoegen concentraties aan level_boundaries
#
# Op de waterstandsranden bij bovengenoemde inlaten differentieren we in het Kanaal van Deurne en het Defensiekanaal

time = [model.starttime] * 6

model.level_boundary.concentration = level_boundary.Concentration(
    node_id=[33, 53, 1280, 1568, 1958, 3397],
    time=time,
    substance=[
        "Defensiekanaal",
        "Kanaal_van_Deurne",
        "Kanaal_van_Deurne",
        "Defensiekanaal",
        "Defensiekanaal",
        "Kanaal_van_Deurne",
    ],
    concentration=[1] * len(time),
)

# %% [markdown]

## Toevoegen concentraties aan basins
# - Differentieren tussen Oude Aa, Vlier, Kaweise Loop en Bakelse Aa
# - We maken onderscheid tussen stromend en bergend water

# clip_boundary_gpkg = settings.source_data_dir.joinpath("shp", "subcatchments_Bakelse_Aa.shp")
# catchments_df = gpd.read_file(clip_boundary_gpkg).to_crs(model.crs)

# basin_fractions = (
#     gpd.sjoin(
#         model.basin.node.df,
#         catchments_df[["DEEL_WL", "geometry"]],
#         how="left",
#         predicate="within",
#     )
#     .dropna(subset="DEEL_WL")
#     .reset_index()[["node_id", "meta_categorie", "DEEL_WL"]]
# )
# basin_fractions.replace(to_replace="hoofdwater", value="stromend", inplace=True)
# basin_fractions.replace(to_replace="doorgaand", value="stromend", inplace=True)
# basin_fractions["substance"] = (basin_fractions["DEEL_WL"] + "_" + basin_fractions["meta_categorie"]).str.replace(
#     " ", "_"
# )
# basin_fractions["substance"] = basin_fractions["substance"].str[:20]

# time = [model.starttime] * len(basin_fractions)

# model.basin.concentration = basin.Concentration(
#     node_id=basin_fractions.node_id.to_list(),
#     time=time,
#     substance=basin_fractions.substance.to_list(),
#     drainage=[1] * len(basin_fractions),
#     precipitation=[1] * len(basin_fractions),
#     surface_runoff=[1] * len(basin_fractions),
# )


budgets_df = pd.read_feather(settings.LHM_BA_RVW_toml_path.with_name("budgets.arrow"))
mask = (budgets_df.index.get_level_values("time") >= model.starttime) & (
    budgets_df.index.get_level_values("time") <= model.endtime
)
budgets_df = budgets_df[mask]
# sum all budgets (columns) and create drainage and infiltration series
drainage_budgets_df = budgets_df.clip(upper=0).abs()
drainage_sum = pd.Series(drainage_budgets_df.sum(axis=1))

# TODO: dit netjes schaalbaar maken met script 3_rvw_LHM_BA.py
primary_budgets = ["bdgriv_sys1"]
secondary_budgets = ["bdgriv_sys2", "bdgdrn_sys2", "bdgdrn_sys3", "bdgpssw", "bdgqrun"]

secondary_basin_ids = model.basin.node.df[model.basin.node.df["meta_categorie"] == "bergend"].index.values
primary_basin_ids = model.basin.node.df[model.basin.node.df["meta_categorie"] != "bergend"].index.values

pd.Series(budgets_df.sum(axis=1))
mask = drainage_budgets_df.notna() & (drainage_budgets_df != 0)
concentrations = drainage_budgets_df.div(drainage_sum, axis=0).where(mask, 0)


def make_budget_concentration_table(concentrations, basin_ids, budget):
    df = concentrations.loc[basin_ids].reset_index()[["node_id", "time", budget]].rename(columns={budget: "drainage"})
    df["substance"] = budget
    df["precipitation"] = float(0)
    df["surface_runoff"] = float(0)
    return df


concentration_df = pd.concat(
    [
        basin.Concentration(
            node_id=primary_basin_ids,
            time=[model.starttime] * len(primary_basin_ids),
            substance=primary_budgets * len(primary_basin_ids),
            drainage=[1] * len(primary_basin_ids),
            precipitation=[0] * len(primary_basin_ids),
            surface_runoff=[0] * len(primary_basin_ids),
        ).df
    ]
    + [make_budget_concentration_table(concentrations, secondary_basin_ids, budget) for budget in secondary_budgets],
    ignore_index=True,
)


model.basin.concentration.df = concentration_df


# %% [markdown]

## Wegschrijven en runnen van het Ribasim model
model.write(settings.LHM_BA_Delwaq_toml_path)
run_ribasim(settings.LHM_BA_Delwaq_toml_path, ribasim_exe=settings.ribasim_exe)

# %% [markdown]

# Aanmaken van de Delwaq schematisatie
graph, substances = generate(settings.LHM_BA_Delwaq_toml_path, settings.LHM_BA_Delwaq_output_dir)
list(substances)

# %% [markdown]

# Runnen van Delwaq
dimr_config = settings.LHM_BA_Delwaq_output_dir / "dimr_config.xml"
specs = run_delwaq(dimr_config=dimr_config, run_dimr_bat=settings.run_dimr_bat)
assert specs.exit_code == 0


# %% [ markdown]

# Parsen en controle van Delwaq resultaten. Continuity check voor alle nodes.

nmodel = parse(settings.LHM_BA_Delwaq_toml_path, graph, substances, output_folder=settings.LHM_BA_Delwaq_output_dir)

node_ids = check_nodes_continuity(nmodel)

# %% [ markdown]
# Plotten van resultaten
node_id = 1216  # Bakelse Aa
link_id = 1986  # Uitlaat Bakelse Aa
default_tracers = ["LevelBoundary", "Initial", "Drainage", "Precipitation"]

user_tracers = (
    ["Initial", "Precipitation"]
    + list(model.basin.concentration.df.substance.unique())
    + list(model.level_boundary.concentration.df.substance.unique())
)

plot_fraction(nmodel, node_id, ["Continuity"])

plot_fraction(nmodel, node_id, default_tracers)

plot_fraction(
    model=nmodel,
    node_id=node_id,
    tracers=user_tracers,
    legend_outside_figure=True,
)

plot_fractional_flow(nmodel, node_id, link_id, tracers=default_tracers)

# %% [markdown]
location_id = "ADCP261B"
df = pd.read_csv(settings.source_data_dir.joinpath("afvoermetingen", "OPP_discharge_2020_now.csv"), index_col=0)
df = df[(df["location_id"] == location_id) & (df["flag"] <= 2)][["value"]]
df.rename(columns={"value": "Meting"}, inplace=True)
df.index = pd.to_datetime(df.index)
observations = df.resample("D").mean(numeric_only=True)["Meting"]
ax = plot_fractional_flow(
    nmodel,
    node_id,
    link_id,
    tracers=user_tracers,
    legend_outside_figure=True,
    observations=None,
    starttime=model.starttime,
    endtime=model.endtime - timedelta(days=1),
    title=f"Afvoer Bakelse Aa ({location_id})",
    ylabel="Afvoer (m3/s)",
    xlabel="Tijd",
    ymax=11,
)


# %%
