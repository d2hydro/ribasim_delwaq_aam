# %%
from itertools import cycle

import matplotlib.pyplot as plt
import pandas as pd
from ribasim import Model

from ribasim_tools.read_delwaq_fractions import default_tracers, read_fractional_flow, read_fractions

USER_COLORS = {"Initial": "#808080"}


def _order_fractions(pivot_df: pd.DataFrame) -> pd.DataFrame:
    """Order Pivot DataFrame for smooth plotting.

    Initial will be the first column so it won't be visually overestimated in a stack.
    The rest we add rest alphabetically so the color scheme will be as stable as possible

    """
    cols = sorted([i for i in pivot_df.columns if i != "Initial"])
    if "Initial" in pivot_df.columns:
        cols = ["Initial"] + cols

    return pivot_df[cols]


def _get_colors(columns: list[str], user_colors: dict) -> list[str]:
    """Get colors for plotting based on tracer names."""
    # Define Pandas default color cycle
    prop_cycle = plt.rcParams["axes.prop_cycle"]
    color_iter = cycle(prop_cycle.by_key()["color"])

    # Populate colors list, initial will be grey, the rest from the color cycle
    colors: list[str] = []
    for col in columns:
        if col in user_colors.keys():
            colors.append(user_colors[col])  # specify user color
        colors.append(next(color_iter))  # cycle through Pandas default color cycle
    return colors


def _plot_figure(
    pivot_df: pd.DataFrame,
    title: str,
    ylabel: str,
    user_colors: dict[str, str],
    legend_outside_figure: bool = False,
) -> None:
    """Reusable plotting function for fractional flow plots."""
    # Create stacked area plot
    ax = pivot_df.plot.area(
        stacked=True,
        title=title,
        ylabel=ylabel,
        grid=True,
        color=_get_colors(pivot_df.columns, user_colors=user_colors),
        label=False,
    )
    if legend_outside_figure:
        ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), borderaxespad=0.0, frameon=False)


def plot_fraction(
    model: Model,
    node_id: int,
    tracers: list[str] = default_tracers,
    validate_fractions: bool = True,
    validation_decimal_precision: int = 3,
    user_colors: dict[str, str] = USER_COLORS,
    legend_outside_figure: bool = False,
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
    validate_fractions : bool, optional
        Validate if Continuity and default fractions sum-up to 1, by default True
    validation_decimal_precision : int, optional
        Decimal precision to validate fractions, by default 3
    user_colors : dict[str, str], optional
        Colors to use for specific tracers, by default {"Initial": "#808080"}
    legend_outside_figure : bool, optional
        Place legend outside of figure, by default False
    """
    fraction_pivot = read_fractions(
        model=model,
        node_id=node_id,
        tracers=tracers,
        validate_fractions=validate_fractions,
        validation_decimal_precision=validation_decimal_precision,
    )
    fraction_pivot = _order_fractions(pivot_df=fraction_pivot)
    _plot_figure(
        pivot_df=fraction_pivot,
        title=f"Volume fraction for basin {node_id}",
        ylabel="fraction",
        user_colors=user_colors,
        legend_outside_figure=legend_outside_figure,
    )


def plot_fractional_flow(
    model: Model,
    node_id: int,
    link_id: int,
    tracers: list[str] = default_tracers,
    validate_fractions: bool = True,
    validation_decimal_precision: int = 3,
    user_colors: dict[str, str] = USER_COLORS,
    legend_outside_figure: bool = False,
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
    validate_fractions : bool, optional
        Validate if Continuity and default fractions sum-up to 1, by default True
    validation_decimal_precision : int, optional
        Decimal precision to validate fractions, by default 3
    user_colors : dict[str, str], optional
        Colors to use for specific tracers, by default {"Initial": "#808080"}
    legend_outside_figure : bool, optional
        Place legend outside of figure, by default False
    """
    # Read fractional_flow
    fractional_flow_pivot = read_fractional_flow(
        model=model,
        node_id=node_id,
        link_id=link_id,
        tracers=tracers,
        validate_fractions=validate_fractions,
        validation_decimal_precision=validation_decimal_precision,
    )

    fractional_flow_pivot = _order_fractions(pivot_df=fractional_flow_pivot)

    # Create stacked area plot
    _plot_figure(
        pivot_df=fractional_flow_pivot,
        title=f"Fractional flow Link {link_id} (Basin {node_id})",
        ylabel="Flow rate (m3/s)",
        user_colors=user_colors,
        legend_outside_figure=legend_outside_figure,
    )
