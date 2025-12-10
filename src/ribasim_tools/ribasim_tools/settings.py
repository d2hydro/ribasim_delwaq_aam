# file taken from https://github.com/Deltares/Ribasim-NL/tree/main/src/ribasim_nl/ribasim_nl
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    source_data_dir: Path = Path(__file__).parents[3] / "source_data"
    processed_data_dir: Path = Path(__file__).parents[3] / "processed_data"
    ribasim_exe: Path = Path("ribasim")
    run_dimr_bat: Path = Path(
        r"c:\Program Files\Deltares\D-HYDRO Suite 2025.02 1D2D\plugins\DeltaShell.Dimr\kernels\x64\bin\run_dimr.bat"
    )
    model_config = SettingsConfigDict(env_file=(".env"))

    ###############################
    # 📁 LHM Aa en Maas file paths
    ###############################

    @property
    def LHM_AAM_toml_path(self) -> Path:
        return self.source_data_dir.joinpath("lhm_aam", "AaenMaas_2025_9_0", "aam.toml")

    @property
    def LHM_BA_toml_path(self) -> Path:
        return self.processed_data_dir.joinpath("lhm_aam", "LHM_BA", "LHM_BA.toml")

    @property
    def LHM_BA_RVW_toml_path(self) -> Path:
        return self.processed_data_dir.joinpath("lhm_aam", "LHM_BA_RVW", "LHM_BA.toml")

    @property
    def LHM_BA_Delwaq_toml_path(self) -> Path:
        return self.processed_data_dir.joinpath("lhm_aam", "LHM_BA_Delwaq", "LHM_BA.toml")

    @property
    def LHM_BA_Delwaq_output_dir(self) -> Path:
        return self.LHM_BA_Delwaq_toml_path.parent / "delwaq_output"

    ###############################
    # 📁 HSA file paths
    ###############################

    @property
    def HSA_toml_path(self) -> Path:
        return self.source_data_dir.joinpath("hsa_model", "ribasim.toml")

    @property
    def HSA_BA_toml_path(self) -> Path:
        return self.processed_data_dir.joinpath("hsa_model", "HSA_BA", "HSA_BA.toml")


settings = Settings()
