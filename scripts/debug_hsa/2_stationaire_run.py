# %%

from __future__ import annotations

from datetime import datetime

from ribasim import Model

from ribasim_tools import run_ribasim, settings

# =============================================================================
# Paden
# =============================================================================
src_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "1c_sanitize_model_fix_cyclic")
src_dir_file = src_dir / "hsa.toml"
dst_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "2_stationaire_run")
dst_toml_file = dst_dir / "hsa.toml"

# =============================================================================
# Instellingen
# =============================================================================
NEERSLAG_MM_DAG = 5
EXECUTE_MODEL = False


# =============================================================================
# Helper functies
# =============================================================================
def constant_precipitation(model: Model, precipitation_mm_day: float = 5) -> None:
    """Zet een constante neerslag (mm/dag) op alle basins."""
    model.basin.time.df = model.basin.time.df.loc[model.basin.time.df.node_id == -9999]
    model.basin.time.df.node_id = model.basin.node.df.index.to_numpy()

    area = model.basin.area.df.set_index("node_id").loc[model.basin.time.df.node_id, "geometry"].area.to_numpy()

    model.basin.time.df.drainage = area * precipitation_mm_day / 86400 / 1000
    model.basin.time.df.time = model.starttime


# =============================================================================
# INLEZEN MODEL EN VOORZIEN VAN CONSTANTE NEERSLAG
# =============================================================================

model = Model.read(src_dir_file)
constant_precipitation(model, precipitation_mm_day=NEERSLAG_MM_DAG)
model.starttime = datetime(2005, 1, 1)
model.endtime = datetime(2005, 1, 10)
model.write(dst_toml_file)

# =============================================================================
# Run model
# =============================================================================
if EXECUTE_MODEL:
    run_ribasim(toml_path=dst_toml_file, ribasim_exe=settings.ribasim_exe)
