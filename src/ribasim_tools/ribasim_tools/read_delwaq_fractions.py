import logging

import pandas as pd
from ribasim import Model
from ribasim_tools.read_ribasim_flow_rate import read_flow_rate

logger = logging.getLogger(__name__)

default_tracers = [
    "LevelBoundary",
    "FlowBoundary",
    "UserDemand",
    "Initial",
    "Drainage",
    "Precipitation",
    "SurfaceRunoff",
]


def read_fractions(
    model: Model,
    node_id: int,
    tracers: list[str] = default_tracers,
    validate_fractions: bool = True,
    validation_decimal_precision: int = 3,
) -> pd.DataFrame:
    """Get Delwaq fractions for a specific node from a Ribasim model

    Parameters
    ----------
    model : Model
        ribasim.Model object with Delwaq results loaded
    node_id : int
        node id to read fractions for
    tracers : list[str], optional
        Substances to return, by default default_tracers
    validate_fractions : bool, optional
        Validate if Continuity and default fractions sum-up to 1, by default True
    validation_decimal_precision : int, optional
        Decimal precision to validate fractions, by default 3

    Returns
    -------
    pd.DataFrame
        Pivoted dataframe with time as index and substances as columns
    """
    fraction_table = model.basin.concentration_external.df
    fraction_table = fraction_table[fraction_table["node_id"] == node_id]
    if len(fraction_table) == 0:
        raise ValueError(f"No data found for node {node_id}")

    # pivot the table to have substances as columns
    fraction_pivot = fraction_table.pivot(index="time", columns="substance", values="concentration").sort_index(axis=1)
    if validate_fractions:
        # Validate continuity
        if not fraction_pivot["Continuity"].round(validation_decimal_precision).eq(1).all():
            raise ValueError(
                f"Continuity check failed for node {node_id}. Does not round to 1 decimal precision of {validation_decimal_precision}"
            )
        # Validate default tracers sum to 1
        if not fraction_pivot[default_tracers].sum(axis=1).round(validation_decimal_precision).eq(1).all():
            raise ValueError(
                f"Default tracers ({default_tracers}) do not sum to 1 for node {node_id} at decimal precision of {validation_decimal_precision}"
            )

    # return only requested tracers
    missing_tracers = [tracer for tracer in tracers if tracer not in fraction_pivot.columns]
    if missing_tracers:
        raise ValueError(f"Requested tracers {missing_tracers} not found for node {node_id}")

    return fraction_pivot[tracers]


def read_fractional_flow(
    model: Model,
    node_id: int,
    link_id: int,
    tracers: list[str] = default_tracers,
    validate_fractions: bool = True,
    validation_decimal_precision: int = 3,
) -> pd.DataFrame:
    """Plot Delwaq fractional flow for a specific link from a Ribasim model

    Parameters
    ----------
    model : Model
        ribasim.Model object with Delwaq results loaded
    node_id : int
        node id to read fractions for
    link_id : int
        link id to read flow for
    tracers : list[str], optional
        Substances to plot, by default default_tracers
    validate_fractions : bool, optional
        Validate if Continuity and default fractions sum-up to 1, by default True
    validation_decimal_precision : int, optional
        Decimal precision to validate fractions, by default 3
    """
    # Read fractions without validation
    fraction_pivot = read_fractions(
        model=model,
        node_id=node_id,
        tracers=tracers,
        validate_fractions=validate_fractions,
        validation_decimal_precision=validation_decimal_precision,
    )

    # Validate tracers fractions sum to 1
    if not fraction_pivot.sum(axis=1).round(validation_decimal_precision).eq(1).all():
        raise ValueError(
            f"Tracers do not sum to 1 for node {node_id} at decimal precision of {validation_decimal_precision}. Cannot plot fractional flow. Inspect volume fraction for {node_id} first."
        )

    # Get flow rates for the link and multiply with fractions
    flow_rate = read_flow_rate(model=model, link_id=link_id)
    fractional_flow_pivot = fraction_pivot.mul(flow_rate, axis=0)

    return fractional_flow_pivot


def check_nodes_continuity(
    model: Model,
    validation_decimal_precision: int = 3,
) -> list[int]:
    """Validate continuity for all nodes in the model at the last timestep

    Parameters
    ----------
    model : Model
        ribasim.Model object with Delwaq results loaded
    validation_decimal_precision : int, optional
        Decimal precision to validate continuity sum to 1, by default 3

    Returns
    -------
    list[int]
        node_ids that fail the continuity check
    """
    fraction_table = model.basin.concentration_external.df
    fraction_table = fraction_table[
        (fraction_table.time == fraction_table.time.max()) & (fraction_table.substance == "Continuity")
    ]

    node_ids = fraction_table[~fraction_table["concentration"].round(validation_decimal_precision).eq(1)][
        "node_id"
    ].tolist()

    if node_ids:
        logger.error(
            f"Continuity check failed for nodes {node_ids}. Do not round to decimal precision {validation_decimal_precision} at last timestep"
        )
    return node_ids
