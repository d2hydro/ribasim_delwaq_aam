# %%
import pandas as pd
from ribasim import Model
from ribasim_tools import settings

TOML_FILE = settings.processed_data_dir.joinpath("hsa_model", "debug", "1a_sanitize_model")
SPLITSING_NODE_IDS = [40001874, 40001462, 40001873]

model = Model.read(TOML_FILE)

df = model.tabulated_rating_curve.time.df[
    (
        model.tabulated_rating_curve.time.df.node_id.isin(SPLITSING_NODE_IDS)
        & model.tabulated_rating_curve.time.df.meta_season.isin(["Winter"])
    )
]


df[["node_id", "flow_rate", "level"]].pivot_table(
    index="flow_rate", columns="node_id", values="level"
).ffill().bfill().plot(grid=True, ylabel="level")

# %%
BASIN = 10000449
TABULATED_RATING_CURVE = 10000894


def calc_volume(row, df):
    row_idx = row.name
    if row_idx == 0:
        return 0
    else:
        previous_row = df.loc[row_idx - 1]
        dh = row.level - previous_row.level
        da = row.area - previous_row.area
        dv = previous_row.area * dh + da * dh / 2
        return dv


time = model.tabulated_rating_curve.time.df.time.min()
Qh = (
    model.tabulated_rating_curve.time.df[
        (
            model.tabulated_rating_curve.time.df.node_id.isin([TABULATED_RATING_CURVE])
            & model.tabulated_rating_curve.time.df.meta_season.isin(["Winter"])
            & model.tabulated_rating_curve.time.df.time.isin([time])
        )
    ]
    .set_index("level")["flow_rate"]
    .sort_values()
)

profile = (
    model.basin.profile.df[(model.basin.profile.df.node_id.isin([BASIN]))][["level", "area"]]
    .sort_values(by="level")
    .reset_index()
)
profile["volume"] = profile.apply(calc_volume, args=(profile,), axis=1).cumsum()

Vh = profile.set_index("level")["volume"]


# linker y-as: flow_rate
ax = Qh.plot(label="Flow rate", grid=True)

ax.set_xlabel("Level")
ax.set_ylabel("Flow rate")

# rechter y-as: volume
Vh.plot(ax=ax, secondary_y=True, label="Volume")

ax.right_ax.set_ylabel("Volume")

# ---- legenda combineren ----
lines_left, labels_left = ax.get_legend_handles_labels()
lines_right, labels_right = ax.right_ax.get_legend_handles_labels()

ax.legend(lines_left + lines_right, labels_left + labels_right, loc="best")

QVT = pd.concat([Vh.rename("volume"), Qh.rename("flow_rate")], axis=1).sort_index().dropna()
QVT["depletion_time"] = QVT.volume / QVT.flow_rate

# %%
