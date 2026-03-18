# %%
from datetime import datetime

import imod
import numpy as np
import pandas as pd
from ribasim import Model, Node
from ribasim.nodes import level_boundary
from ribasim_tools.check_model import check_level_boundaries_for_delwaq
from ribasim_tools.get_drainage_from_modflow import AssignOfflineBudgets
from ribasim_tools.knmi_daggegevens import update_meteo
from shapely.geometry import LineString, Point

from ribasim_tools import run_ribasim, settings


def get_budgets(
    assign_offline_budgets,
    model,
    primary_budgets,
    secondary_budgets,
    ignore_budgets,
    basin_split: str = "area",
    basin_subtype: str = "state",
    basin_metacol: str = "meta_categorie",
):
    print("📖 read and validate budgets")
    budgets, model = assign_offline_budgets._sync_files(model)

    # Validate budgets
    assign_offline_budgets._validate_budgets(
        budgets=budgets,
        primary_budgets=primary_budgets,
        secondary_budgets=secondary_budgets,
        ignore_budgets=ignore_budgets,
    )

    # Split into primary and secondary basin definition
    print("🪓 split basins into primary and secondary")
    primary_basin_definition, secondary_basin_definition = assign_offline_budgets.split_basin_definitions(
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

    return budgets, primary_basin_mask, secondary_basin_mask


def sum_budgets_per_basin(budgets, basin_mask, nodata=-999):
    print(f"∑ budgets {list(budgets.data_vars)} rasters to basins")
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


# %% [markdown]

# Optioneel hergebruik van bestaande time-table als we níet meteo en drainage willen updaten

REUSE_BASIN_TIME_TABLE = True

if REUSE_BASIN_TIME_TABLE:
    # inlezen geschreven model
    model = Model.read(settings.LHM_BA_RVW_toml_path)
    basin_time_df = model.basin.time.df.copy()

# %% [markdown]

## Inlezen model met randvoorwaarden

# inlezen en concentratie aanzetten
model = Model.read(settings.LHM_BA_toml_path)

if REUSE_BASIN_TIME_TABLE:
    # hergebruiken bestaande time-table
    model.starttime = datetime(2015, 1, 1)
    model.endtime = datetime(2024, 12, 31)
    model.basin.time.df = basin_time_df

# %% markdown

## Fixen basin profiles
#
# Basin-profiles voor hoofdwater en stromend water bevatten veel teveel opperlakte; 90% en 10% respectievelijk. We maken hier 5% van voor nu

node_ids = model.basin.node.df[model.basin.node.df.meta_categorie == "hoofdwater"].index.to_list()
model.basin.profile.df.loc[model.basin.profile.df.node_id.isin(node_ids), "area"] /= 18
node_ids = model.basin.node.df[model.basin.node.df.meta_categorie == "doorgaand"].index.to_list()
model.basin.profile.df.loc[model.basin.profile.df.node_id.isin(node_ids), "area"] /= 2

# %% [markdown]

## Bewerken inlaatcapaciteiten bij Kanaal van Deurne en Defensiekanaal
#
# De Outlets bij het Kanaal van Deurne en Defensiekanaal krijgen een inlaatcapaciteit die overeen komt met
# de gewenste aanvoerdebieten zoals gegeven door Luuk van Gerwen op 7-10-2025
#
# Voor validiteit van Delwaq splitsen we LevelBoundary # 1280 (Kanaal van Deurne) in 2 LevelBoundaries, omdat een 1 LevelBoundary mag linken naar max 1 connector-node
#
# Aan het einde van dit block controlleren we de validiteit van de overige boundary-nodes

level_kanalen = 30.5
flow_rates = [(0.3, 367), (0.1, 2029), (0.025, 2034), (0.025, 601), (0.065, 156), (0.01, 358), (0.03, 331)]
for flow_rate, primary_node_id in flow_rates:
    model.outlet.static.df.loc[model.outlet.static.df.node_id == primary_node_id, "flow_rate"] = flow_rate
    model.outlet.static.df.loc[model.outlet.static.df.node_id == primary_node_id, "max_downstream_level"] = pd.NA

# verplaatsen node 1280 vlakbij outlet node 367
model.level_boundary.node.df.loc[1280, "geometry"] = Point(
    model.outlet[367].geometry.x + 10, model.outlet[367].geometry.y
)
model.link.df.loc[1352, "geometry"] = LineString([model.level_boundary[1280].geometry, model.outlet[367].geometry])

# Nieuwe levelboundary naast outlet node 2029 en link 2134 hier naartoe leiden
outlet_node = model.outlet[2029]


boundary_node = model.level_boundary.add(
    Node(geometry=Point(outlet_node.geometry.x + 10, outlet_node.geometry.y)),
    tables=[level_boundary.Static(level=[level_kanalen])],
)
model.link.df.loc[2134, "from_node_id"] = boundary_node.node_id
model.link.df.loc[2134, "geometry"] = LineString([boundary_node.geometry, outlet_node.geometry])

# set upstream levels voor alle level boundaries bovenstrooms inlaten
node_ids = [model.link.df.set_index("to_node_id").at[flow_rate[1], "from_node_id"] for flow_rate in flow_rates]
node_ids = [i for i in node_ids if i in model.level_boundary.node.df.index]
model.level_boundary.static.df.loc[model.level_boundary.static.df.node_id.isin(node_ids), "level"] = level_kanalen

# Set level Leijsingloop
model.level_boundary.static.df.loc[model.level_boundary.static.df.node_id == 1791, "level"] = 20

check_level_boundaries_for_delwaq(model)


# %% [markdown]

## Updaten meteorologische randvoorwaarden
#
# Updaten van de neerslag en verdamping aan de hand van daggegevens bij Meteostation Volkel (375).
# Deze gegevens zijn gedownload van het KNMI als JSON: https://www.knmi.nl/nederland-nu/klimatologie/daggegevens
# Hier maken we de time-table opnieuw aan (recreate_time_table=True) omdat we voor een nieuwe periode gaan rekenen en de bestaande tabel weg willen gooien
# We updaten ook het bestaande model (inplace=True)

if not REUSE_BASIN_TIME_TABLE:
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

if not REUSE_BASIN_TIME_TABLE:
    modflow_budgets_path = (
        settings.source_data_dir / "GRAM3_2" / "100" / "GRAM32_BASIS1_TA-PRJ" / "RESULTS" / "BASIS1_TA-PRJ"
    )
    metaswap_budgets_path = modflow_budgets_path / "MSWAPINPUT"

    assign_offline_budgets = AssignOfflineBudgets(
        modflow_budgets_path=modflow_budgets_path, metaswap_budgets_path=metaswap_budgets_path
    )

    # model = assign_offline_budgets.compute_budgets(
    #     model=model,
    #     primary_budgets=["bdgriv_sys1"],
    #     secondary_budgets=["bdgriv_sys2", "bdgdrn_sys2", "bdgdrn_sys3", "bdgpssw", "bdgqrun"],
    #     ignore_budgets=["bdgdrn_sys1"],
    # )

    # dit stuk vervangt de regels hierboven. Later moet dit, samen met de gebruikte functies hierboven, de stukken in compute_budgets() vervangen
    primary_budgets = ["bdgriv_sys1"]
    secondary_budgets = ["bdgriv_sys2", "bdgdrn_sys2", "bdgdrn_sys3", "bdgpssw", "bdgqrun"]
    budgets, primary_basin_mask, secondary_basin_mask = get_budgets(
        assign_offline_budgets=assign_offline_budgets,
        model=model,
        primary_budgets=["bdgriv_sys1"],
        secondary_budgets=["bdgriv_sys2", "bdgdrn_sys2", "bdgdrn_sys3", "bdgpssw", "bdgqrun"],
        ignore_budgets=["bdgdrn_sys1"],
    )

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

    basin_area = model.basin.area.df.set_index("node_id").at[basin_node_id, "geometry"].area
    df = model.basin.time.df[model.basin.time.df.node_id == basin_node_id].set_index("time")
    df["drainage"] = df["drainage"] * 86400 * 1000 / basin_area
    df["infiltration"] = df["infiltration"] * 86400 * 1000 / basin_area
    df.groupby(df.index.year)[["drainage", "infiltration"]].cumsum().plot(
        grid=True, title=f"Drainage/Infiltratie basin {basin_node_id}", ylabel="mm", xlabel="tijd"
    )


# %% [markdown]

## Wegschrijven en runnen Ribasim model
model.write(settings.LHM_BA_RVW_toml_path)
if not REUSE_BASIN_TIME_TABLE:
    budgets_df.to_csv(model.filepath.with_name("budgets.csv"))
    budgets_df.to_feather(model.filepath.with_name("budgets.csv"))

run_ribasim(settings.LHM_BA_RVW_toml_path, ribasim_exe=settings.ribasim_exe)

# %% [markdown]

## Plotten resultaten bij outlet

df = pd.read_feather(model.toml_path.parent.joinpath("results", "flow.arrow"))
df[df.link_id == 1986].set_index("time")["flow_rate"].plot(
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
).cumsum().plot(title=f"{primary_node_id} (hoofdsysteem)", grid=True)
compare_series(
    model=model,
    model_node_id=secondary_node_id,
    imod_node_id=primary_node_id,
    systems=secondary_systems,
).cumsum().plot(title=f"{secondary_node_id} (bergend)", grid=True)

# %%
