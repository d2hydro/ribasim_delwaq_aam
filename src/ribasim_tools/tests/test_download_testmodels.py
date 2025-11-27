"""Tests for download_testmodels function."""

from pathlib import Path

import pytest

from ribasim_tools.download_testmodels import download_testmodels
from ribasim_tools.settings import settings


def test_download_testmodels_creates_directory(testmodels_dir: Path):
    """Test that download_testmodels creates the expected directory."""
    assert testmodels_dir.exists()
    assert testmodels_dir.is_dir()


def test_download_testmodels_contains_basic_model(testmodels_dir: Path):
    """Test that the basic model exists after download."""
    basic_model_path = testmodels_dir / "basic" / "ribasim.toml"
    assert basic_model_path.exists()


def test_download_testmodels_contains_multiple_models(testmodels_dir: Path):
    """Test that multiple test models are downloaded."""
    # Check for a few known test models
    expected_models = ["basic", "basic_transient", "bucket"]
    
    for model_name in expected_models:
        model_dir = testmodels_dir / model_name
        assert model_dir.exists(), f"Expected model '{model_name}' not found"
