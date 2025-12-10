# %%

import geopandas as gpd
from ribasim import Model
from ribasim.delwaq import generate, parse
from ribasim.nodes import basin, level_boundary
from ribasim_tools.check_model import check_level_boundaries_for_delwaq
from ribasim_tools.plot_fractions import plot_fraction, plot_fractional_flow
from ribasim_tools.read_delwaq_fractions import check_nodes_continuity

from ribasim_tools import run_delwaq, run_ribasim, settings

# %% [markdown]

## Inlezen model met randvoorwaarden

# inlezen en concentratie aanzetten
model = Model.read(settings.LHM_BA_RVW_toml_path)
model.experimental.concentration = True
check_level_boundaries_for_delwaq(model)

# %% [markdown]

## Toevoegen concentraties aan level_boundaries
#
# Op de waterstandsranden bij bovengenoemde inlaten differentieren we in het Kanaal van Deurne en het Defensiekanaal

time = [model.starttime] * 4

model.level_boundary.concentration = level_boundary.Concentration(
    node_id=[1280, 53, 1958, 1568],
    time=time,
    substance=["Kanaal_van_Deurne", "Kanaal_van_Deurne", "Defensiekanaal", "Defensiekanaal"],
    concentration=[1, 1, 1, 1],
)

# %% [markdown]

## Toevoegen concentraties aan basins
# - Differentieren tussen Oude Aa, Vlier, Kaweise Loop en Bakelse Aa
# - We maken onderscheid tussen stromend en bergend water

clip_boundary_gpkg = settings.source_data_dir.joinpath("shp", "subcatchments_Bakelse_Aa.shp")
catchments_df = gpd.read_file(clip_boundary_gpkg).to_crs(model.crs)

basin_fractions = (
    gpd.sjoin(
        model.basin.node.df,
        catchments_df[["DEEL_WL", "geometry"]],
        how="left",
        predicate="within",
    )
    .dropna(subset="DEEL_WL")
    .reset_index()[["node_id", "meta_categorie", "DEEL_WL"]]
)
basin_fractions.replace(to_replace="hoofdwater", value="stromend", inplace=True)
basin_fractions.replace(to_replace="doorgaand", value="stromend", inplace=True)
basin_fractions["substance"] = (basin_fractions["DEEL_WL"] + "_" + basin_fractions["meta_categorie"]).str.replace(
    " ", "_"
)
basin_fractions["substance"] = basin_fractions["substance"].str[:20]

time = [model.starttime] * len(basin_fractions)
model.basin.concentration = basin.Concentration(
    node_id=basin_fractions.node_id.to_list(),
    time=time,
    substance=basin_fractions.substance.to_list(),
    drainage=[1] * len(basin_fractions),
    precipitation=[1] * len(basin_fractions),
    surface_runoff=[1] * len(basin_fractions),
)

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
default_tracers = ["LevelBoundary", "Initial", "Drainage", "Precipitation"]

user_tracers = (
    ["Initial"]
    + list(model.basin.concentration.df.substance.unique())
    + list(model.level_boundary.concentration.df.substance.unique())
)

plot_fraction(nmodel, 1216, ["Continuity"])

plot_fraction(nmodel, 1216, default_tracers)

plot_fraction(
    model=nmodel,
    node_id=1216,
    tracers=user_tracers,
)

plot_fractional_flow(nmodel, 1216, 1986, tracers=default_tracers)

plot_fractional_flow(nmodel, 1216, 1986, tracers=user_tracers)
