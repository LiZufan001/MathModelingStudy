from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q1_advanced import schedule_q1_pressure
from q1_exact import solve_q1_exact
from q1_scheduler import schedule_q1_baseline


def strategic_l0_graph() -> ComputeGraph:
    # Buffer P (100) is live first. Choosing L0 buffer A first forces X (80) to
    # overlap P, while choosing L0 buffer B first unlocks FREE(P) before X is allocated.
    nodes = [
        Node(0, "ALLOC", 0, 100, "L1"),      # P
        Node(1, "ALLOC", 1, 8, "L0A"),       # A: baseline chooses this by id
        Node(2, "ALLOC", 2, 8, "L0A"),       # B: strategically better
        Node(3, "ALLOC", 3, 80, "L1"),       # X
        Node(4, "FREE", 1, 8, "L0A"),
        Node(5, "FREE", 0, 100, "L1"),
        Node(6, "FREE", 2, 8, "L0A"),
        Node(7, "FREE", 3, 80, "L1"),
    ]
    edges = [
        (0, 1), (0, 2),
        (1, 3), (3, 4), (3, 7),
        (2, 5), (5, 6),
    ]
    return ComputeGraph.from_edges(nodes, edges)


def l0_deadlock_trap_graph() -> ComputeGraph:
    # If A is allocated first, FREE(A) cannot become ready until B is allocated,
    # but B cannot be allocated while A occupies L0A. B-first is feasible.
    nodes = [
        Node(0, "ALLOC", 0, 8, "L0A"),
        Node(1, "ALLOC", 1, 8, "L0A"),
        Node(2, "FREE", 0, 8, "L0A"),
        Node(3, "FREE", 1, 8, "L0A"),
    ]
    edges = [(0, 2), (1, 2), (1, 3)]
    return ComputeGraph.from_edges(nodes, edges)


def test_exact_solver_proves_strategic_l0_optimum() -> None:
    graph = strategic_l0_graph()
    exact = solve_q1_exact(graph)
    assert exact.evaluation.valid
    assert exact.evaluation.peak_residency == 100
    assert exact.explored_states > 0


def test_pressure_matches_exact_and_beats_baseline_on_strategic_l0_choice() -> None:
    graph = strategic_l0_graph()
    baseline = schedule_q1_baseline(graph)
    pressure = schedule_q1_pressure(graph)
    exact = solve_q1_exact(graph)

    assert baseline.evaluation.peak_residency == 180
    assert pressure.evaluation.peak_residency == 100
    assert pressure.evaluation.peak_residency == exact.evaluation.peak_residency
    assert pressure.order.index(2) < pressure.order.index(1)


def test_exact_and_pressure_escape_l0_deadlock_trap() -> None:
    graph = l0_deadlock_trap_graph()
    with pytest.raises(ValueError, match="unschedulable|no Q1-feasible"):
        schedule_q1_baseline(graph)

    pressure = schedule_q1_pressure(graph)
    exact = solve_q1_exact(graph)
    assert pressure.evaluation.valid
    assert exact.evaluation.valid
    assert pressure.order[0] == 1
    assert exact.evaluation.peak_residency == 0


def test_exact_solver_has_explicit_size_guard() -> None:
    graph = ComputeGraph.from_edges([Node(i, "OP") for i in range(19)], [])
    with pytest.raises(ValueError, match="limited to 18 nodes"):
        solve_q1_exact(graph)
