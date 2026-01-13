# %%

from __future__ import annotations

from ribasim import Model

from ribasim_tools import run_ribasim, settings

# =============================================================================
# Paden
# =============================================================================
src_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "2_stationaire_run")
src_dir_file = src_dir / "hsa.toml"
dst_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "3_basin_area_vergroten")
dst_toml_file = dst_dir / "hsa.toml"

# =============================================================================
# Instellingen
# =============================================================================
BASIN_NODE_IDS = [40000042, 40000219, 30000029, 30000495, 10000449]
BASIN_AREA_MULTIPLICATION_FACTOR = 20
EXECUTE_MODEL = False

# =============================================================================
# INLEZEN MODEL EN BASIN AREA VERGROTEN
# =============================================================================

model = Model.read(src_dir_file)
model.basin.profile.df.loc[model.basin.profile.df.node_id.isin(BASIN_NODE_IDS), "area"] *= (
    BASIN_AREA_MULTIPLICATION_FACTOR
)

model.write(dst_toml_file)

# =============================================================================
# Run model
# =============================================================================
if EXECUTE_MODEL:
    run_ribasim(toml_path=dst_toml_file, ribasim_exe=settings.ribasim_exe)
