# %%
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
    convert_node_types: dict[int, str],
    default_flow_rate: float = 25,
    inplace: bool = False,
) -> Model:
    """Clip a model by a Polygon

    From the input `model` all nodes outside the polygon are removed. This includes all sub-tables (e.g. static, time, area, ..).
    All links connected to these nodes are removed as well.

    User can specify extra nodes outside the polygon-area to keep in keep_node_ids. Or drop nodes inside the polygon with drop_node_ids.

    The function will list all links crossing the polygon boundary before removal. By this the user can specify node conversions in `convert_node_types`.
    Typical node conversions at the boundary of the clipped model are:
     - Basin -> LevelBoundary: for the clipped model adjacent Basins act as LevelBoundaries. The clip-function automatically takes the original `Basin.state` as  LevelBoundary.level.
     - ManningResistance -> Outlet: a manning resistance cannot connect a Basin to a LevelBoundary. So, when a user starts to convert Basin -> LevelBoundary a ManningResistance -> Outlet conversion may be needed as well.

    Parameters
    ----------
        model : Model
            Ribasim Model to be clipped
        polygon : Polygon
            Polygon to clip model by
        keep_node_ids : list[int]
            Extra nodes to keep (outside polygon)
        drop_node_ids : list[int]
            Extra nodes to drop (inside polygon)
        convert_node_types : dict[int, str]
            Nodes to convert to another Ribasim.nodes type
        default_flow_rate : float, optional
            Default flow_rate for Outlet in convert_node_types. Defaults to 25.
        inplace : bool, optional
            Option for inplace drop. If set `False` a model copy will be made. By default False

    Raises
    ------
        NotImplementedError: When `convert_node_types` a type-conversion that is not yet implemented

    Returns
    -------
        Model: clipped model
    """
    # create a copy of model
    if inplace:
        clipped_model = model
    else:
        clipped_model = model.model_copy()

    # first get all nodes within polygon or keep_ids and reduce by drop_node_ids
    node_df = clipped_model.node_table().df
    node_ids = keep_node_ids + node_df[node_df.within(polygon)].index.to_list()

    # convert to drop node ids
    drop_node_ids += node_df[~node_df.index.isin(node_ids)].index.to_list()
    drop_nodes(model=clipped_model, drop_node_ids=drop_node_ids, inplace=True)

    # get links trough polygon boundary
    links = clipped_model.link.df[clipped_model.link.df.intersects(polygon.exterior)]
    print(f"Links trough polygon-boundary: {links.index.to_list()}")

    node_table_df = clipped_model.node.df

    for node_id, node_type in convert_node_types.items():
        existing_node_type = node_table_df.at[node_id, "node_type"]

        # save node-attributes, so we can add it later. Pop node-type as we'll change that
        node_dict = model.node.df.loc[node_id].to_dict()
        node_dict.pop("node_type")
        node_dict["node_id"] = node_id

        # Make data based on existing statics
        if (existing_node_type == "Basin") and (node_type == "LevelBoundary"):
            data = level_boundary.Static(level=[clipped_model.basin.state.df.set_index("node_id").at[node_id, "level"]])
        elif (existing_node_type == "ManningResistance") and (node_type == "Outlet"):
            data = outlet.Static(flow_rate=[default_flow_rate])
        else:
            raise NotImplementedError(
                f"For # {node_id}. Change from {existing_node_type} to {node_type} not implemented."
            )

        # remove node from all tables
        model._remove_node_id(node_id)

        # add to table
        table = getattr(clipped_model, pascal_to_snake_case(node_type))
        table.add(Node(**node_dict), tables=[data])

    # final (and dirty) cleanup of control table
    model.discrete_control.variable.df = model.discrete_control.variable.df[
        model.discrete_control.variable.df.listen_node_id.isin(model.node.df.index.values)
    ]

    if inplace:
        return None
    else:
        return clipped_model
