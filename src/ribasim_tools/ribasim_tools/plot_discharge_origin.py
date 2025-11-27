import matplotlib.pyplot as plt
import numpy as np

def plot_discharge_origin(
    model,
    node_id,
    tracers=[
        "LevelBoundary",
        "FlowBoundary",
        "UserDemand",
        "Initial",
        "Drainage",
        "Precipitation",
        "SurfaceRunoff",
    ],
) -> tuple[plt.Figure, plt.Axes]:
    table = model.basin.concentration_external.df
    table = table[table["node_id"] == node_id]
    table = table[table["substance"].isin(tracers)]
    if len(table) == 0:
        raise ValueError(f"No data found for node {node_id} with tracers {tracers}")

    groups = table.groupby("substance")
    stack = {k: v["concentration"].to_numpy() for (k, v) in groups}

    fig, ax = plt.subplots()
    key = next(iter(groups.groups))
    time = groups.get_group(key)["time"]
    ax.stackplot(
        time,
        stack.values(),
        labels=stack.keys(),
    )
    ax.plot(
        time,
        np.sum(list(stack.values()), axis=0),
        c="black",
        lw=2,
    )
    ax.legend()
    ax.set_title(f"Fraction plot for node {node_id}")
    ax.set_xlabel("Time")
    ax.set_ylabel("Fraction")

    plt.show(fig)
    return fig, ax