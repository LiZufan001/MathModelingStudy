from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution
from q3_pipeline_scheduler import reschedule_q3_critical


def test_critical_reschedule_improves_bad_same_pipe_order_without_changing_q2() -> None:
    # Two independent chains. The submitted order puts long B before short A on
    # CUBE, delaying A's long VECTOR successor. Critical-bottom-level ordering
    # chooses A first and exposes CUBE/VECTOR overlap. The exact lower bound is
    # 202 here: VECTOR has 201 busy cycles and cannot start before A finishes at t=1.
    nodes = [
        Node(0, "A", pipe="CUBE", cycles=1),
        Node(1, "X", pipe="VECTOR", cycles=200),
        Node(2, "B", pipe="CUBE", cycles=100),
        Node(3, "Y", pipe="VECTOR", cycles=1),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (2, 3)])
    original = Q2Solution((2, 0, 1, 3), {}, ())
    original_timing = evaluate_q3_solution(graph, original)
    original_timing.require_ok()
    assert original_timing.total_cycles == 302

    result = reschedule_q3_critical(graph, original)
    validate_q2_solution(graph, result.solution).require_ok()
    assert result.solution.schedule[0] == 0
    assert result.timing.total_cycles == 202
    assert result.changed_positions > 0


def test_critical_reschedule_preserves_address_reuse_order() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L1"),
        Node(1, "USE_A", pipe="CUBE", cycles=10, bufs=(0,)),
        Node(2, "FREE", 0, 4, "L1"),
        Node(3, "ALLOC", 1, 4, "L1"),
        Node(4, "USE_B", pipe="VECTOR", cycles=20, bufs=(1,)),
        Node(5, "FREE", 1, 4, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (1, 2), (3, 4), (4, 5)])
    solution = Q2Solution(tuple(range(6)), {0: 0, 1: 0}, ())
    result = reschedule_q3_critical(graph, solution)
    result.timing.require_ok()
    assert result.solution.schedule.index(2) < result.solution.schedule.index(3)
    assert result.timing.total_cycles == 30
