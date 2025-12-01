"""Tests for drop_nodes function."""

import pytest
from ribasim import Model

from ribasim_tools.drop_nodes import drop_nodes


def test_drop_nodes_removes_specified_nodes(basic_model: Model):
    """Test that drop_nodes removes the specified nodes."""
    original_node_count = len(basic_model.node_table().df)
    
    # Drop a couple of nodes (pick node IDs from the basic model)
    nodes_to_drop = [6, 15]
    
    result_model = drop_nodes(basic_model, nodes_to_drop, inplace=False)
    
    new_node_count = len(result_model.node_table().df)
    assert new_node_count < original_node_count


def test_drop_nodes_with_copy_returns_modified_model(basic_model: Model):
    """Test that inplace=False returns a modified model."""
    original_node_count = len(basic_model.node_table().df)
    
    nodes_to_drop = [1, 16]
    # inplace=False creates a copy and modifies it
    result_model = drop_nodes(basic_model, nodes_to_drop, inplace=False)
    
    # The returned copy should have fewer nodes
    assert result_model is not None
    assert len(result_model.node_table().df) < original_node_count


def test_drop_nodes_empty_list(basic_model: Model):
    """Test that dropping no nodes returns unchanged model."""
    original_node_count = len(basic_model.node_table().df)
    
    result_model = drop_nodes(basic_model, [], inplace=False)
    
    assert len(result_model.node_table().df) == original_node_count
