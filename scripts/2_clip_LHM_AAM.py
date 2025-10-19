# %%
import geopandas as gpd
from ribasim import Model

from ribasim_tools import settings
from ribasim_tools.case_conversions import pascal_to_snake_case

# %% inlezen model en clip-shape
toml_path = settings.data_dir.joinpath("lhm_aam", "AaenMaas_2025_9_0", "aam.toml")
model = Model.read(toml_path)

clip_boundary_gpkg = settings.data_dir.joinpath("shp", "subcatchments_Bakelse_Aa.shp")
polygon = gpd.read_file(clip_boundary_gpkg).to_crs(model.crs).union_all()


# %% clip-functie

keep_node_ids = []
drop_node_ids = []

# first estimate off node_ids
node_ids = keep_node_ids + model.basin.node.df.within(polygon).index.to_list()
node_ids = [node_id for node_id in node_ids if node_ids not in drop_node_ids]

# get links trough polygon boundary
links = model.link.df[model.link.df.intersects(polygon.exterior)]

node_df = model.node_table().df
conversion_node_types: dict[int:str] = {}

for link in links.itertuples():
    us_node_geometry, ds_node_geometry = link.geometry.boundary.geoms
    # if line starts and ends in polygon, we don't need to expand node-ids
    if us_node_geometry.within(polygon) and ds_node_geometry.within(polygon):
        continue
    if us_node_geometry.within(polygon):
        us_node_id = link.from_node_id
        # TODO: add logic to find all downstream node_ids and add them to node_ids
        # TODO: expand conversion_node_types Basin -> LevelBoundary and (possibly) ManningResistance -> Outlet
    if ds_node_geometry.within(polygon):
        ds_node_id = link.from_node_id
        # TODO: add logic to find all upstream node_ids and add them to node_ids
        # TODO: expand conversion_node_types Basin -> LevelBoundary and (possibly) ManningResistance -> Outlet

# TODO: get logic for deleting node_ids from all tables from RIBASIM-nl


# convert to drop_nodes function
drop_node_ids = node_df[~node_df.index.isin(node_ids)].index.to_list()

for node_type, node_type_df in node_df.loc[drop_node_ids].groupby("node_type"):
    drop_node_ids_from_tables = node_type_df.index
    # read table
    table = getattr(model, pascal_to_snake_case(node_type))

    # remove node from all tables
    for attr in table.model_fields.keys():
        df = getattr(table, attr).df
        if df is not None:
            if "node_id" in df.columns:
                getattr(table, attr).df = df[~df.node_id.isin(drop_node_ids_from_tables)]
            else:
                getattr(table, attr).df = df[~df.index.isin(drop_node_ids_from_tables)]


model.use_validation = False
model.write(toml_path.parent.with_name("LHM_AAM_clipped") / toml_path.name)

# %%
