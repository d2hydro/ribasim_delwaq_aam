# %%
from pathlib import Path

import geopandas as gpd
import pandas as pd
from ribasim import Model
from ribasim.config import Solver

from ribasim_tools import run_ribasim, settings

# =============================================================================
# Paden
# =============================================================================
src_dir = settings.source_data_dir.joinpath("hsa_model")
src_toml_file = src_dir / "ribasim.toml"
dst_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "1a_sanitize_model")
dst_toml_file = dst_dir / "hsa.toml"
dst_gpkg = dst_dir / "database.gpkg"

# %%
# =============================================================================
# Instellingen
# =============================================================================
MANNING_RESISTANCE_STATIC_LAYER = "ManningResistance / static"
OUTLET_STATIC_LAYER = "Outlet / static"
PUMP_STATIC_LAYER = "Pump / static"
EXECUTE_MODEL = False


# =============================================================================
# Helper functies
# =============================================================================
def read_layer_df(gpkg: Path, layer: str) -> pd.DataFrame:
    df = gpd.read_file(gpkg, layer=layer)
    if "geometry" in df.columns:
        df = df.drop(columns="geometry")
    return pd.DataFrame(df)


def overwrite_layer(gpkg: Path, layer: str, df: pd.DataFrame) -> None:
    gpd.GeoDataFrame(df.copy(), geometry=None).to_file(gpkg, layer=layer, driver="GPKG")


def constant_precipitation(model: Model, precipitation_mm_day: float = 5) -> None:
    """Zet een constante neerslag (mm/dag) op alle basins."""
    model.basin.time.df = model.basin.time.df.loc[model.basin.time.df.node_id == -9999]
    model.basin.time.df.node_id = model.basin.node.df.index.to_numpy()

    area = model.basin.area.df.set_index("node_id").loc[model.basin.time.df.node_id, "geometry"].area.to_numpy()

    model.basin.time.df.drainage = area * precipitation_mm_day / 86400 / 1000
    model.basin.time.df.time = model.starttime


# =============================================================================
# Kopieren van model, vóór fixen import
# =============================================================================
# Let op(!) vanaf ribasim 2026.1.0RC1 zul je de database eerst handmatig moeten updaten voordat je kunt importeren.
# Gebruik dan deze code
# if dst_dir.exists():
#     shutil.rmtree(dst_dir)
# dst_dir.parent.mkdir(parents=True, exist_ok=True)
# shutil.copytree(src_dir, dst_dir)

# Active kolom op None zetten, zodat model kan worden ingelezen
# Outlet control_state expliciet op flow_rate zetten om parse fouten te voorkomen
# for layer in [MANNING_RESISTANCE_STATIC_LAYER, OUTLET_STATIC_LAYER, PUMP_STATIC_LAYER]:
#     df = read_layer_df(dst_gpkg, layer)
#     df["active"] = None
#     if layer == OUTLET_STATIC_LAYER and "control_state" in df.columns:
#         df["control_state"] = "flow_rate"
#     overwrite_layer(dst_gpkg, layer, df)

model = Model.read(src_toml_file)
# Solver herinitialiseren (abstol, reltol op defaults)
model.solver = Solver()

model.write(dst_toml_file)

# =============================================================================
# Run model
# =============================================================================

if EXECUTE_MODEL:
    run_ribasim(toml_path=dst_toml_file, ribasim_exe=settings.ribasim_exe)

# %%
