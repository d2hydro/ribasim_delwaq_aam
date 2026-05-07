# %%

from datetime import timedelta

import matplotlib.pyplot as plt
import pandas as pd
from ribasim import Model
from ribasim_tools.plot_fractions import _make_up_legend, plot_fraction, plot_fractional_flow

from ribasim_tools import read_flow_rate, read_fractions, settings

# %% [ markdown]

# Parsen en controle van Delwaq resultaten. Continuity check voor alle nodes.
model = Model.read(settings.LHM_BA_RVW_toml_path)
# %% [ markdown]
# Plotten van resultaten
node_id = 1216  # Bakelse Aa
link_id = 1986  # Uitlaat Bakelse Aa
default_tracers = ["LevelBoundary", "Initial", "Drainage", "Precipitation", "SurfaceRunoff"]

user_tracers = (
    ["Initial", "Precipitation"]
    + list(model.basin.concentration.df.substance.unique())
    + list(model.level_boundary.concentration.df.substance.unique())
)

plot_fraction(model, node_id, ["Continuity"])

plot_fraction(model, node_id, default_tracers)

plot_fraction(
    model=model,
    node_id=node_id,
    tracers=user_tracers,
    legend_outside_figure=True,
)

plot_fractional_flow(model, node_id, link_id, tracers=default_tracers)

# %% [markdown]

# old-style gefractioneerde flow
location_id = "ADCP261B"
df = pd.read_csv(settings.source_data_dir.joinpath("afvoermetingen", "OPP_discharge_2020_now.csv"), index_col=0)
df = df[(df["location_id"] == location_id) & (df["flag"] <= 2)][["value"]]
df.rename(columns={"value": "Meting"}, inplace=True)
df.index = pd.to_datetime(df.index)
observations = df.resample("D").mean(numeric_only=True)["Meting"]
ax = plot_fractional_flow(
    model,
    node_id,
    link_id,
    tracers=user_tracers,
    legend_outside_figure=True,
    observations=observations,
    starttime="2023-01-01",
    endtime=model.endtime - timedelta(days=1),
    title=f"Afvoer Bakelse Aa ({location_id})",
    ylabel="Afvoer (m3/s)",
    xlabel="Tijd",
    ymax=11,
)


# %% [markdown]

# new style fractie-plot met metingen
start_time = starttime = "2023-01-01"
endtime = model.endtime - timedelta(days=1)

simulation = read_flow_rate(model=model, link_id=link_id)
observations_selec = observations.reindex(simulation.index)

fraction_pivot = read_fractions(
    model=model,
    node_id=node_id,
    tracers=user_tracers,
)

grouped_fraction_pivot = pd.DataFrame(index=fraction_pivot.index)

groups = {
    "Neerslag": "Precipitation",
    "Maaiveld afvoer": r".*_qrun$",
    "Kanaal van Deurne": "Kanaal_van_Deurne",
    "Defensiekanaal": "Defensiekanaal",
    "Bakelse Aa (drains)": r"^Bakelse_Aa_drn",
    "Oude Aa (drains)": r"^Oude_Aa_drn",
    "Oude Vlier (drains)": r"^Vlier_drn",
    "Kaweise Loop (drains)": r"^Kaw_Loop_drn",
    "Ondiepe waterlopen (riv2)": r".*_riv2$",
    "Bakelse Aa (riv1)": r"^Bakelse_Aa_riv1",
    "Oude Aa (riv1)": r"^Oude_Aa_riv1",
    "Oude Vlier (riv1)": r"^Vlier_riv1",
    "Kaweise Loop (riv1)": r"^Kaw_Loop_riv1",
    "Initieel": "Initial",
}

columns = []
for new_col, pattern in dict(
    reversed(list(groups.items()))
).items():  # in omgekeerde volgorde zetten zodat ze goed worden geplot
    df = fraction_pivot.filter(regex=pattern)
    if any(i in columns for i in df.columns):
        raise ValueError(f"one or more columns {df.columns} for {new_col} is allready summed {columns}")
    columns += df.columns.to_list()
    if df.empty:
        raise ValueError(f"{new_col} doesn't match with any existing fraction on pattern {pattern}")
    grouped_fraction_pivot[new_col] = df.sum(axis=1)

missed_columns = [i for i in fraction_pivot.columns if i not in columns]
if missed_columns:
    raise ValueError(f"Adjust mapping! Original columns missed: {missed_columns}")


color_dict = {
    "Neerslag": "#1f77b4",  # blauw (vast)
    "Maaiveld afvoer": "#ff7f0e",  # oranje
    "Kanaal van Deurne": "#2ca02c",  # groen
    "Defensiekanaal": "#9467bd",  # paars
    "Bakelse Aa (drains)": "#8c564b",  # bruin
    "Oude Aa (drains)": "#e377c2",  # roze
    "Oude Vlier (drains)": "#bcbd22",  # geelgroen
    "Kaweise Loop (drains)": "#17becf",  # cyaan
    "Ondiepe waterlopen (riv2)": "#aec7e8",  # lichtblauw
    "Bakelse Aa (riv1)": "#2ca02c",  # groen
    "Oude Aa (riv1)": "#9467bd",  # paars
    "Oude Vlier (riv1)": "#8c564b",  # bruin
    "Kaweise Loop (riv1)": "#e377c2",  # roze
    "Initieel": "#7f7f7f",  # grijs (vast)
}

pivot_df = grouped_fraction_pivot.loc[slice(starttime, endtime)]


fig, ax = plt.subplots(figsize=(12, 5))
ax.set_ylabel("Afvoer (m3/s)")
ax.set_ylim(0, 10)
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

# Create stacked area plot
ax2 = ax.twinx()
pivot_df.plot.area(
    ax=ax2,
    stacked=True,
    title="Fractionele afvoer Bakelse Aa",
    ylabel="Fractie (-)",
    xlabel="Tijd",
    color=[color_dict[i] for i in pivot_df.columns],
    label=False,
    legend=False,
    alpha=0.7,
)

ax.set_zorder(2)
ax2.set_zorder(1)
ax2.set_ylim(0, 1)
ax.patch.set_visible(False)
_make_up_legend(ax, legend_outside_figure=True, legend_x_anchor=0.82)


# %%
age_df = pd.read_csv(settings.processed_data_dir.joinpath("leeftijd", "age_outlet.csv"), sep=";").replace(
    -999, float("nan")
)[["AgeTR1 outlet", "AgeTR2 outlet"]]
age_df.index = grouped_fraction_pivot.index
age_df.rename(columns={"AgeTR1 outlet": "vanaf 1512", "AgeTR2 outlet": "vanaf 1363"}, inplace=True)

age_df.loc[age_df["vanaf 1363"] > 4000, "vanaf 1363"] = float("nan")
age_df.loc[age_df["vanaf 1512"] > 2000, "vanaf 1512"] = float("nan")

ax = age_df.loc[slice(starttime, endtime)].plot(grid=True, ylabel="leeftijd (dagen)", xlabel="tijd")
ax.set_ylim(0, 4000)


# %%

ax = plot_fraction(
    model=model,
    node_id=node_id,
    tracers=user_tracers,
    legend_outside_figure=True,
    starttime=start_time,
    endtime=endtime,
    add_legend=False,
)
ax2 = ax.twinx()
ax2.set_ylabel("Afvoer (m3/s)")

ax2.plot(
    observations_selec.index,
    observations_selec.values,
    label=observations_selec.name,
    linestyle=":",
    color="red",
    linewidth=1,
)
ax2.plot(simulation.index, simulation.values, color="black", linewidth=1, label="Ribasim")
_make_up_legend(ax, legend_outside_figure=True)
