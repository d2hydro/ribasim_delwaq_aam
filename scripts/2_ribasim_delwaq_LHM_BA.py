# %%
from datetime import datetime

import geopandas as gpd
from ribasim import Model
from ribasim.delwaq import generate, parse
from ribasim.nodes import level_boundary
from ribasim_tools.knmi_daggegevens import update_meteo
from ribasim_tools.modflow_metaswap import AssignOfflineBudgets, read_budgets
from ribasim_tools.plot_fractions import plot_fraction
from ribasim_tools.read_delwaq_fractions import check_nodes_continuity

from ribasim_tools import resolve_mfms_path, run_delwaq, run_ribasim, settings

# %% [markdown]

### Inlezen basismodel

model = Model.read(settings.LHM_BA_toml_path)
model.basin.static.df = None  # op None zetten, want we gaan een time-table gebruiken

# %% [markdown]

### Updaten meteorologische randvoorwaarden
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

# Plotje met de neerslag
basin_node_id = model.basin.node.df.index[0]
df = model.basin.time.df[model.basin.time.df.node_id == basin_node_id].set_index("time")
df["precipitation"] = df["precipitation"] * 86400 * 1000
df["potential_evaporation"] = df["potential_evaporation"] * 86400 * 1000
df.groupby(df.index.year)[["precipitation", "potential_evaporation"]].cumsum().plot(
    grid=True, title=f"Neerslag/Verdamping basin {basin_node_id}", ylabel="mm", xlabel="tijd"
)

# %% [markdown]

### Updaten drainage en infiltratie uit GRAM
#
# `modflow_budgets_path` met daarin `BDGDRN` en `BDGRIV` sub-folders
# `metaswap_budgets_path` met daarin `bdgPssw` en `bdgqrun` sub-folders
# Met `AssignOfflineBudgets` verwijzen we naar de paden
# Bij `AssignOfflineBudgets.compute_budgets()` specificeren we de lagen die gesommeert primary budgets en secondary budgets zijn
# `Primary` alles wat niet `meta_categorie` == `bergend` heeft
#
# Er wordt tegelijk (deel-)fracties weggeschreven in de basin.concentration tabel.

modflow_budgets_path = resolve_mfms_path(settings.source_data_dir.joinpath("GRAM3_2", "100", "GRAM32_BASIS1_TA-PRJ"))
# modflow_budgets_path = (
#     settings.source_data_dir / "GRAM3_2" / "100" / "GRAM32_BASIS1_TA-PRJ" / "RESULTS" / "BASIS1_TA-PRJ"
# )
metaswap_budgets_path = modflow_budgets_path / "MSWAPINPUT"

# budgets lezen uit MODFLOW en MetaSWAP (xr.DataSet)
budgets = read_budgets(
    modflow_budgets_path=modflow_budgets_path,
    metaswap_budgets_path=metaswap_budgets_path,
    starttime=model.starttime,
    endtime=model.endtime,
)

# toekennen van de budgetten aan de basins. Assign_fractions=True, want dan hebben we die ook direct.
assign_offline_budgets = AssignOfflineBudgets(budgets=budgets)

model, budgets_df = assign_offline_budgets.compute_budgets(
    model=model,
    primary_budgets={"bdgriv_sys1"},
    secondary_budgets={"bdgriv_sys2", "bdgdrn_sys2", "bdgdrn_sys3", "bdgpsswm3"},
    surface_runoff_budgets={"bdgqrunm3"},
    assign_fractions=True,
)

# %% [markdown]

### Bijwerken Basin Fracties (concentratie-tabel)
#
# inlezen de stroomgebieden waarmee we het model hebben geklip, deze bevat:
# - Vlier
# - Oude Aa
# - Bakelse Aa
# - Kaweise Loop
# We moeten deze een beetje compacteren i.v.m. maximale lengte van een DELWAQ sommetje (20 karakters)

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

# E Voila (kijk naar kolom substance)!
model.basin.concentration.df.head(2)

# %% [markdown]

### Aanmaken LevelBoundary Concentraties
#
# LevelBoundary node_id #53 en #1280 horen bij Kanaal van Deurne
# LevelBoundary node_id #1568, #1958 en #33 bij Defensiekanaal

time = [model.starttime] * 5
model.level_boundary.concentration = level_boundary.Concentration(
    node_id=[
        53,
        1280,
        1568,
        1958,
        33,
    ],
    time=time,
    substance=[
        "Kanaal_van_Deurne",
        "Kanaal_van_Deurne",
        "Defensiekanaal",
        "Defensiekanaal",
        "Defensiekanaal",
    ],
    concentration=[1] * len(time),
)

# %% [markdown]

### Wegschrijven en runnen Ribasim model
#
# we schrijven ook direct de budgetten per basin weg als CSV; altijd handig!
model.write(settings.LHM_BA_RVW_toml_path)
budgets_df.to_csv(settings.LHM_BA_RVW_toml_path.parent.with_name("mfms_budgetten.csv.zip"))
specs = run_ribasim(settings.LHM_BA_RVW_toml_path, ribasim_home=settings.ribasim_home)
assert specs.exit_code == 0

# %% [markdown]

### DELWAQ!
#
# Aanmaken van de Delwaq schematisatie
graph, substances = generate(settings.LHM_BA_RVW_toml_path, settings.LHM_BA_Delwaq_output_dir)

# Runnen van Delwaq
dimr_config = settings.LHM_BA_Delwaq_output_dir / "dimr_config.xml"
specs = run_delwaq(dimr_config=dimr_config, run_dimr_bat=settings.run_dimr_bat)
assert specs.exit_code == 0

# Parsen en controle van Delwaq resultaten. Continuity check voor alle nodes.
model = parse(
    settings.LHM_BA_RVW_toml_path, graph, substances, output_folder=settings.LHM_BA_Delwaq_output_dir, to_input=True
)
model.write(settings.LHM_BA_RVW_toml_path)  # saven, zodat we later het model weer kunnen lezen mét fracties

# Checken continuiteit
node_ids = check_nodes_continuity(model)
if node_ids:
    raise ValueError(
        f"Continuiteitsproblemen bij {node_ids}. Dit betekent dat er ergens water is verloren gegaan/bij gekomen, dus eerst oplossen!"
    )

# %% [markdown]

### Plotten
# Wat eerste resultaten bij de Outlet
#
# Continuiteit (altijd even checken of deze 1 is over de hele tijdseries)
plot_fraction(model=model, node_id=1216, tracers=["Continuity"], legend_outside_figure=True)

# Default tracers voor DELWAQ; moeten ook optellen tot 1
plot_fraction(model=model, node_id=1216, legend_outside_figure=True)

# Onze eigen tracers; ook die tellen op tot 1, anders zijn we wat vergeten te labellen
tracers = (
    ["Initial", "Precipitation"]
    + list(model.basin.concentration.df.substance.unique())
    + list(model.level_boundary.concentration.df.substance.unique())
)
plot_fraction(model=model, node_id=1216, tracers=tracers, legend_outside_figure=True)
