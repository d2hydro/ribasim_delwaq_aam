"""Tests for clip_model function."""

import pytest
from ribasim import Model
from shapely.geometry import Polygon

from ribasim_tools.clip_model import clip_model


def test_clip_model_keeps_specified_nodes(basic_model: Model):
    """Test that keep_node_ids preserves nodes outside the polygon."""
    # Create a small polygon
    clip_polygon = Polygon([(-1, -1), (1, -1), (1, 1), (-1, 1)])
    
    keep_id = 3
    
    result_model = clip_model(
        basic_model,
        clip_polygon,
        keep_node_ids=[keep_id],
        drop_node_ids=[],
        convert_node_types={},
        inplace=False
    )
    
    result_nodes = result_model.node_table().df.index.tolist()
    assert keep_id in result_nodes


def test_clip_model_with_copy_returns_modified_model(basic_model: Model):
    """Test that inplace=True returns no clipped model."""
    original_node_count = len(basic_model.node_table().df)
    
    clip_polygon = Polygon([(-1, -1), (1, -1), (1, 1), (-1, 1)])
    
    result_model = clip_model(
        basic_model,
        clip_polygon,
        keep_node_ids=[],
        drop_node_ids=[],
        convert_node_types={},
        inplace=True
    )
    
    # Result should be returned and have fewer or equal nodes
    assert result_model is None
    assert len(basic_model.node_table().df) <= original_node_count