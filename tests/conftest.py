"""Pytest configuration and shared fixtures for ribasim_tools tests."""

import shutil
from pathlib import Path

import pytest
from ribasim import Model

from ribasim_tools.download_testmodels import download_testmodels
from ribasim_tools.settings import settings


@pytest.fixture(scope="session")
def testmodels_dir() -> Path:
    """Download test models once per test session and return the directory."""
    download_testmodels(overwrite=False)
    return settings.data_dir / "generated_testmodels"


@pytest.fixture
def basic_model(testmodels_dir: Path) -> Model:
    """Load a fresh copy of the basic test model for each test."""
    toml_path = testmodels_dir / "basic" / "ribasim.toml"
    return Model.read(toml_path)


@pytest.fixture
def temp_model_dir(tmp_path: Path):
    """Create a temporary directory for test model outputs."""
    model_dir = tmp_path / "test_model"
    model_dir.mkdir(parents=True, exist_ok=True)
    yield model_dir
    # Cleanup after test
    shutil.rmtree(model_dir, ignore_errors=True)


@pytest.fixture
def basic_model_copy(basic_model: Model, temp_model_dir: Path) -> tuple[Model, Path]:
    """Create a copy of the basic model in a temporary directory.
    
    Returns:
        tuple[Model, Path]: The model and its toml path in the temp directory
    """
    toml_path = temp_model_dir / "ribasim.toml"
    basic_model.write(toml_path)
    return basic_model, toml_path
