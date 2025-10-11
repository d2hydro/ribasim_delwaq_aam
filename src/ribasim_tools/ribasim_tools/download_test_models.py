# %%
import shutil
import zipfile
from importlib.metadata import version
from io import BytesIO

import requests

from ribasim_tools.settings import settings


def download_test_models(overwrite: bool = True):
    """Download test models from the ribasim_delwaq_aam repository"""
    # create data_dir
    file_name = "generated_testmodels"
    dst_dir = settings.data_dir / file_name
    if overwrite or (not dst_dir.exists()):
        shutil.rmtree(dst_dir, ignore_errors=True)
        dst_dir.mkdir(parents=True, exist_ok=True)

        ribasim_version = version("ribasim")
        file_name = "generated_testmodels"
        url = f"https://github.com/Deltares/Ribasim/releases/download/v{ribasim_version}/{file_name}.zip"

        #
        response = requests.get(url)
        response.raise_for_status()

        # unzip and save files
        with zipfile.ZipFile(BytesIO(response.content), "r") as zip_ref:
            zip_ref.extractall(dst_dir)

        print("Test models downloaded.")
