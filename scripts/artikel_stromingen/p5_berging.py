# %%
import pandas as pd
from ribasim import Model
from ribasim.delwaq import generate, parse
from ribasim.nodes import level_boundary
from ribasim_tools import run_delwaq, run_ribasim, settings

from datetime import timedelta
from ribasim_tools.plot_fractions import plot_fraction, plot_fractional_flow


# %% Inlezen van het weggeschreven Ribasim-model met de geparste Delwaq-fracties.
model = Model.read(settings.LHM_BA_RVW_toml_path)

target_categories = ["hoofdwater", "doorgaand"]
area_factor = {"hoofdwater": 0.05, "doorgaand": 0.05}

# nodes identificeren en verwijderen
target_nodes = model.basin.node.df.loc[
    model.basin.node.df["meta_categorie"].isin(target_categories), ["meta_categorie"]
].copy()

# tabel met streefpeil, categorie en profile_area maken
basin_area_df = (
    model.basin.area.df.set_index("node_id")[["geometry", "meta_streefpeil"]]
    .join(target_nodes, how="inner")
    .dropna(subset=["geometry", "meta_streefpeil"])
)

basin_area_df["profile_area"] = basin_area_df["geometry"].area * basin_area_df["meta_categorie"].map(area_factor)

# %% Verwijder bestaande profielregels voor deze basins
model.basin.profile.df = model.basin.profile.df.loc[~model.basin.profile.df["node_id"].isin(basin_area_df.index)].copy()

# nieuwe profielen toevoegen
new_profile_df = (
    pd.concat(
        [
            basin_area_df.assign(
                node_id=basin_area_df.index,
                level=basin_area_df["meta_streefpeil"] - 2.05,
                area=basin_area_df["profile_area"],
            )[["node_id", "level", "area"]],
            basin_area_df.assign(
                node_id=basin_area_df.index,
                level=basin_area_df["meta_streefpeil"],
                area=basin_area_df["profile_area"],
            )[["node_id", "level", "area"]],
        ],
        ignore_index=True,
    )
    .sort_values(["node_id", "level"])
    .reset_index(drop=True)
)

model.basin.profile.df = (
    pd.concat([model.basin.profile.df, new_profile_df], ignore_index=True)
    .sort_values(["node_id", "level"])
    .reset_index(drop=True)
)

# model.basin.profile.df.loc[model.basin.profile.df["node_id"] == 1486, "level"] = 19
# model.basin.profile.df.loc[model.basin.profile.df["node_id"] == 1512, "level"] = 14.82

# wegschrijven als nieuwe case
nieuwe_toml = settings.LHM_BA_RVW_toml_path.parents[1].joinpath(
    f"{settings.LHM_BA_RVW_toml_path.parent.name}_p95_case", settings.LHM_BA_RVW_toml_path.name
)

model.write(nieuwe_toml)
# v.a. hier DELWAQ een slinger geven en resultaten beoordelen
specs = run_ribasim(nieuwe_toml, ribasim_home=settings.ribasim_home)


# %% ### DELWAQ!
#
from pathlib import Path

delwaq_path = Path(r'C:\GitHub\data\LHM_BA_RVW_p95_case_delwaq')

# Aanmaken van de Delwaq schematisatie
graph, substances = generate(nieuwe_toml, delwaq_path)

# Runnen van Delwaq
dimr_config = delwaq_path / "dimr_config.xml"
specs = run_delwaq(dimr_config=dimr_config, run_dimr_bat=settings.run_dimr_bat)
assert specs.exit_code == 0

# Parsen en controle van Delwaq resultaten. Continuity check voor alle nodes.
model = parse(
    nieuwe_toml, graph, substances, output_folder=delwaq_path, to_input=True
)
model.write(nieuwe_toml)  # saven, zodat we later het model weer kunnen lezen mét fracties

# %% [markdown]

### Inlezen Delwaq resultaten
#
# Inlezen van het weggeschreven Ribasim-model met de geparste Delwaq-fracties.
nieuwe_toml = settings.LHM_BA_RVW_toml_path.parents[1].joinpath(
    f"{settings.LHM_BA_RVW_toml_path.parent.name}_p95_case", settings.LHM_BA_RVW_toml_path.name
)

model = Model.read(nieuwe_toml)

### Plotten van fracties
#
# Eerste controleplots voor continuiteit, default tracers en alle user-defined tracers.
node_id = 1216  # Bakelse Aa
link_id = 1986  # Uitlaat Bakelse Aa

default_tracers = ["LevelBoundary", "Initial", "Drainage", "Precipitation", "SurfaceRunoff"]

color_dict = {
    "Neerslag": "#1f77b4",  # blauw (vast)
    "Maaiveld afvoer": "#ff7f0e",  # oranje
    "Randvoorwaarde": "#d62728",  # rood
    "Drainage": "#2ca02c",  # groen
    "Initieel": "#7f7f7f",  # grijs (vast)
}

groups = {
    "Neerslag": "Precipitation",  # Precipitation wordt Neerslag
    "Maaiveld afvoer": "SurfaceRunoff",  # alles met qrun wordt Maaiveld afvoer
    "Randvoorwaarde":"LevelBoundary",
    "Drainage": "Drainage",
    "Initieel": "Initial",  # Initial wordt Initieel, want dat is Nederlands
}

plot_fraction(model, 
              node_id, 
              tracers=default_tracers, 
              color_dict=color_dict, 
              groups=groups, 
              title=False,
              add_legend=False, 
              starttime="2015-01-01", 
              endtime="2016-01-01")


# %%
