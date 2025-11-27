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


settings = Settings()
