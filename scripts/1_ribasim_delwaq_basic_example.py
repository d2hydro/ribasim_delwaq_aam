# %% [markdown]
# # Ribasim Delwaq basisvoorbeeld
# De stappen zijn grotendeels overgenomen van een Ribasim Delwaq [voorbeeld](https://ribasim.org/guide/delwaq.html). 
# Voor verdere informatie kan je de [Ribasim documentatie](https://ribasim.org/concept/concept.html) raadplegen. 
# Deze workflow is een voorbeeld om:

# 1. Een Ribasim schematisatie in te laden en weer te geven
# 2. Toewijzen van concentraties en toevoegen van tracers in Ribasim model
# 3. Ribasim berekening uitvoeren
# 4. Genereren van een Delwaq schematisatie op basis van het Ribasim model
# 4. Delwaq berekeningen uitvoeren
# 5. Fracties van tracers per basins visualiseren

# Om Delwaq invoerbestanden te genereren is een doorgerekend Ribasim model (meestal met `results` map) nodig. 
# Ideaal heeft de Ribasim schematisatie ook enkele stoffen gedefinieerd en initiële concentraties.  

# ### Importeren van de benodigde libraries
# De meeste packages spreken voor zich, deze workflow bevat naast standaard packages ook extra functionaliteit vanuit `ribasim_tools`. 
# Alle packages zouden al binnen de huidige .pixi omgeving geïnstalleerd moeten zijn.

import shutil
import matplotlib.pyplot as plt
import networkx as nx
from IPython.display import display
from ribasim import Model
from ribasim.delwaq import add_tracer, generate, parse, plot_fraction
from ribasim_tools import download_testmodels, run_delwaq, run_ribasim, settings
# %% [markdown]
# ### Downloaden van het Basic ribasim model vanuit de Ribasim GitHub repository
# We nemen hier een voorbeeld model, als je een ander Ribasim model wilt inladen: verander het `toml_path` om een ander Ribasim model in te lezen. 
# Ook kan je het `.env`-bestand aanpassen waarin dezelfde verwijzing staat naar de padnaam van het Ribasim model. 
# Het `.env`-bestand is een [tekst bestand](https://www.geeksforgeeks.org/python/how-to-create-and-use-env-files-in-python/) waarin settings naar ribasim en dimr .exe's kunnen worden opgegeven. 

download_testmodels(overwrite=True)
toml_path = settings.source_data_dir.joinpath("generated_testmodels", "basic", "ribasim.toml")
assert toml_path.exists()

# %% [markdown]
### Inlezen en tonen van het basic Ribasim model
# Het Ribasim test model heeft al de stof `Cl` en een `Tracer` voorgedefinieerd in de input tabellen. 
# We gaan hier enkele toevoegen voordat we ze gebruiken voor de Ribasim en Delwaq input bestanden.
model = Model.read(toml_path)
display(model.basin.concentration_state)  # basin initial state
display(model.basin.concentration)  # basin boundaries
display(model.flow_boundary.concentration)  # flow boundaries
display(model.level_boundary.concentration)  # level boundaries
display(model.basin.profile)
model.plot()  # for later comparison


# %% [markdown]
# ### Toevoegen van twee fictieve tracers Foo and Bar aan Node # 11 en Node # 15
# Hier voegen we nog 2 tracers toe, aan knopen 11 en 15, en geven ze een label.
# Merk op dat de concentraties zijn veranderd ten opzichte van de initiële waarden; 
# aan de `FlowBoundary` is een extra rij `Bar` verschenen met een concentratie van 1. 
# Bij de `LevelBoundary` is een extra rij `Foo` verschenen met een concentratie van 1.

add_tracer(model, 11, "Foo")
add_tracer(model, 15, "Bar")
display(model.flow_boundary.concentration)  # flow boundaries
display(model.level_boundary.concentration)  # level boundaries

# %% [markdown]
# ### Eventuele resultaten uit een eerdere run verwijderen en het model opslaan op een nieuwe locatie
# Het model wordt hier met ribasim.exe uitgevoerd. 
# Mocht het crashen op het niet kunnen vinden van Ribasim dan kan je het pad naar Ribasim aanpassen in het `.env` bestand.

toml_path = settings.processed_data_dir.joinpath("basic_delwaq") / model.filepath.name
shutil.rmtree(toml_path.parent, ignore_errors=True)
model.write(toml_path)
specs = run_ribasim(toml_path, settings.ribasim_exe)
assert specs.exit_code == 0

# %% [markdown]
# ### Genereren van het delwaq netwerk op basis van het Ribasim model
# Met het pad naar een volledig doorgerekend Ribasim model kunnen we een Delwaq schematisatie opzetten. 
# `generate` heeft een pad naar een (Ribasim) .toml-bestand nodig, of een `Model` object, en een pad naar een output map. 
# De default waarde slaat de Delwaq input bestanden in een aparte `delwaq` map naast het .toml-bestand.
output_path = model.filepath.parent.joinpath("delwaq")
graph, substances = generate(toml_path, output_path)
list(output_path.iterdir())
list(substances)

# %% [markdown]
## Delwaq en ribasim schematisaties plotten
# Hieronder worden de node ID's van de verschillende schematisatie getoond. 
# Merk op dat elke basin in Ribasim wordt opgesplitst in 3 aparte bakjes. 
# Door middel van de verschillende bakjes kan Delwaq de schematisatie opbouwen en er eigen node ID's van maken.
#  De delwaq node ID's worden weer omgezet naar Ribasim ID's bij het inladen.

fig, ax = plt.subplots(1, 2, figsize=(10, 5))
nx.draw(
    graph,
    pos={k: v["pos"] for k, v in graph.nodes(data=True)},
    with_labels=True,
    labels={k: k for k, v in graph.nodes(data=True)},
    ax=ax[0],
)
ax[0].set_title("Delwaq node IDs")
nx.draw(
    graph,
    pos={k: v["pos"] for k, v in graph.nodes(data=True)},
    with_labels=True,
    labels={k: v["id"] for k, v in graph.nodes(data=True)},
    ax=ax[1],
)
ax[1].set_title("Ribasim node IDs")
fig.suptitle("Delwaq network")

# %% [markdown]
# ### Runnen van Delwaq met de DHydro DIMR
# Onderstaande code runt de Delwaq input bestanden. 
# We gebruiken hiervoor de D-Hydro DeltaShell dimr in plaats van de delwaq executable omdat deze betrouwbaarder is.
from pathlib import Path

dimr_config = toml_path.parent.joinpath("delwaq", "dimr_config.xml")
print(dimr_config)
settings.run_dimr_bat = Path(
    r"c:\Program Files\Deltares\D-HYDRO Suite 2025.02 1D2D\plugins\DeltaShell.Dimr\kernels\x64\bin\run_dimr.bat"
)
specs = run_delwaq(dimr_config=dimr_config, run_dimr_bat=settings.run_dimr_bat)
assert specs.exit_code == 0

# %% [markdown]
### Inlezen van de Delwaq resultaten in het Ribasim model en plotten van de concentraties van de twee tracers in Basin #9
# Hieronder een voorbeeld om de fracties te plotten van een van de basins (node #9).

nmodel = parse(toml_path, graph, substances, output_folder=output_path)

plot_fraction(nmodel, 9, ["Foo", "Bar"])
plot_fraction(nmodel, 6)
# %%
