from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q1_exact import solve_q1_exact
from q1_frontier import schedule_q1_frontier
from q1_scheduler import schedule_q1_baseline


def frontier_advantage_graph() -> ComputeGraph:
    # P is forced live first. Node 1 unlocks an old small allocation Y; node 2 then
    # unlocks a newer larger allocation X that immediately enables FREE(P). The
    # baseline chooses smaller Y first (peak 190), while frontier continuity chooses X
    # first, frees P, then opens Y (peak 180).
    nodes = [
        Node(0, "ALLOC", 0, 100, "L1"),       # P
        Node(1, "OP", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(2, "OP", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(3, "ALLOC", 1, 10, "UB"),        # Y, becomes ready earlier
        Node(4, "ALLOC", 2, 80, "L1"),        # X, becomes ready later
        Node(5, "FREE", 0, 100, "L1"),
        Node(6, "FREE", 1, 10, "UB"),
        Node(7, "FREE", 2, 80, "L1"),
    ]
    edges = [
        (0, 1), (0, 2),
        (1, 3),
        (2, 4),
        (4, 5),
        (3, 6), (4, 6),
        (4, 7),
    ]
    return ComputeGraph.from_edges(nodes, edges)


def test_frontier_matches_exact_and_beats_smallest_alloc_baseline() -> None:
    graph = frontier_advantage_graph()
    baseline = schedule_q1_baseline(graph)
    frontier = schedule_q1_frontier(graph)
    exact = solve_q1_exact(graph)

    assert baseline.evaluation.valid
    assert frontier.evaluation.valid
    assert exact.evaluation.valid
    assert baseline.evaluation.peak_residency == 190
    assert frontier.evaluation.peak_residency == 180
    assert exact.evaluation.peak_residency == 180
    assert frontier.order.index(4) < frontier.order.index(3)


def test_frontier_keeps_l0_deadlock_safety() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 8, "L0A"),
        Node(1, "ALLOC", 1, 8, "L0A"),
        Node(2, "OP", pipe="VECTOR", cycles=1),
        Node(3, "FREE", 0, 8, "L0A"),
        Node(4, "FREE", 1, 8, "L0A"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 3), (1, 2), (2, 3), (1, 4)])
    result = schedule_q1_frontier(graph)
    assert result.evaluation.valid
    assert result.order[0] == 1
