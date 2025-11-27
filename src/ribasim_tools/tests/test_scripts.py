"""Integration tests for scripts - sanity checks to ensure scripts run and produce output."""

import shutil
import subprocess
import sys
from pathlib import Path
import pytest

from ribasim_tools.settings import settings


@pytest.fixture
def scripts_dir() -> Path:
    """Return the scripts directory."""
    return Path(__file__).parents[3] / "scripts"


@pytest.fixture
def clean_processed_data():
    """Clean up processed data directory before and after tests."""
    processed_dir = settings.processed_data_dir
    
    # Clean before test
    if processed_dir.exists():
        for item in processed_dir.iterdir():
            if item.is_dir() and item.name in ["basic_delwaq", "LHM_AAM_clipped"]:
                shutil.rmtree(item, ignore_errors=True)
    
    yield processed_dir
    
    # Clean after test (optional - comment out if you want to inspect results)
    for item in processed_dir.iterdir():
        if item.is_dir() and item.name in ["basic_delwaq", "LHM_AAM_clipped"]:
            shutil.rmtree(item, ignore_errors=True)


def run_script(script_path: Path) -> subprocess.CompletedProcess:
    """Run a Python script and return the result."""

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        cwd=script_path.parent,
    )
    return result


def test_basic_delwaq_example(scripts_dir: Path):
    """Test script 1 (basic delwaq example) runs successfully and creates output."""
    script_path = scripts_dir / "1_ribasim_delwaq_basic_example.py"

    # Run the script
    result = run_script(script_path)
    
    # Check script ran successfully
    if result.returncode != 0:
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
    assert result.returncode == 0, f"Script should run without errors. Error: {result.stderr}"
    
    # Check expected outputs were created
    output_dir = settings.processed_data_dir / "basic_delwaq"
    assert output_dir.exists(), "Output directory should be created"
    
    results_dir = output_dir / "results"
    assert results_dir.exists(), "Results directory should be created"
    
    delwaq_dir = output_dir / "delwaq"
    assert delwaq_dir.exists(), "Delwaq directory should be created"
    assert len(list(delwaq_dir.iterdir())) > 0, "Delwaq directory should contain files"


def test_basic_hsa_example(scripts_dir: Path):
    """Test script 1 (basic hsa example) runs successfully and creates output."""
    script_path = scripts_dir / "1_ribasim_delwaq_hsa_example.py"

    # Run the script
    result = run_script(script_path)
    
    # Check script ran successfully
    if result.returncode != 0:
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
    assert result.returncode == 0, f"Script should run without errors. Error: {result.stderr}"
    
    # Check expected outputs were created
    output_dir = settings.processed_data_dir / "basic_hsa"
    assert output_dir.exists(), "Output directory should be created"
    
    results_dir = output_dir / "results"
    assert results_dir.exists(), "Results directory should be created"
    
    delwaq_dir = output_dir / "delwaq"
    assert delwaq_dir.exists(), "Delwaq directory should be created"
    assert len(list(delwaq_dir.iterdir())) > 0, "Delwaq directory should contain files"


def test_clip_lhm_aam(scripts_dir: Path):
    """Test that script 2 (clip LHM AAM) runs successfully."""
    script_path = scripts_dir / "2_clip_LHM_AAM.py"
    assert script_path.exists(), f"Script should exist at {script_path}"
    
    # Check prerequisites
    clip_boundary = settings.source_data_dir.joinpath("shp", "subcatchments_Bakelse_Aa.shp")
    assert clip_boundary.exists(), "Clip boundary shapefile should exist"
    
    # Run the script
    result = run_script(script_path)
    
    # Check script ran successfully
    if result.returncode != 0:
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
    assert result.returncode == 0, f"Script should run without errors. Error: {result.stderr}"
    
    # Check output was created
    output_dir = settings.processed_data_dir / "LHM_AAM_clipped"
    output_path = output_dir / "aam.toml"
    assert output_path.exists(), "Clipped model should be written"
    assert (output_dir / "results" / "basin.arrow").exists(), "Database should be created"


def test_clip_hsa(scripts_dir: Path):
    """Test that script 2 (clip HSA) runs successfully."""
    script_path = scripts_dir / "2_clip_HSA.py"
    assert script_path.exists(), f"Script should exist at {script_path}"
    
    # Check prerequisites
    clip_boundary = settings.source_data_dir.joinpath("shp", "subcatchments_Bakelse_Aa.shp")
    assert clip_boundary.exists(), "Clip boundary shapefile should exist"
    
    # Run the script
    result = run_script(script_path)
    
    # Check script ran successfully
    if result.returncode != 0:
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
    assert result.returncode == 0, f"Script should run without errors. Error: {result.stderr}"
    
    # Check output was created
    output_dir = settings.processed_data_dir / "hsa_model_clipped"
    output_path = output_dir / "ribasim.toml"
    assert output_path.exists(), "Clipped model should be written"

def test_lhm_aam_delwaq(scripts_dir: Path):
    """Test script 3 (LHM AAM Delwaq) runs successfully."""
    script_path = scripts_dir / "3_LHM_AAM_Delwaq.py"
    assert script_path.exists(), f"Script should exist at {script_path}"
    
    # Run the script
    result = run_script(script_path)
    
    # Check script ran successfully
    if result.returncode != 0:
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
    assert result.returncode == 0, f"Script should run without errors. Error: {result.stderr}"
    
    # Check output was created
    output_dir = settings.processed_data_dir / "LHM_AAM_delwaq"
    output_path = output_dir / "aam.toml"
    assert output_path.exists(), "Model should be written"

    output_dir = settings.processed_data_dir / "LHM_AAM_delwaq" / "results"
    output_path = output_dir / "basin.arrow"
    assert output_path.exists(), "Model should be written"

    output_dir = settings.processed_data_dir / "LHM_AAM_delwaq" / "delwaq"
    output_path = output_dir / "dimr_config.xml"
    assert output_path.exists(), "Delwaq is written"
