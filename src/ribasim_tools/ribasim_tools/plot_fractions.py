# %%
from datetime import date, datetime
from itertools import cycle
from typing import Union

import matplotlib.pyplot as plt
import pandas as pd
from ribasim import Model

from ribasim_tools.read_delwaq_fractions import default_tracers, read_fractional_flow, read_fractions

USER_COLORS = {"Initial": "#808080"}


DateLike = Union[str, date, datetime]


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


def _make_up_legend(ax, legend_outside_figure) -> None:
    """Make up figure legend."""
    # we reverse handles and labels so they match stack-order (bottom in stack is bottom in legend)
    handles, labels = ax.get_legend_handles_labels()

    # optional placing outside figure (so legend won't be placed on top of stack)
    if legend_outside_figure:
        ax.legend(
            handles[::-1], labels[::-1], loc="center left", bbox_to_anchor=(1.02, 0.5), borderaxespad=0.0, frameon=False
        )
    else:
        ax.legend(handles[::-1], labels[::-1])


def _plot_figure(
    pivot_df: pd.DataFrame,
    title: str,
    ylabel: str,
    xlabel: str,
    user_colors: dict[str, str],
    legend_outside_figure: bool = False,
    observations: pd.Series | None = None,
    starttime: DateLike | None = None,
    endtime: DateLike | None = None,
) -> None:
    """Reusable plotting function for fractional flow plots."""
    # Clip time-series if starttime/endtime provided
    pivot_df = pivot_df.loc[slice(starttime, endtime)]

    # Create stacked area plot
    ax = pivot_df.plot.area(
        stacked=True,
        title=title,
        ylabel=ylabel,
        xlabel=xlabel,
        grid=True,
        color=_get_colors(pivot_df.columns, user_colors=user_colors),
        label=False,
    )
    if observations is not None:
        observations = observations.loc[pivot_df.index.min() : pivot_df.index.max()]  # clip
        ax.plot(
            observations.index,
            observations.to_numpy(),
            linestyle=":",
            color="black",
            linewidth=1,
            label=observations.name,
        )
        ax.set_ylim(top=observations.max())

    _make_up_legend(ax, legend_outside_figure)

    return ax


def plot_fraction(
    model: Model,
    node_id: int,
    tracers: list[str] = default_tracers,
    validate_fractions: bool = True,
    validation_decimal_precision: int = 3,
    user_colors: dict[str, str] = USER_COLORS,
    legend_outside_figure: bool = False,
    starttime: DateLike | None = None,
    endtime: DateLike | None = None,
    title: str | None = None,
    ylabel: str = "Fraction",
    xlabel: str = "Time",
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
    starttime : DateLike | None, optional
        Start time for plotting, by default None
    endtime : DateLike | None, optional
        End time for plotting, by default None
    title: str | None, optional
        Title for the plot, by default None. If None, a default title will be used generated based on node_id
    ylabel: str, optional
        Y-axis label, by default "Flow rate (m3/s)"
    xlabel: str, optional
        X-axis label, by default "Time"
    """
    fraction_pivot = read_fractions(
        model=model,
        node_id=node_id,
        tracers=tracers,
        validate_fractions=validate_fractions,
        validation_decimal_precision=validation_decimal_precision,
    )
    fraction_pivot = _order_fractions(pivot_df=fraction_pivot)

    if title is None:
        title = f"Volume fraction for basin {node_id}"
    return _plot_figure(
        pivot_df=fraction_pivot,
        title=title,
        ylabel=ylabel,
        xlabel=xlabel,
        user_colors=user_colors,
        legend_outside_figure=legend_outside_figure,
        starttime=starttime,
        endtime=endtime,
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
    observations: pd.DataFrame | None = None,
    starttime: DateLike | None = None,
    endtime: DateLike | None = None,
    title: str | None = None,
    ylabel: str = "Flow rate (m3/s)",
    xlabel: str = "Time",
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
    observations : pd.DataFrame | None, optional
        DataFrame with observations to plot as overlay, by default None
    starttime : DateLike | None, optional
        Start time for plotting, by default None
    endtime : DateLike | None, optional
        End time for plotting, by default None
    title: str | None, optional
        Title for the plot, by default None. If None, a default title will be used generated based on link_id and node_id
    ylabel: str, optional
        Y-axis label, by default "Flow rate (m3/s)"
    xlabel: str, optional
        X-axis label, by default "Time"
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

    # customize title
    if title is None:
        title = f"Fractional flow Link {link_id} (Basin {node_id})"

    # Create stacked area plot
    return _plot_figure(
        pivot_df=fractional_flow_pivot,
        title=title,
        ylabel=ylabel,
        xlabel=xlabel,
        user_colors=user_colors,
        legend_outside_figure=legend_outside_figure,
        observations=observations,
        starttime=starttime,
        endtime=endtime,
    )
