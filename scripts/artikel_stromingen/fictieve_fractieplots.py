# %%
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

# Tijdas: 10 dagen, met uurlijkse resolutie en dagnummer op de x-as
day_axis = np.linspace(1, 10, 10 * 24 + 1)
output_dir = Path(r"d:\projecten\D2513.Tauw.Ribasim-Delwaq\03.artikel_stromingen")

end_fractions_case_1 = {
    "Drainage (D)": 0.55,
    "Aanvoer": 0.20,
    "RWZI": 0.00,
    "Maaiveld afvoer (Rsurf)": 0.20,
    "Neerslag (P)": 0.05,
}

end_fractions_case_2 = {name: value * 0.8 for name, value in end_fractions_case_1.items()}
end_fractions_case_2["RWZI"] = 0.2

# Plotvolgorde van onder naar boven
order = [
    "Initeel volume",
    "Drainage (D)",
    "Aanvoer",
    "RWZI",
    "Maaiveld afvoer (Rsurf)",
    "Neerslag (P)",
]

colors = {
    "Initeel volume": "0.65",
    "Drainage (D)": "forestgreen",
    "Aanvoer": "red",
    "RWZI": "purple",
    "Maaiveld afvoer (Rsurf)": "orange",
    "Neerslag (P)": "royalblue",
}

LABEL_FONTSIZE = 14
TICK_FONTSIZE = 12


def make_fraction_plot(
    end_fractions: dict[str, float],
    title: str,
    decay_end_day: float,
):
    # Fractie Initeel volume: natuurlijk ogende exponentiele afname tot decay_end_day,
    # daarna blijft de fractie 0.
    progress = np.clip((day_axis - day_axis.min()) / (decay_end_day - day_axis.min()), 0, 1)
    decay = np.exp(-4 * progress)
    initial_fraction = pd.Series((decay - decay[-1]) / (decay[0] - decay[-1]), index=day_axis)
    ramp = 1 - initial_fraction

    df = pd.DataFrame(index=day_axis)
    df.index.name = "Dag"
    df["Initeel volume"] = initial_fraction

    for name, value in end_fractions.items():
        df[name] = ramp * value

    fig, ax = plt.subplots(figsize=(6, 4))

    ax.stackplot(
        df.index,
        [df[c] for c in order],
        labels=order,
        colors=[colors[c] for c in order],
        linewidth=0,
    )

    # ax.set_title(title)
    ax.set_ylim(0, 1)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["0", "1"])
    ax.set_ylabel("fractie [-]", fontsize=LABEL_FONTSIZE)
    ax.set_xlabel(r"dagen $\rightarrow$", fontsize=LABEL_FONTSIZE)
    ax.set_xlim(1, 10)
    ax.set_xticks([])
    ax.tick_params(axis="x", labelsize=TICK_FONTSIZE)
    ax.tick_params(axis="y", labelsize=TICK_FONTSIZE)
    ax.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    return fig


def export_legend(filename: Path) -> None:
    legend_handles = [Patch(facecolor=colors[label], edgecolor="none", label=label) for label in order]
    legend_fig, legend_ax = plt.subplots(figsize=(2.4, 2.0))
    legend_ax.axis("off")
    legend_ax.legend(handles=legend_handles[::-1], loc="center left", frameon=False)
    legend_fig.savefig(filename, dpi=300, bbox_inches="tight", transparent=True)


output_dir.mkdir(parents=True, exist_ok=True)

fig1 = make_fraction_plot(end_fractions_case_1, "Scenario 1", decay_end_day=3)
fig1.savefig(output_dir / "fictieve_fractieplot_scenario_1.png", dpi=300, bbox_inches="tight")

fig2 = make_fraction_plot(end_fractions_case_2, "Scenario 2", decay_end_day=2.5)
fig2.savefig(output_dir / "fictieve_fractieplot_scenario_2.png", dpi=300, bbox_inches="tight")
export_legend(output_dir / "fictieve_fractieplot_legenda.png")

plt.show()
