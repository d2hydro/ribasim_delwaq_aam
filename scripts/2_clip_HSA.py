# %% [markdown]
### Clip HSA-model met ribasim_tools.clip_model
# Importeer packages

import geopandas as gpd
from ribasim import Model

from ribasim_tools import clip_model, run_ribasim, settings

# %% [markdown]

### lees model en knip polygon in
#
# Let op (!):
# - polygon moet dezelfde CRS hebben als het model
# - individuele shapes in de polygonen-file kunnen slivers bevatten. Lossen we hier op door te bufferen en ontbufferen

toml_path = settings.source_data_dir.joinpath("hsa_model", "ribasim.toml")
model = Model.read(toml_path)

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
        40001971,
        10000233,
        30001270,
        30000120,
        10000224,
        40000035,
        40000172,
        40000434,
        40000832,
        40000308,
        50000070,
        40001927,  # control pump
        40001926,  # extra takje
        40000197,  # extra takje
    ],
    drop_node_ids=[],
    convert_node_types={
        10000233: "LevelBoundary",
        30000120: "LevelBoundary",
        10000224: "LevelBoundary",
        40000035: "LevelBoundary",
        40000172: "LevelBoundary",
        40000434: "LevelBoundary",
        40000308: "LevelBoundary",
        40000832: "LevelBoundary",
        50000070: "LevelBoundary",
    },
    inplace=True,
)

# %% [markdown]
### wegschrijven model
#
# Set `model.use_validation = False`: wanneer het niet lukt het model weg te schrijven, omdat er nog fouten in zitten
# Bij `run_ribasim()` print de rekenkern de foute verbindingen
model.use_validation = True
model.write(settings.processed_data_dir / "hsa_model_clipped" / "ribasim.toml")
run_ribasim(model.filepath, ribasim_exe=settings.ribasim_exe)

# %%
