from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from ribasim import Model

from ribasim_tools import read_flow_rate

OUTPUT_PATH = Path(__file__).with_name("afvoer_link_1986_2015.png")
LINK_ID = 1986
STARTTIME = "2015-01-01"
ENDTIME = "2016-01-01"

MODEL_SPECS = [
    {
        "toml_path": Path(
            r"d:\projecten\D2513.Tauw.Ribasim-Delwaq\01.bewerkte_gegevens\lhm_aam\LHM_BA_RVW\LHM_BA.toml"
        ),
        "label": "LHM oppervlaktewater",
        "color": "#1f77b4",
    },
    {
        "toml_path": Path(
            r"d:\projecten\D2513.Tauw.Ribasim-Delwaq\01.bewerkte_gegevens\lhm_aam\LHM_BA_RVW_p90_case\LHM_BA.toml"
        ),
        "label": "10-90% oppervlaktewater",
        "color": "#d62728",
    },
    {
        "toml_path": Path(
            r"d:\projecten\D2513.Tauw.Ribasim-Delwaq\01.bewerkte_gegevens\lhm_aam\LHM_BA_RVW_p05_case\LHM_BA.toml"
        ),
        "label": "5% oppervlaktewater",
        "color": "#2ca02c",
    },
]


def main() -> None:
    fig, ax = plt.subplots()

    for spec in MODEL_SPECS:
        model = Model.read(spec["toml_path"])
        flow_rate = read_flow_rate(model=model, link_id=LINK_ID, starttime=STARTTIME, endtime=ENDTIME)
        if flow_rate.empty:
            raise ValueError(f"Geen debiet gevonden voor link {LINK_ID} in {spec['toml_path']}.")

        ax.plot(
            flow_rate.index,
            flow_rate.values,
            label=spec["label"],
            color=spec["color"],
            linewidth=2,
        )

    ax.set_title(f"Afvoer op link {LINK_ID} in 2015")
    ax.set_xlabel("Time")
    ax.set_ylabel("Debiet [m3/s]")
    ax.grid(True, color="#d9d9d9", linewidth=0.8, alpha=0.8)
    ax.legend(frameon=False, loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlim(pd.Timestamp(STARTTIME), pd.Timestamp(ENDTIME))
    ax.margins(x=0)

    locator = mdates.MonthLocator()
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    fig.tight_layout()
    fig.savefig(OUTPUT_PATH, dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
