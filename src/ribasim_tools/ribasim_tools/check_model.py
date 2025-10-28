import pandas as pd
from ribasim import Model


def check_level_boundaries_for_delwaq(model: Model):
    """Check if any LevelBoundary is linked to more than one connector-node (Outlet, Pump, ...)

    For Delwaq every BoundaryNode is to be connected to max one Basin. Therefore every connector-node at the
    model boundary has to have its own boundary node.

    Function will raise a ValueError if such LevelBoundaries exist, including the list of invalid boundary nodes

    Parameters
    ----------
    model : Model
        Ribasim Model
    """

    def _node_has_multiple_links(row: pd.Series) -> bool:
        """Check if a node has multiple links (is linked to multiple other nodes)"""
        node_id = row.name
        return len(model.link.df[(model.link.df.from_node_id == node_id) | (model.link.df.to_node_id == node_id)]) > 1

    df = model.level_boundary.node.df[model.level_boundary.node.df.apply(_node_has_multiple_links, axis=1)]
    if not df.empty:
        raise ValueError(
            f"LevelBoundaries cannot be linked to more than one connector prior to generating a Delwaq schematization. Fix LevelBoundaries: {df.index.to_list()}"
        )
