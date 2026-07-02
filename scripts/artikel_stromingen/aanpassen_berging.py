# %%
import pandas as pd
from ribasim import Model

from ribasim_tools import settings

# %% Inlezen van het weggeschreven Ribasim-model met de geparste Delwaq-fracties.
model = Model.read(settings.LHM_BA_RVW_toml_path)

target_categories = ["hoofdwater", "doorgaand"]
area_factor = {"hoofdwater": 0.9, "doorgaand": 0.1}

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
                level=basin_area_df["meta_streefpeil"] - 2.0,
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

# wegschrijven als nieuwe case
output_toml = settings.LHM_BA_RVW_toml_path.parents[1].joinpath(
    f"{settings.LHM_BA_RVW_toml_path.parent.name}_p90_case", settings.LHM_BA_RVW_toml_path.name
)

model = Model.write(settings.LHM_BA_RVW_toml_path.parent)
# v.a. hier DELWAQ een slinger geven en resultaten beoordelen
