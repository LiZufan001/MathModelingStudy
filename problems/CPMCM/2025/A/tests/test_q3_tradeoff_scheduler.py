from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q3_tradeoff_scheduler import schedule_q3_critical_window


def test_window_zero_reproduces_base_order() -> None:
    nodes = [
        Node(0, "A", pipe="CUBE", cycles=1),
        Node(1, "X", pipe="VECTOR", cycles=200),
        Node(2, "B", pipe="CUBE", cycles=100),
        Node(3, "Y", pipe="VECTOR", cycles=1),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (2, 3)])
    base = (2, 0, 1, 3)
    result = schedule_q3_critical_window(graph, base, window=0)
    assert result.order == base
    assert result.changed_positions == 0
    assert result.evaluation.valid


def test_wide_window_prioritizes_longer_bottom_level() -> None:
    nodes = [
        Node(0, "A", pipe="CUBE", cycles=1),
        Node(1, "X", pipe="VECTOR", cycles=200),
        Node(2, "B", pipe="CUBE", cycles=100),
        Node(3, "Y", pipe="VECTOR", cycles=1),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (2, 3)])
    base = (2, 0, 1, 3)
    result = schedule_q3_critical_window(graph, base, window=4)
    assert result.order[0] == 0
    assert result.changed_positions > 0
    assert result.evaluation.valid


def test_wide_window_preserves_l0_single_residency_order() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L0A"),
        Node(1, "SHORT", pipe="CUBE", cycles=1, bufs=(0,)),
        Node(2, "FREE", 0, 4, "L0A"),
        Node(3, "ALLOC", 1, 4, "L0A"),
        Node(4, "LONG", pipe="CUBE", cycles=100, bufs=(1,)),
        Node(5, "FREE", 1, 4, "L0A"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [(0, 1), (1, 2), (3, 4), (4, 5)],
    )
    base = (0, 1, 2, 3, 4, 5)
    result = schedule_q3_critical_window(graph, base, window=100)
    pos = {node_id: i for i, node_id in enumerate(result.order)}
    assert pos[2] < pos[3]
    assert result.evaluation.valid
