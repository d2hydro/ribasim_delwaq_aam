from ribasim import Model


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
        result_model = model
    else:
        result_model = model.model_copy()

    assert result_model.node.df is not None

    result_model.node.df = result_model.node.df[~result_model.node.df.index.isin(drop_node_ids)]

    for sub in result_model._nodes():
        # Remove from data tables
        for table in sub._tables():
            if table.df is not None:
                if "node_id" in table.df.columns:
                    table.df = table.df[~table.df["node_id"].isin(drop_node_ids)]
                if table.df.empty:
                    table.df = None

    # make accessable for further processing
    for node_id in drop_node_ids:
        if node_id in result_model.node._used_node_ids:
            result_model.node._used_node_ids.node_ids.remove(node_id)

    if drop_connected_links:
        result_model.link.df = result_model.link.df[
            ~(
                result_model.link.df.from_node_id.isin(drop_node_ids)
                | result_model.link.df.to_node_id.isin(drop_node_ids)
            )
        ]

    if inplace:
        return None
    else:
        return result_model
