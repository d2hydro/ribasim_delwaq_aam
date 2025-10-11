# %%

import shutil

import matplotlib.pyplot as plt
import networkx as nx
from IPython.display import display
from ribasim import Model
from ribasim.delwaq import add_tracer, generate, parse, plot_fraction

from ribasim_tools import download_test_models, run_delwaq, run_ribasim, settings

download_test_models(overwrite=True)

toml_path = settings.data_dir.joinpath("generated_testmodels", "basic", "ribasim.toml")
assert toml_path.exists()
model = Model.read(toml_path)

# %%

# Tonen van het model
display(model.basin.concentration_state)  # basin initial state
display(model.basin.concentration)  # basin boundaries
display(model.flow_boundary.concentration)  # flow boundaries
display(model.level_boundary.concentration)  # level boundaries
display(model.basin.profile)
model.plot()  # for later comparison


# %%

# Toevoegen van tracers Foo and Bar
add_tracer(model, 11, "Foo")
add_tracer(model, 15, "Bar")
display(model.flow_boundary.concentration)  # flow boundaries
display(model.level_boundary.concentration)  # flow boundaries

# %%

# Eventueel bestaand model verwijderen, herschrijven en runnen van ribasim
toml_path = settings.data_dir.joinpath("basic_delwaq") / model.filepath.name
shutil.rmtree(toml_path.parent, ignore_errors=True)
model.write(toml_path)
run_ribasim(toml_path, settings.ribasim_exe)

# %%

# Genereren van het delwaq netwerk en runnen van delwaq
output_path = model.filepath.parent.joinpath("delwaq")
graph, substances = generate(toml_path, output_path)
list(output_path.iterdir())
list(substances)

dimr_config = toml_path.parent.joinpath("delwaq", "dimr_config.xml")

run_delwaq(dimr_config=dimr_config, run_dimr_bat=settings.run_dimr_bat)
# %%


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


nmodel = parse(toml_path, graph, substances, output_folder=output_path)

plot_fraction(nmodel, 9, ["Foo", "Bar"])
