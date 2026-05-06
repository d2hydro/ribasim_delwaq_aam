# %%
from datetime import datetime

import geopandas as gpd
import pandas as pd
from ribasim import Model, run_delwaq, run_ribasim
from ribasim.delwaq import generate, parse
from ribasim.node import level_boundary
from ribasim_tools.knmi_daggegevens import update_meteo
from ribasim_tools.modflow_metaswap import AssignOfflineBudgets, read_budgets
from ribasim_tools.read_delwaq_fractions import check_nodes_continuity

from ribasim_tools import read_flow_rate, settings

# %% [markdown]

## Inlezen basismodel

# Inlezen
model = Model.read(settings.LHM_BA_toml_path)
model.basin.static.df = None  # op None zetten, want we gaan een time-table gebruiken


# %% [markdown]

## Bewerken inlaatcapaciteiten bij Kanaal van Deurne en Defensiekanaal
#
# Voor validiteit van Delwaq splitsen we LevelBoundary # 1280 (Kanaal van Deurne) in 2 LevelBoundaries, omdat een 1 LevelBoundary mag linken naar max 1 connector-node
#
# Aan het einde van dit block controlleren we de validiteit van de overige boundary-nodes

# level_kanalen = 30.5

# # verplaatsen node 1280 vlakbij outlet node 3090
# model.node.df.loc[1280, "geometry"] = Point(model.outlet[3090].geometry.x + 10, model.outlet[3090].geometry.y)
# model.link.df.loc[2142, "geometry"] = LineString([model.level_boundary[1280].geometry, model.outlet[3090].geometry])

# # van knoop 4109 maken we een boundary die we verbinden met 367
# geometry = model.junction[4109].geometry
# model.remove_node(4109)

# boundary_node = model.level_boundary.add(
#     Node(geometry=geometry),
#     tables=[level_boundary.Static(level=[level_kanalen])],
# )

# outlet_node = model.outlet[367]
# model.link.add(boundary_node, outlet_node)

# # set upstream levels voor alle level boundaries bovenstrooms inlaten

# # Set level Leijsingloop
# model.level_boundary.static.df.loc[model.level_boundary.static.df.node_id == 1791, "level"] = 20

# check_level_boundaries_for_delwaq(model)


# %% [markdown]

## Updaten meteorologische randvoorwaarden
#
# Updaten van de neerslag en verdamping aan de hand van daggegevens bij Meteostation Volkel (375).
# Deze gegevens zijn gedownload van het KNMI als JSON: https://www.knmi.nl/nederland-nu/klimatologie/daggegevens
# Hier maken we de time-table opnieuw aan (recreate_time_table=True) omdat we voor een nieuwe periode gaan rekenen en de bestaande tabel weg willen gooien
# We updaten ook het bestaande model (inplace=True)


print("toekennen uniforme neerslag van Volkel")
starttime = datetime(2015, 1, 1)
endtime = datetime(2024, 12, 31)

update_meteo(
    model,
    station_id=375,
    starttime=starttime,
    endtime=endtime,
    recreate_time_table=True,
    inplace=True,
)

basin_node_id = model.basin.node.df.index[0]
df = model.basin.time.df[model.basin.time.df.node_id == basin_node_id].set_index("time")
df["precipitation"] = df["precipitation"] * 86400 * 1000
df["potential_evaporation"] = df["potential_evaporation"] * 86400 * 1000
df.groupby(df.index.year)[["precipitation", "potential_evaporation"]].cumsum().plot(
    grid=True, title=f"Neerslag/Verdamping basin {basin_node_id}", ylabel="mm", xlabel="tijd"
)


# %% [markdown]

## Updaten drainage en infiltratie uit GRAM
#
# `modflow_budgets_path` met daarin `BDGDRN` en `BDGRIV` sub-folders
# `metaswap_budgets_path` met daarin `bdgPssw` en `bdgqrun` sub-folders
# Met `AssignOfflineBudgets` verwijzen we naar de paden
# Bij `AssignOfflineBudgets.compute_budgets()` specificeren we de lagen die gesommeert primary budgets en secondary budgets zijn
# `Primary` alles wat niet `meta_categorie` == `bergend` heeft


modflow_budgets_path = (
    settings.source_data_dir / "GRAM3_2" / "100" / "GRAM32_BASIS1_TA-PRJ" / "RESULTS" / "BASIS1_TA-PRJ"
)
metaswap_budgets_path = modflow_budgets_path / "MSWAPINPUT"

budgets = read_budgets(
    modflow_budgets_path=modflow_budgets_path,
    metaswap_budgets_path=metaswap_budgets_path,
    starttime=model.starttime,
    endtime=model.endtime,
)

assign_offline_budgets = AssignOfflineBudgets(budgets=budgets)

model, budgets_df = assign_offline_budgets.compute_budgets(
    model=model,
    primary_budgets={"bdgriv_sys1"},
    secondary_budgets={"bdgriv_sys2", "bdgdrn_sys2", "bdgdrn_sys3", "bdgpsswm3"},
    surface_runoff_budgets={"bdgqrunm3"},
    assign_fractions=True,
)

# %% [markdown]

## Bijwerken Basin Fracties (Concentraties)
#
# inlezen de stroomgebieden waarmee we het model hebben geklip, deze bevat:
# - Vlier
# - Oude Aa
# - Bakelse Aa
# - Kaweise Loop
# We moeten deze een beetje compacteren i.v.m. maximale lengte van een DELWAQ sommetje (20 karakters)

# Wat het was
model.basin.concentration.df.head(2)

# Inlezen
clip_boundary_gpkg = settings.source_data_dir.joinpath("shp", "subcatchments_Bakelse_Aa.shp")
catchments_df = gpd.read_file(clip_boundary_gpkg).to_crs(model.crs)

# Mapping
mapping = {"Vlier": "Vlier", "Oude Aa": "Oude_Aa", "Bakelse Aa": "Bakelse_Aa", "Kaweise Loop": "Kaw_Loop"}

# Een Pandas.Series met node_id en prefix
basin_fraction_prefixes = (
    (
        gpd.sjoin(
            model.basin.node.df,
            catchments_df[["DEEL_WL", "geometry"]],
            how="left",
            predicate="within",
        )
        .dropna(subset="DEEL_WL")
        .reset_index()[["node_id", "meta_categorie", "DEEL_WL"]]
    )
    .set_index("node_id")["DEEL_WL"]
    .map(mapping)
)

# Controle of alle basins nu een prefix hebben
assert not basin_fraction_prefixes.isna().any()

# Prefix en van de substance
model.basin.concentration.df["substance"] = (
    model.basin.concentration.df["node_id"].map(basin_fraction_prefixes)
    + "_"
    + model.basin.concentration.df["substance"].astype(str)
)

# E Voila!
model.basin.concentration.df.head(2)

# %% [markdown]

## Aanmaken LevelBoundary Concentraties
# LevelBoundary node_id #53, #1280 en #5139 horen bij Kanaal van Deurne
# LevelBoundary node_id #1568, #1958 en #33 bij Defensiekanaal

time = [model.starttime] * 6
model.level_boundary.concentration = level_boundary.Concentration(
    node_id=[
        53,
        1280,
        # 5139,
        1568,
        1958,
        33,
    ],
    time=time,
    substance=[
        "Kanaal_van_Deurne",
        "Kanaal_van_Deurne",
        # "Kanaal_van_Deurne",
        "Defensiekanaal",
        "Defensiekanaal",
        "Defensiekanaal",
    ],
    concentration=[1] * len(time),
)

# %% [markdown]

## Wegschrijven en runnen Ribasim model
model.write(settings.LHM_BA_RVW_toml_path)
run_ribasim(settings.LHM_BA_RVW_toml_path, ribasim_home=settings.ribasim_home)

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

nmodel = parse(
    settings.LHM_BA_Delwaq_toml_path, graph, substances, output_folder=settings.LHM_BA_Delwaq_output_dir, to_input=True
)

node_ids = check_nodes_continuity(nmodel)


## Plotten resultaten bij outlet

read_flow_rate(model, link_id=1986).plot(
    title="Afvoer Bakelse Aa nabij Zuid-Willemsvaart", grid=True, xlabel="Tijd", ylabel="Afvoer (m3/s)"
)


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
