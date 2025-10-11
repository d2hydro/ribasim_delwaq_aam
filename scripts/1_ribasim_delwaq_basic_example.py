# %%

## Importeren van de benodigde libraries

import shutil

import matplotlib.pyplot as plt
import networkx as nx
from IPython.display import display
from ribasim import Model
from ribasim.delwaq import add_tracer, generate, parse, plot_fraction

from ribasim_tools import download_testmodels, run_delwaq, run_ribasim, settings

# %%

# Downloaden van het Basic ribasim model vanuit de Ribasim GitHub repository
download_testmodels(overwrite=True)

toml_path = settings.data_dir.joinpath("generated_testmodels", "basic", "ribasim.toml")
assert toml_path.exists()


# %%

# Inlezen en tonen van het basic Ribasim model

model = Model.read(toml_path)
display(model.basin.concentration_state)  # basin initial state
display(model.basin.concentration)  # basin boundaries
display(model.flow_boundary.concentration)  # flow boundaries
display(model.level_boundary.concentration)  # level boundaries
display(model.basin.profile)
model.plot()  # for later comparison


# %%

# Toevoegen van twee fictieve tracers Foo and Bar aan Node # 11 en Node # 15
# Merk op dat de concentraties zijn veranderd ten opzichte van de initiële waarden
add_tracer(model, 11, "Foo")
add_tracer(model, 15, "Bar")
display(model.flow_boundary.concentration)  # flow boundaries
display(model.level_boundary.concentration)  # level boundaries

# %%

# Eventuele resultaten uit een eerdere run verwijderen en het model opslaan op een nieuwe locatie
# Het model wordt hierna met ribasim.exe gerund
toml_path = settings.data_dir.joinpath("basic_delwaq") / model.filepath.name
shutil.rmtree(toml_path.parent, ignore_errors=True)
model.write(toml_path)
run_ribasim(toml_path, settings.ribasim_exe)

# %%

# Genereren van het delwaq netwerk op basis van het Ribasim model

output_path = model.filepath.parent.joinpath("delwaq")
graph, substances = generate(toml_path, output_path)
list(output_path.iterdir())
list(substances)

# Let's draw the graph
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

# %%

# Runnen van Delwaq met de DHydro DIMR
dimr_config = toml_path.parent.joinpath("delwaq", "dimr_config.xml")

run_delwaq(dimr_config=dimr_config, run_dimr_bat=settings.run_dimr_bat)

# %%

# Inlezen van de Delwaq resultaten ín het RIBASIM model en plotten van de concentraties van de twee tracers in Basin #9
nmodel = parse(toml_path, graph, substances, output_folder=output_path)

plot_fraction(nmodel, 9, ["Foo", "Bar"])
