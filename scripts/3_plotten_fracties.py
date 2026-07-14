# %%

from datetime import timedelta

import pandas as pd
from ribasim import Model
from ribasim_tools.plot_fractions import plot_fraction, plot_fractional_flow

from ribasim_tools import settings

# %% [markdown]

### Inlezen Delwaq resultaten
#
# Inlezen van het weggeschreven Ribasim-model met de geparste Delwaq-fracties.
model = Model.read(settings.LHM_WAM_RVW_toml_path)

# %% [markdown]

### Plotten van fracties
#
# Eerste controleplots voor continuiteit, default tracers en alle user-defined tracers.
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

# %% [markdown]

### Groeperen van tracers
#
# Groeperen van individuele tracers naar leesbare categorieen en vaste kleuren.
groups = {
    "Neerslag": "Precipitation",  # Precipitation wordt Neerslag
    "Maaiveld afvoer": r".*_qrun$",  # alles met qrun wordt Maaiveld afvoer
    "Kanaal van Deurne": "Kanaal_van_Deurne",
    "Defensiekanaal": "Defensiekanaal",
    "Bakelse Aa (drains)": r"^Bakelse_Aa_drn",  # alle drn systemen van Bakelse Aa
    "Oude Aa (drains)": r"^Oude_Aa_drn",  # alle drn systemen van Oude Aa
    "Oude Vlier (drains)": r"^Vlier_drn",  # alle drn systemen van Oude Vlier
    "Kaweise Loop (drains)": r"^Kaw_Loop_drn",  # alle drn systemen van Kaweise Loop
    "Ondiepe waterlopen (riv2)": r".*_riv2$",  # álle ondiepe waterlopen
    "Bakelse Aa (riv1)": r"^Bakelse_Aa_riv1",  # riv1 van Bakelse Aa
    "Oude Aa (riv1)": r"^Oude_Aa_riv1",  # riv1 van Oude Aa
    "Oude Vlier (riv1)": r"^Vlier_riv1",  # riv1 van Oude Vlier
    "Kaweise Loop (riv1)": r"^Kaw_Loop_riv1",  # riv 1 van Oude Vlier
    "Initieel": "Initial",  # Initial wordt Initieel, want dat is Nederlands
}

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

plot_fraction(
    model=model,
    node_id=node_id,
    tracers=user_tracers,
    legend_outside_figure=True,
    groups=groups,
    color_dict=color_dict,
)
# %% [markdown]

### Gefractioneerde afvoer
#
# Vergelijking van de gesimuleerde afvoer met metingen, eerst zonder en daarna met gegroepeerde fracties.

# Inlezen observaties
location_id = "ADCP261B"
df = pd.read_csv(settings.source_data_dir.joinpath("afvoermetingen", "OPP_discharge_2020_now.csv"), index_col=0)
df = df[(df["location_id"] == location_id) & (df["flag"] <= 2)][["value"]]
df.rename(columns={"value": "Meting"}, inplace=True)
df.index = pd.to_datetime(df.index)
observations = df.resample("D").mean(numeric_only=True)["Meting"]

# Plotten zonder groepering
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

# Tijdsselectie en inlezen fracties voor vervolgplots
start_time = starttime = "2023-01-01"
endtime = model.endtime - timedelta(days=1)

# Plot met groepen
ax = plot_fractional_flow(
    model=model,
    node_id=node_id,
    link_id=link_id,
    tracers=user_tracers,
    legend_outside_figure=True,
    observations=observations,
    starttime=starttime,
    endtime=endtime,
    title="Fractionele afvoer Bakelse Aa",
    ylabel="Afvoer (m3/s)",
    xlabel="Tijd",
    ymax=10,
    groups=groups,
    color_dict=color_dict,
)


# %% [markdown]

### Leeftijdsplot
#
# Plotten van de berekende verblijftijden bij de outlet.
age_csv = settings.processed_data_dir.joinpath("leeftijd", "age_outlet.csv")
if not age_csv.exists():
    print(
        "INFO: voor het aanmaken van een leeftijdsplot, moet je eerste de leeftijdsberekening uitvoeren volgens de handleiding"
    )
    print(f"INFO: sla de CSV op als {age_csv}")
else:
    age_df = pd.read_csv(age_csv, sep=";").replace(-999, float("nan"))[["AgeTR1 outlet", "AgeTR2 outlet"]]
    n_days = (model.endtime - model.starttime).days
    age_df.index = pd.date_range(start=model.starttime, periods=n_days, freq="D")
    age_df.rename(columns={"AgeTR1 outlet": "vanaf 1512", "AgeTR2 outlet": "vanaf 1363"}, inplace=True)

    age_df.loc[age_df["vanaf 1363"] > 4000, "vanaf 1363"] = float("nan")
    age_df.loc[age_df["vanaf 1512"] > 2000, "vanaf 1512"] = float("nan")

    ax = age_df.loc[slice(starttime, endtime)].plot(grid=True, ylabel="leeftijd (dagen)", xlabel="tijd")
    ax.set_ylim(0, 4000)
