from __future__ import annotations

import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_model import Q2Solution, SpillRecord
from q2_validator import validate_q2_solution
from q3_critical_spill_switch import (
    critical_spill_switch_candidates,
    search_q3_critical_spill_switch_bubbles,
)
from q3_evaluator import evaluate_q3_solution


def _spill_switch_fixture() -> tuple[ComputeGraph, Q2Solution]:
    nodes = [
        Node(0, "ALLOC", 0, 1, "L1"),
        Node(1, "MTE3_DISTRACTOR", pipe="MTE3", cycles=100),
        Node(2, "MTE2_DISTRACTOR", pipe="MTE2", cycles=100),
        Node(3, "FREE", 0, 1, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [])
    # N=4, so spill 0 is OUT=4 / IN=5.  The submitted pipe order makes
    # MTE3_DISTRACTOR -> OUT -> IN -> MTE2_DISTRACTOR one 504-cycle critical
    # chain.  Bubbling OUT one MTE3 slot earlier preserves the spill and Q2
    # traffic but overlaps the distractor with the MTE2 side of the chain.
    solution = Q2Solution(
        schedule=(0, 1, 4, 5, 2, 3),
        initial_offsets={0: 0},
        spills=(SpillRecord(0, 0),),
    )
    validate_q2_solution(graph, solution).require_ok()
    return graph, solution


def test_critical_spill_switch_targets_long_cross_pipe_chain() -> None:
    graph, solution = _spill_switch_fixture()
    baseline = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline.require_ok()
    assert baseline.total_cycles == 504
    assert baseline.critical_path == (1, 4, 5, 2)

    candidates = critical_spill_switch_candidates(
        graph,
        solution,
        baseline,
        max_switches=4,
    )
    assert len(candidates) == 1
    assert candidates[0].spill_index == 0
    assert candidates[0].out_id == 4
    assert candidates[0].in_id == 5
    assert candidates[0].left_run_cycles == 252
    assert candidates[0].right_run_cycles == 252

    result = search_q3_critical_spill_switch_bubbles(
        graph,
        solution,
        max_switches=4,
        baseline_official=baseline,
    )
    assert result.improved
    assert result.best_move == (0, "out_earlier")
    assert result.best_official.total_cycles == 404
    assert result.best_safe.ok
    assert result.best_solution.spills == solution.spills

    final_q2 = validate_q2_solution(graph, result.best_solution)
    final_q2.require_ok()
    assert final_q2.extra_traffic == validate_q2_solution(graph, solution).extra_traffic
    assert final_q2.spill_count == 1
