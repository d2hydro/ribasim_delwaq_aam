# %%
from datetime import date, datetime
from itertools import cycle
from re import Pattern
from typing import Union

import matplotlib.pyplot as plt
import pandas as pd
from ribasim import Model

from ribasim_tools.read_delwaq_fractions import default_tracers, read_fractions
from ribasim_tools.read_ribasim_flow_rate import read_flow_rate

USER_COLORS = {"Initial": "#808080"}


DateLike = Union[str, date, datetime]


def _remove_area_edges(ax) -> None:
    """Remove outlines from filled area collections."""
    for collection in ax.collections:
        collection.set_linewidth(0)
        collection.set_edgecolor("none")


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
        else:
            colors.append(next(color_iter))  # cycle through Pandas default color cycle
    return colors


def _make_up_legend(ax, legend_outside_figure: bool, legend_x_anchor=0.85) -> None:
    """Maak 1 gecombineerde legenda voor alle assen."""
    handles, labels = [], []

    for a in ax.figure.axes:
        h, l = a.get_legend_handles_labels()
        handles.extend(h)
        labels.extend(l)

    # dubbele labels verwijderen, volgorde behouden
    seen = set()
    uniq_handles = []
    uniq_labels = []
    for h, l in zip(handles, labels):
        if l and l not in seen:
            seen.add(l)
            uniq_handles.append(h)
            uniq_labels.append(l)

    # bestaande legends weghalen
    for a in ax.figure.axes:
        leg = a.get_legend()
        if leg is not None:
            leg.remove()

    fig = ax.figure

    if legend_outside_figure:
        fig.subplots_adjust(right=0.78)
        fig.legend(
            uniq_handles[::-1],
            uniq_labels[::-1],
            loc="center left",
            bbox_to_anchor=(legend_x_anchor, 0.5),
            frameon=False,
        )
    else:
        ax.legend(
            uniq_handles[::-1],
            uniq_labels[::-1],
            frameon=False,
            loc="lower left",
        )


def _group_fractions(
    fraction_pivot: pd.DataFrame,
    groups: dict[str, str | Pattern[str]],
) -> pd.DataFrame:
    """Aggregate fraction columns based on regex mappings."""
    grouped_fraction_pivot = pd.DataFrame(index=fraction_pivot.index)
    matched_columns: list[str] = []

    # Reverse plotting order so the first user-facing group is drawn on top.
    for new_col, pattern in reversed(list(groups.items())):
        df = fraction_pivot.filter(regex=pattern)
        duplicate_columns = [col for col in df.columns if col in matched_columns]
        if duplicate_columns:
            raise ValueError(f"One or more columns {duplicate_columns} for {new_col} are already grouped")
        if df.empty:
            raise ValueError(f"{new_col} doesn't match any existing fraction on pattern {pattern}")

        matched_columns.extend(df.columns.to_list())
        grouped_fraction_pivot[new_col] = df.sum(axis=1)

    missed_columns = [col for col in fraction_pivot.columns if col not in matched_columns]
    if missed_columns:
        raise ValueError(f"Adjust mapping! Original columns missed: {missed_columns}")

    return grouped_fraction_pivot


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
    ymax: float | None = None,
    add_legend: bool = True,
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
        linewidth=0,
        label=False,
        legend=False,
    )
    _remove_area_edges(ax)
    if ymax is not None:
        ax.set_ylim(top=ymax)

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
        if ymax is not None:
            ymax = max(observations.max(), ymax)
        else:
            ymax = observations.max()

        ax.set_ylim(top=ymax)

    if add_legend:
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
    add_legend: bool = True,
    groups: dict[str, str | Pattern[str]] | None = None,
    color_dict: dict[str, str] | None = None,
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
    if groups is not None:
        fraction_pivot = _group_fractions(fraction_pivot=fraction_pivot, groups=groups)
    else:
        fraction_pivot = _order_fractions(pivot_df=fraction_pivot)

    if title is None:
        title = f"Volume fraction for basin {node_id}"
    return _plot_figure(
        pivot_df=fraction_pivot,
        title=title,
        ylabel=ylabel,
        xlabel=xlabel,
        user_colors=color_dict or user_colors,
        legend_outside_figure=legend_outside_figure,
        starttime=starttime,
        endtime=endtime,
        add_legend=add_legend,
    )


def plot_fractional_flow(
    model: Model,
    node_id: int,
    link_id: int,
    tracers: list[str] = default_tracers,
    validate_fractions: bool = True,
    validation_decimal_precision: int = 3,
    legend_outside_figure: bool = False,
    observations: pd.Series | None = None,
    starttime: DateLike | None = None,
    endtime: DateLike | None = None,
    title: str | None = None,
    ylabel: str = "Flow rate (m3/s)",
    xlabel: str = "Time",
    ymax: float | None = None,
    groups: dict[str, str | Pattern[str]] | None = None,
    color_dict: dict[str, str] | None = None,
):
    """Plot flow lines with stacked fractions on a secondary axis.

    This variant supports grouping original fraction columns into user-defined
    categories and plotting them with explicit colors.
    """
    simulation = read_flow_rate(model=model, link_id=link_id)
    fraction_pivot = read_fractions(
        model=model,
        node_id=node_id,
        tracers=tracers,
        validate_fractions=validate_fractions,
        validation_decimal_precision=validation_decimal_precision,
    )

    if groups is not None:
        pivot_df = _group_fractions(fraction_pivot=fraction_pivot, groups=groups)
    else:
        pivot_df = _order_fractions(pivot_df=fraction_pivot)

    pivot_df = pivot_df.loc[slice(starttime, endtime)]
    simulation = simulation.loc[slice(starttime, endtime)]
    observations_selec = observations.reindex(simulation.index) if observations is not None else None

    if title is None:
        title = f"Fractional flow Link {link_id} (Basin {node_id})"

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.set_ylabel(ylabel)
    ax.set_xlabel(xlabel)
    if ymax is not None:
        ax.set_ylim(0, ymax)

    if observations_selec is not None:
        ax.plot(
            observations_selec.index,
            observations_selec.values,
            label=observations_selec.name,
            linestyle=":",
            color="red",
            linewidth=2,
            zorder=10,
        )

    ax.plot(
        simulation.index,
        simulation.values,
        color="black",
        linewidth=2,
        label="Ribasim",
        zorder=10,
    )
    ax.grid(True, zorder=4)

    ax2 = ax.twinx()
    plot_kwargs = {
        "ax": ax2,
        "stacked": True,
        "title": title,
        "ylabel": "Fractie (-)",
        "xlabel": xlabel,
        "linewidth": 0,
        "label": False,
        "legend": False,
        "alpha": 0.7,
    }
    if color_dict is not None:
        plot_kwargs["color"] = [color_dict[col] for col in pivot_df.columns]
    pivot_df.plot.area(**plot_kwargs)
    _remove_area_edges(ax2)

    ax.set_zorder(2)
    ax2.set_zorder(1)
    ax2.set_ylim(0, 1)
    ax.patch.set_visible(False)
    _make_up_legend(ax, legend_outside_figure=legend_outside_figure, legend_x_anchor=0.82)

    return ax
