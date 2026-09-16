from __future__ import annotations

import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution
from q3_priority_rescheduler import search_q3_priority_reschedule_portfolio


def _priority_fixture() -> tuple[ComputeGraph, Q2Solution]:
    nodes = [
        Node(0, "SHORT_UNLOCK", pipe="VECTOR", cycles=1),
        Node(1, "LONG_DISTRACTOR", pipe="VECTOR", cycles=100),
        Node(2, "DOWNSTREAM", pipe="CUBE", cycles=100),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 2)])
    # Same-pipe order 1 -> 0 delays the long downstream chain. A bottom-level
    # priority should put node 0 first while keeping the DAG valid.
    solution = Q2Solution((1, 0, 2), {}, ())
    validate_q2_solution(graph, solution).require_ok()
    return graph, solution


def test_priority_portfolio_improves_independent_same_pipe_order() -> None:
    graph, solution = _priority_fixture()
    baseline = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline.require_ok()
    assert baseline.total_cycles == 201

    result = search_q3_priority_reschedule_portfolio(graph, solution)
    assert result.improved
    assert result.best_official.total_cycles == 101
    assert result.best_safe.ok
    assert result.best_policy != "baseline"
    final_q2 = validate_q2_solution(graph, result.best_solution)
    final_q2.require_ok()
    assert final_q2.extra_traffic == 0
    assert final_q2.spill_count == 0
