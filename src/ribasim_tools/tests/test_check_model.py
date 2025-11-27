"""Tests for check_model functions."""

import pytest
from ribasim import Model

from ribasim_tools.check_model import check_level_boundaries_for_delwaq


def test_check_level_boundaries_valid_model(basic_model: Model):
    """Test that a valid model passes the level boundary check."""
    check_level_boundaries_for_delwaq(basic_model)

