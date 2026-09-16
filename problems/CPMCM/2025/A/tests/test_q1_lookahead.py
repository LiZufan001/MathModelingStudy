from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q1_exact import solve_q1_exact
from q1_frontier import schedule_q1_frontier
from q1_lookahead import schedule_q1_lookahead
from q1_scheduler import schedule_q1_baseline


def two_step_alloc_fork_graph() -> ComputeGraph:
    # After node 1, Y(10) and X(80) become ready in the same epoch. Static policies
    # prefer smaller Y. But Y cannot be freed until X runs; X can immediately free
    # the already-live P(100). Thus:
    #   Y -> X: peak = 100 + 10 + 80 = 190
    #   X -> FREE(P) -> Y: peak = max(180, 90) = 180
    # The exact solver proves 180 is globally optimal.
    nodes = [
        Node(0, "ALLOC", 0, 100, "L1"),
        Node(1, "OP", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(2, "ALLOC", 1, 10, "UB"),
        Node(3, "ALLOC", 2, 80, "L1"),
        Node(4, "FREE", 0, 100, "L1"),
        Node(5, "FREE", 1, 10, "UB"),
        Node(6, "FREE", 2, 80, "L1"),
    ]
    edges = [
        (0, 1),
        (1, 2), (1, 3),
        (3, 4),
        (2, 5), (3, 5),
        (3, 6),
    ]
    return ComputeGraph.from_edges(nodes, edges)


def test_two_step_lookahead_matches_exact_when_static_greedies_fail() -> None:
    graph = two_step_alloc_fork_graph()
    baseline = schedule_q1_baseline(graph)
    frontier = schedule_q1_frontier(graph)
    lookahead = schedule_q1_lookahead(
        graph,
        depth=2,
        candidate_limit=4,
        rollout_horizon=32,
        trigger_ratio=0.0,
    )
    exact = solve_q1_exact(graph)

    assert baseline.evaluation.peak_residency == 190
    assert frontier.evaluation.peak_residency == 190
    assert lookahead.evaluation.valid
    assert lookahead.evaluation.peak_residency == 180
    assert exact.evaluation.peak_residency == 180
    assert lookahead.order.index(3) < lookahead.order.index(2)
    assert lookahead.lookahead_decisions >= 1


def test_lookahead_preserves_l0_deadlock_safety() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 8, "L0A"),
        Node(1, "ALLOC", 1, 8, "L0A"),
        Node(2, "OP", pipe="VECTOR", cycles=1),
        Node(3, "FREE", 0, 8, "L0A"),
        Node(4, "FREE", 1, 8, "L0A"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 3), (1, 2), (2, 3), (1, 4)])
    result = schedule_q1_lookahead(graph, trigger_ratio=0.0)
    assert result.evaluation.valid
    assert result.order[0] == 1


def test_lookahead_recomputes_incremental_peak_with_independent_evaluator() -> None:
    graph = two_step_alloc_fork_graph()
    result = schedule_q1_lookahead(graph, trigger_ratio=0.0)
    assert result.evaluation.valid
    assert result.evaluation.peak_residency == 180
