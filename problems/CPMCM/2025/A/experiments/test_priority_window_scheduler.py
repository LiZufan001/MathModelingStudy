from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EXP = ROOT / "experiments"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(EXP))

from model import ComputeGraph, Node
from priority_window_scheduler import PRIORITY_POLICIES, schedule_priority_window


def test_window_zero_reproduces_base_for_every_policy() -> None:
    nodes = [
        Node(0, "A", pipe="CUBE", cycles=1),
        Node(1, "X", pipe="VECTOR", cycles=20),
        Node(2, "B", pipe="CUBE", cycles=10),
        Node(3, "Y", pipe="VECTOR", cycles=1),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (2, 3)])
    base = (2, 0, 1, 3)
    for policy in PRIORITY_POLICIES:
        result = schedule_priority_window(graph, base, window=0, policy=policy)
        assert result.order == base
        assert result.changed_positions == 0
        assert result.evaluation.valid


def test_pipe_remaining_can_prefer_busier_pipe() -> None:
    nodes = [
        Node(0, "A", pipe="CUBE", cycles=10),
        Node(1, "A2", pipe="CUBE", cycles=10),
        Node(2, "B", pipe="VECTOR", cycles=10),
        Node(3, "B2", pipe="VECTOR", cycles=10),
        Node(4, "LATE_VECTOR", pipe="VECTOR", cycles=100),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (2, 3)])
    base = (0, 2, 1, 3, 4)
    critical = schedule_priority_window(graph, base, window=2, policy="critical")
    pipe = schedule_priority_window(graph, base, window=2, policy="pipe_remaining")
    assert critical.order[0] == 0
    assert pipe.order[0] == 2
    assert pipe.evaluation.valid


def test_unlock_policy_prefers_immediate_unlock_count() -> None:
    nodes = [
        Node(0, "FANOUT", pipe="CUBE", cycles=1),
        Node(1, "LONG", pipe="VECTOR", cycles=100),
        Node(2, "S1", pipe="MTE1", cycles=1),
        Node(3, "S2", pipe="MTE2", cycles=1),
        Node(4, "TAIL", pipe="VECTOR", cycles=1),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 2), (0, 3), (1, 4)])
    base = (1, 0, 2, 3, 4)
    result = schedule_priority_window(graph, base, window=5, policy="unlock")
    assert result.order[0] == 0
    assert result.evaluation.valid


def test_l0_single_residency_order_is_preserved() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L0A"),
        Node(1, "SHORT", pipe="CUBE", cycles=1, bufs=(0,)),
        Node(2, "FREE", 0, 4, "L0A"),
        Node(3, "ALLOC", 1, 4, "L0A"),
        Node(4, "LONG", pipe="VECTOR", cycles=100, bufs=(1,)),
        Node(5, "FREE", 1, 4, "L0A"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [(0, 1), (1, 2), (3, 4), (4, 5)],
    )
    base = (0, 1, 2, 3, 4, 5)
    for policy in PRIORITY_POLICIES:
        result = schedule_priority_window(graph, base, window=100, policy=policy)
        pos = {node_id: i for i, node_id in enumerate(result.order)}
        assert pos[2] < pos[3]
        assert result.evaluation.valid
