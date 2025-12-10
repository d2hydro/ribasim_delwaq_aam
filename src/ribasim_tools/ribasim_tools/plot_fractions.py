import pandas as pd
from ribasim import Model

from ribasim_tools.read_delwaq_fractions import default_tracers, read_fractions


def plot_fraction(
    model: Model,
    node_id: int,
    tracers: list[str] = default_tracers,
) -> None:
    """Plot Delwaq fractions for a specific node from a Ribasim model

    Parameters
    ----------
    model : Model
        ribasim.Model object with Delwaq results loaded
    node_id : int
        node id to plot fractions for
    tracers : list[str], optional
        Substances to plot, by default default_tracers
    """
    fraction_pivot = read_fractions(
        model=model,
        node_id=node_id,
        tracers=tracers,
        validate_fractions=False,
    )
    fraction_pivot.plot.area(stacked=True, title=f"Volume fraction for basin {node_id}", ylabel="fraction")


def plot_fractional_flow(
    model: Model,
    node_id: int,
    link_id: int,
    tracers: list[str] = default_tracers,
    validation_decimal_precision: int = 3,
) -> None:
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
    """
    fraction_pivot = read_fractions(
        model=model,
        node_id=node_id,
        tracers=tracers,
        validate_fractions=False,
    )

    df = pd.read_feather(model.toml_path.parent.joinpath("results", "flow.arrow"))
    df = df[df.link_id == link_id].set_index("time")
    df["flow_rate"]
    fractional_flow_pivot = fraction_pivot.mul(df["flow_rate"].reindex(df["flow_rate"].index), axis=0)

    # Validate default tracers sum to 1
    if not fraction_pivot.sum(axis=1).round(validation_decimal_precision).eq(1).all():
        raise ValueError(
            f"Tracers do not sum to 1 for node {node_id} at decimal precision of {validation_decimal_precision}. Cannot plot fractional flow. Inspect volume fraction for {node_id} first."
        )

    fractional_flow_pivot.plot.area(
        stacked=True, title=f"Fractional flow Link {link_id} (Basin {node_id})", ylabel="Flow rate (m3/s)", grid=True
    )
