# %%
import geopandas as gpd
from ribasim import Model, Node
from ribasim.delwaq import generate, parse, plot_fraction
from ribasim.nodes import basin, level_boundary
from shapely.geometry import LineString, Point

from ribasim_tools import run_delwaq, run_ribasim, settings
from ribasim_tools.check_model import check_level_boundaries_for_delwaq

# %% [markdown]

## Inlezen geknipte model

# inlezen en concentratie aanzetten
toml_path = settings.data_dir.joinpath("lhm_aam", "LHM_AAM_clipped", "aam.toml")
model = Model.read(toml_path)
model.experimental.concentration = True


# %% [markdown]

## Bewerken randvoorwaarden
#
# De Outlets bij het Kanaal van Deurne en Defensiekanaal krijgen een inlaatcapaciteit die overeen komt met
# de gewenste aanvoerdebieten zoals gegeven door Luuk van Gerwen op 7-10-2025
#
# Voor validiteit van Delwaq splitsen we LevelBoundary # 1280 (Kanaal van Deurne) in 2 LevelBoundaries, omdat een 1 LevelBoundary mag linken naar max 1 connector-node
#
# Aan het einde van dit block controlleren we de validiteit van de overige boundary-nodes

for flow_rate, node_id in [(0.3, 367), (0.1, 2029), (0.025, 2034), (0.025, 601), (0.075, 156)]:
    model.outlet.static.df.loc[model.outlet.static.df.node_id == node_id, "flow_rate"] = flow_rate

# verplaatsen node 1280 vlakbij outlet node 367
model.level_boundary.node.df.loc[1280, "geometry"] = Point(
    model.outlet[367].geometry.x + 10, model.outlet[367].geometry.y
)
model.link.df.loc[1352, "geometry"] = LineString([model.level_boundary[1280].geometry, model.outlet[367].geometry])

# Nieuwe levelboundary naast outlet node 2029 en link 2134 hier naartoe leiden
outlet_node = model.outlet[2029]
level = model.level_boundary.static[1280].level.iloc[0]

boundary_node = model.level_boundary.add(
    Node(geometry=Point(outlet_node.geometry.x + 10, outlet_node.geometry.y)),
    tables=[level_boundary.Static(level=[level])],
)
model.link.df.loc[2134, "from_node_id"] = boundary_node.node_id
model.link.df.loc[2134, "geometry"] = LineString([boundary_node.geometry, outlet_node.geometry])

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

clip_boundary_gpkg = settings.data_dir.joinpath("shp", "subcatchments_Bakelse_Aa.shp")
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
toml_path = toml_path.parent.with_name("LHM_AAM_delwaq") / toml_path.name
model.write(toml_path)
run_ribasim(model.filepath, ribasim_exe=settings.ribasim_exe)

# %% [markdown]

# Aanmaken van de Delwaq schematisatie
output_path = model.filepath.parent.joinpath("delwaq")
graph, substances = generate(toml_path, output_path)
list(substances)

# %% [markdown]

# Runnen van Delwaq
dimr_config = output_path / "dimr_config.xml"
specs = run_delwaq(dimr_config=dimr_config, run_dimr_bat=settings.run_dimr_bat)
assert specs.exit_code == 0


# %% [ markdown]

# Parsen van de resultaten
nmodel = parse(toml_path, graph, substances, output_folder=output_path)
plot_fraction(nmodel, 1216, substances)
