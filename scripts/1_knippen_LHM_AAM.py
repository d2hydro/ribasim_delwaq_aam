# %%
import geopandas as gpd
from ribasim import Model, run_ribasim

from ribasim_tools import clip_model, run_ribasim, settings

# %% [markdown]

### lees model en knip polygon in
#
# Let op (!):
# - polygon moet dezelfde CRS hebben als het model
# - individuele shapes in de polygonen-file kunnen slivers bevatten. Lossen we hier op door te bufferen en ontbufferen

model = Model.read(settings.LHM_AAM_toml_path)

clip_boundary_gpkg = settings.source_data_dir.joinpath("shp", "subcatchments_Bakelse_Aa.shp")
polygon = gpd.read_file(clip_boundary_gpkg).to_crs(model.crs).union_all().buffer(1).buffer(-1)


# %% [markdown]
### clip-functie
#
# Met de `clip_model` kunnen we instellen:
# - `keep_node_ids`: knopen die buiten de polygon vallen, maar we willen houden
# - `drop_node_ids`: knopen die bínnen de polygon vallen, maar we willen weggooien
# - `convert_node_types`: Basins die we toevoegen búiten het gebied worden LevelBoundaries en die mogen niet met ManningResistances worden verbonden
# - `default_flow_rate`: Capaciteit voor de ManningResistances die worden geconverteert naar Outlets. LevelBoundaries krijgen de Basin.state mee als level
#
# De functie print Links trough polygon-boundary: [...]. Hierin staan de links die door de rand gaan.
# Door die lijst te inspecteren in het te knippen model kun je de `keep_node_ids`, `drop_node_ids` en `convert_node_types` goed zetten.

clip_model(
    model=model,
    polygon=polygon,
    keep_node_ids=[
        72,  # uitlaat
        367,  # inlaat Oude Aa @ kanaal van deurne
        709,  # Essenloopje (Kaweise Loop)
        1280,  # Kanaal van Deurne
        1791,  # loopje afwaterend Oude Aa
        1846,  # Basin bij Kaweise Loop
        1942,  # Essenloopje
        4109,  # Junction bij Kanaal v Deurne
    ],
    drop_node_ids=[86, 52, 447, 3306, 3655, 3730, 3653, 3302, 3726],
    convert_node_types={
        1942: "LevelBoundary",  # essenloopje
        1791: "LevelBoundary",  # lopoje afwaterend Oude Aa
        1280: "LevelBoundary",  # Kanaal van deurne
        709: "Outlet",
    },
    default_flow_rate=25,
    inplace=True,
)

# %% [markdown]
### wegschrijven en runnen model
#
# Set `model.use_validation = False`: wanneer het niet lukt het model weg te schrijven, omdat er nog fouten in zitten
# Bij `run_ribasim()` print de rekenkern de foute verbindingen

model.write(settings.LHM_BA_toml_path)
run_ribasim(model.filepath, ribasim_home=settings.ribasim_home)
