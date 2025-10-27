# %%
from ribasim import Model, Node
from ribasim.nodes import outlet
from shapely.geometry import Point

from ribasim_tools import run_ribasim, settings

# %% [markdown]

## Inlezen geknipte model
toml_path = settings.data_dir.joinpath("lhm_aam", "LHM_AAM_clipped", "aam.toml")
model = Model.read(toml_path)


# %% [markdown]

## Bewerken randvoorwaarden
#
# De Outlets bij het Kanaal van Deurne en Defensiekanaal krijgen een inlaatcapaciteit die overeen komt met
# de gewenste aanvoerdebieten

# Nieuwe inlaat Deurne naar Oude Aa, vanaf kanaal van Deurne naar Basin # 1226 met een capaciteit van 0.3 m3/s
node = model.outlet.add(Node(geometry=Point(188116.74, 381743.37)), tables=[outlet.Static(flow_rate=[0.3])])
model.link.add(model.level_boundary[1280], node)
model.link.add(node, model.basin[1226])

# overige inlaten
for flow_rate, node_id in [(0.1, 2029), (0.025, 2034), (0.025, 601), (0.075, 156)]:
    model.outlet.static.df.loc[model.outlet.static.df.node_id == node_id, "flow_rate"] = flow_rate


# %% [markdown]

model.write(toml_path.parent.with_name("LHM_AAM_delwaq") / toml_path.name)
run_ribasim(model.filepath, ribasim_exe=settings.ribasim_exe)
