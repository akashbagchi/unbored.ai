"""Tests for unbored/generate_graph_position.py"""
import json
import math
import pytest

from unbored.generate_graph_position import (
    generate_graph_positions,
    adaptive_params,
    adaptive_viewport,
    de_overlap,
)


def _write_graph(path, nodes, edges):
    graph = {"nodes": nodes, "edges": edges}
    path.write_text(json.dumps(graph))


# ── generate_graph_positions ──────────────────────────────────────────────────

def test_generate_positions_adds_xy_to_nodes(tmp_path):
    in_path = tmp_path / "graph.json"
    out_path = tmp_path / "out.json"
    _write_graph(in_path,
                 [{"id": "a"}, {"id": "b"}, {"id": "c"}],
                 [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}])
    generate_graph_positions(str(in_path), str(out_path))
    result = json.loads(out_path.read_text())
    for node in result["nodes"]:
        assert "x" in node, f"Node missing x: {node}"
        assert "y" in node, f"Node missing y: {node}"


def test_generate_positions_small_graph(tmp_path):
    """n < 60 uses spring layout — should not crash."""
    nodes = [{"id": str(i)} for i in range(10)]
    edges = [{"source": str(i), "target": str(i + 1)} for i in range(9)]
    in_path = tmp_path / "graph.json"
    out_path = tmp_path / "out.json"
    _write_graph(in_path, nodes, edges)
    generate_graph_positions(str(in_path), str(out_path))
    result = json.loads(out_path.read_text())
    assert len(result["nodes"]) == 10


def test_generate_positions_large_graph(tmp_path):
    """n >= 60 uses community strategy — should not crash."""
    nodes = [{"id": str(i)} for i in range(65)]
    edges = [{"source": str(i), "target": str(i + 1)} for i in range(64)]
    in_path = tmp_path / "graph.json"
    out_path = tmp_path / "out.json"
    _write_graph(in_path, nodes, edges)
    generate_graph_positions(str(in_path), str(out_path))
    result = json.loads(out_path.read_text())
    assert len(result["nodes"]) == 65


def test_empty_graph_no_crash(tmp_path):
    in_path = tmp_path / "graph.json"
    out_path = tmp_path / "out.json"
    _write_graph(in_path, [], [])
    generate_graph_positions(str(in_path), str(out_path))
    result = json.loads(out_path.read_text())
    assert result["nodes"] == []
    assert result["edges"] == []


# ── adaptive_params ───────────────────────────────────────────────────────────

def test_adaptive_params_scales_with_n():
    k_small, spread_small, min_dist_small, _ = adaptive_params(5)
    k_large, spread_large, min_dist_large, _ = adaptive_params(500)
    # k (repulsion) should be smaller for large graphs
    assert k_small > k_large
    # spread and min_dist should grow with n
    assert spread_large > spread_small
    assert min_dist_large > min_dist_small


# ── adaptive_viewport ─────────────────────────────────────────────────────────

def test_adaptive_viewport_scales_with_n():
    w_small, h_small = adaptive_viewport(10)
    w_large, h_large = adaptive_viewport(500)
    assert w_large >= w_small
    assert h_large >= h_small


# ── de_overlap ────────────────────────────────────────────────────────────────

def test_de_overlap_min_distance_satisfied():
    # Place two nodes very close together and verify de_overlap separates them.
    pos = {"a": (0.0, 0.0), "b": (1.0, 0.0)}
    min_dist = 100.0
    result = de_overlap(pos, min_dist=min_dist, passes=10)
    ax, ay = result["a"]
    bx, by = result["b"]
    dist = math.hypot(bx - ax, by - ay)
    assert dist >= min_dist * 0.99, f"Nodes too close: {dist:.2f} < {min_dist}"
