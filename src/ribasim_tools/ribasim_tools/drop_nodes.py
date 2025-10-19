from ribasim import Model

from ribasim_tools.case_conversions import pascal_to_snake_case


def drop_nodes(model: Model, drop_node_ids: list[int], drop_connected_links: bool = True):
    """Drop nodes and optionally connected links

    Args:
        model (Model): ribasim.Model
        drop_node_ids (list[int]): list of node ids
        drop_connected_links: option to drop connected links too. Default = True
    """
    node_df = model.node_table().df
    for node_type, node_type_df in node_df.loc[drop_node_ids].groupby("node_type"):
        drop_node_ids_from_tables = node_type_df.index
        # read table
        table = getattr(model, pascal_to_snake_case(node_type))

        # # remove node from all tables
        for attr in type(table).model_fields.keys():
            df = getattr(table, attr).df
            if df is not None:
                if "node_id" in df.columns:
                    getattr(table, attr).df = df[~df.node_id.isin(drop_node_ids_from_tables)]
                else:
                    getattr(table, attr).df = df[~df.index.isin(drop_node_ids_from_tables)]

    if drop_connected_links:
        model.link.df = model.link.df[
            ~(model.link.df.from_node_id.isin(drop_node_ids) | model.link.df.to_node_id.isin(drop_node_ids))
        ]
