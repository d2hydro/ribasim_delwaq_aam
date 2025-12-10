# %%
from datetime import datetime

import pandas as pd
from ribasim import Model, Node
from ribasim.nodes import level_boundary
from ribasim_tools.check_model import check_level_boundaries_for_delwaq
from ribasim_tools.get_drainage_from_modflow import AssignOfflineBudgets
from ribasim_tools.knmi_daggegevens import update_meteo
from shapely.geometry import LineString, Point

from ribasim_tools import run_ribasim, settings

# %% [markdown]

## Inlezen model met randvoorwaarden

# inlezen en concentratie aanzetten
model = Model.read(settings.LHM_BA_toml_path)

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
for flow_rate, node_id in flow_rates:
    model.outlet.static.df.loc[model.outlet.static.df.node_id == node_id, "flow_rate"] = flow_rate
    model.outlet.static.df.loc[model.outlet.static.df.node_id == node_id, "max_downstream_level"] = pd.NA

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
model.level_boundary.static.df.loc[1791, "level"] = 20

check_level_boundaries_for_delwaq(model)


# %% [markdown]

## Updaten meteorologische randvoorwaarden
#
# Updaten van de neerslag en verdamping aan de hand van daggegevens bij Meteostation Volkel (375).
# Deze gegevens zijn gedownload van het KNMI als JSON: https://www.knmi.nl/nederland-nu/klimatologie/daggegevens
# Hier maken we de time-table opnieuw aan (recreate_time_table=True) omdat we voor een nieuwe periode gaan rekenen en de bestaande tabel weg willen gooien
# We updaten ook het bestaande model (inplace=True)

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
    grid=True, title=f"Neerslag/Verdamping basin {basin_node_id}"
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


assign_offline_budgets = AssignOfflineBudgets(
    modflow_budgets_path=modflow_budgets_path, metaswap_budgets_path=metaswap_budgets_path
)

model = assign_offline_budgets.compute_budgets(
    model=model,
    primary_budgets=["bdgriv_sys1"],
    secondary_budgets=["bdgriv_sys2", "bdgdrn_sys1", "bdgdrn_sys2", "bdgdrn_sys3", "bdgpssw", "bdgqrun"],
)


basin_area = model.basin.area.df.set_index("node_id").at[basin_node_id, "geometry"].area
df["drainage"] = df["drainage"] * 86400 * 1000 / basin_area
df["infiltration"] = df["infiltration"] * 86400 * 1000 / basin_area
df.groupby(df.index.year)[["drainage", "infiltration"]].cumsum().plot(
    grid=True, title=f"Drainage/Infiltratie basin {basin_node_id}"
)


# %% [markdown]

## Wegschrijven en runnen Ribasim model
model.write(settings.LHM_BA_RVW_toml_path)
run_ribasim(settings.LHM_BA_RVW_toml_path, ribasim_exe=settings.ribasim_exe)
