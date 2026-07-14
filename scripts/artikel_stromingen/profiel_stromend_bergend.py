# %%
from pathlib import Path

import matplotlib.pyplot as plt
from ribasim import Model

from ribasim_tools import settings

OUTPUT_PATH = Path(__file__).with_name("profiel_stromend_bergend.png")
PROFILE_SPECS = {
    1592: {"label": "stromend", "color": "#0077b6"},
    5042: {"label": "bergend", "color": "#d95f02"},
}


def main() -> None:
    model = Model.read(settings.LHM_BA_RVW_toml_path)
    profile_df = model.basin.profile.df.reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(4, 5))

    for node_id, spec in PROFILE_SPECS.items():
        basin_profile = (
            profile_df.loc[profile_df["node_id"] == node_id, ["area", "level"]]
            .sort_values("level")
            .reset_index(drop=True)
        )
        if basin_profile.empty:
            raise ValueError(f"Geen basin.profile gevonden voor node_id {node_id}.")
        basin_profile["area_1000_m2"] = basin_profile["area"] / 1000.0

        ax.plot(
            basin_profile["level"],
            basin_profile["area_1000_m2"],
            label=spec["label"],
            color=spec["color"],
            linewidth=2.8,
        )
        ax.fill_between(
            basin_profile["level"],
            0,
            basin_profile["area_1000_m2"],
            color=spec["color"],
            alpha=0.12,
        )
        ax.scatter(
            basin_profile["level"],
            basin_profile["area_1000_m2"],
            color=spec["color"],
            s=16,
            alpha=0.75,
        )

    # ax.set_title("Basinprofiel stromend en bergend", fontsize=14, weight="bold")
    ax.set_xlabel("Hoogte [m NAP]")
    ax.set_ylabel("Oppervlak [1000 m2]")
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.grid(True, color="#d9d9d9", linewidth=0.8, alpha=0.8)
    ax.legend(frameon=False, loc="lower right")
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUTPUT_PATH, dpi=300, bbox_inches="tight")
    plt.show()


if __name__ == "__main__":
    main()
