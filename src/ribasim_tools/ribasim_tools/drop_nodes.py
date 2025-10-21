from ribasim import Model

from ribasim_tools.case_conversions import pascal_to_snake_case


def drop_nodes(
    model: Model, drop_node_ids: list[int], drop_connected_links: bool = True, inplace: bool = False
) -> Model | None:
    """Drop nodes and optionally connected links

    All nodes in `drop_node_ids` are dropped. If `drop_connected_links` is set `True` links connected to a node in `drop_node_ids` are removed as well.

    If `inplace` is set `True` the input model is modified. If not, the function will return a model-copy.

    Parameters
    ----------
    model : Model
        Ribasim Model to drop nodes from
    drop_node_ids : list[int]
        List of node_dis to drop
    drop_connected_links : bool, optional
        Option to drop links connected to dropped nodes, by default True
    inplace : bool, optional
        Option for inplace drop. If set `False` a model copy will be made. By default False

    Returns
    -------
    Model | None
        Modified model or None depending on inplace setting
    """
    if inplace:
        result_model = model.model_copy()
    else:
        result_model = model
    node_df = result_model.node_table().df
    for node_type, node_type_df in node_df.loc[drop_node_ids].groupby("node_type"):
        drop_node_ids_from_tables = node_type_df.index
        # read table
        table = getattr(result_model, pascal_to_snake_case(node_type))

        # # remove node from all tables
        for attr in type(table).model_fields.keys():
            table_attr = getattr(table, attr)
            df = table_attr.df
            if df is not None:
                if "node_id" in df.columns:
                    table_attr.df = df[~df.node_id.isin(drop_node_ids_from_tables)]
                else:
                    table_attr.df = df[~df.index.isin(drop_node_ids_from_tables)]

    if drop_connected_links:
        result_model.link.df = result_model.link.df[
            ~(
                result_model.link.df.from_node_id.isin(drop_node_ids)
                | result_model.link.df.to_node_id.isin(drop_node_ids)
            )
        ]

    if not inplace:
        return result_model
    else:
        return None
