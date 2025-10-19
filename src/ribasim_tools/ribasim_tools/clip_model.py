from ribasim import Model, Node
from ribasim.nodes import level_boundary, outlet
from shapely.geometry import Polygon

from ribasim_tools.case_conversions import pascal_to_snake_case
from ribasim_tools.drop_nodes import drop_nodes


def clip_model(
    model: Model,
    polygon: Polygon,
    keep_node_ids: list[int],
    drop_node_ids: list[int],
    convert_node_types: dict[int:str],
    default_flow_rate: float = 25,
):
    """Clip a model by a polygon

    Args:
        model (Model): ribasim model to clip
        polygon (Polygon): polygon to clip model by
        keep_node_ids (list[int]): extra nodes to keep (outside polygon)
        drop_node_ids (list[int]): extra nodes to drop (inside polygon)
        convert_node_types (_type_): nodes to convert to another type
        default_flow_rate (float, optional): flow_rate in case ManningResistances are converted to Outlets. Defaults to 25.
    """
    # first get all nodes within polygon or keep_ids and reduce by drop_node_ids
    node_df = model.node_table().df
    node_ids = keep_node_ids + node_df[node_df.within(polygon)].index.to_list()

    # convert to drop node ids
    drop_node_ids += node_df[~node_df.index.isin(node_ids)].index.to_list()
    drop_nodes(model=model, drop_node_ids=drop_node_ids)

    # get links trough polygon boundary
    links = model.link.df[model.link.df.intersects(polygon.exterior)]
    print(f"Links trough polygon-boundary: {links.index.to_list()}")

    # %% update node-types

    default_flow_rate = 25

    node_table_df = model.node_table().df

    for node_id, node_type in convert_node_types.items():
        existing_node_type = node_table_df.at[node_id, "node_type"]
        # get table
        table = getattr(model, pascal_to_snake_case(existing_node_type))

        # save node-attributes, so we can add it later. Pop node-type as we'll change that
        node_dict = table.node.df.loc[node_id].to_dict()
        node_dict.pop("node_type")
        node_dict["node_id"] = node_id

        # Make data based on existing statics
        if (existing_node_type == "Basin") and (node_type == "LevelBoundary"):
            data = level_boundary.Static(level=[model.basin.state.df.set_index("node_id").at[node_id, "level"]])
        elif (existing_node_type == "ManningResistance") and (node_type == "Outlet"):
            data = outlet.Static(flow_rate=[default_flow_rate])
        else:
            raise ValueError(f"For # {node_id}. Change from {existing_node_type} to {node_type} not implemented.")

        # remove node from all tables
        for attr in type(table).model_fields.keys():
            df = getattr(table, attr).df
            if df is not None:
                if "node_id" in df.columns:
                    getattr(table, attr).df = df[df.node_id != node_id]
                else:
                    getattr(table, attr).df = df[df.index != node_id]

        # remove from used node-ids so we can add it again in the same table
        if node_id in table._parent._used_node_ids:
            table._parent._used_node_ids.node_ids.remove(node_id)

        # add to table
        table = getattr(model, pascal_to_snake_case(node_type))
        table.add(Node(**node_dict), tables=[data])
