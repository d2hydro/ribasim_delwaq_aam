# %%
from pathlib import Path

from IPython.display import display
from ribasim import Model
from ribasim.delwaq import add_tracer

data_dir = Path(__file__).parents[1] / "data"

model = Model.read(data_dir / "basic_model" / "ribasim.toml")

# %% display model
display(model.basin.concentration_state)  # basin initial state
display(model.basin.concentration)  # basin boundaries
display(model.flow_boundary.concentration)  # flow boundaries
display(model.level_boundary.concentration)  # level boundaries
display(model.basin.profile)
model.plot()  # for later comparison


# %% Add traces Foo and Bar
add_tracer(model, 11, "Foo")
add_tracer(model, 15, "Bar")
display(model.flow_boundary.concentration)  # flow boundaries
display(model.level_boundary.concentration)  # flow boundaries

# %%
