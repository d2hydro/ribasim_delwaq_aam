# %%
from ribasim import Model
from ribasim_tools.case_conversions import pascal_to_snake_case

from ribasim_tools import run_ribasim, settings

# =============================================================================
# Paden
# =============================================================================
src_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "3_basin_area_vergroten_ns")
src_dir_file = src_dir / "hsa.toml"
dst_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "4_merge_basins_ns")
dst_toml_file = dst_dir / "hsa.toml"

# =============================================================================
# Instellingen
# =============================================================================
REMOVE_NODES = [40000219, 40001316]
BASIN_NODE_IDS = [40000042, 30000029, 30000495, 20000016]
BASIN_AREA_MULTIPLICATION_FACTOR = 20
EXECUTE_MODEL = False
LINK_NODES = [(50000263, 40000042), (40000042, 90000001)]


# =============================================================================
# Helper functies
# =============================================================================
def remove_node(model, node_id: int):
    # remove node from tables
    for sub in model._nodes():
        assert sub.node.df is not None
        if node_id in sub.node.df.index:
            # Remove from node table
            sub.node.df = sub.node.df.drop(node_id)
            if sub.node.df.empty:
                sub.node.df = None

            # Remove from data tables
            for table in sub._tables():
                if table.df is not None and "node_id" in table.df.columns:
                    table.df = table.df[table.df["node_id"] != node_id]
                    if table.df.empty:
                        table.df = None

            break

    # remove node from link
    if model.link.df is not None:
        model.link.df = model.link.df.loc[
            (model.link.df["from_node_id"] != node_id) & (model.link.df["to_node_id"] != node_id)
        ]
        if model.link.df.empty:
            model.link.df = None


def link_nodes(model: Model, links: list[tuple[int, int]]):
    node_type = model.node_table().df["node_type"]
    for from_node_id, to_node_id in links:
        from_node = getattr(model, pascal_to_snake_case(node_type[from_node_id]))[from_node_id]
        to_node = getattr(model, pascal_to_snake_case(node_type[to_node_id]))[to_node_id]
        model.link.add(from_node=from_node, to_node=to_node)


# =============================================================================
# INLEZEN MODEL EN BASINS SAMENVOEGEN
# =============================================================================

model = Model.read(src_dir_file)

# verwijderen nodes en links
for node_id in REMOVE_NODES:
    remove_node(model, node_id)

# toevoegen links
link_nodes(model=model, links=LINK_NODES)

# vergroten basin area (volume) zodat totale volume ongeveer hetzelfde blijft
model.basin.profile.df.loc[model.basin.profile.df.node_id.isin(BASIN_NODE_IDS), "area"] *= (
    BASIN_AREA_MULTIPLICATION_FACTOR
)

model.write(dst_toml_file)

# =============================================================================
# Run model
# =============================================================================
if EXECUTE_MODEL:
    run_ribasim(toml_path=dst_toml_file, ribasim_exe=settings.ribasim_exe)
