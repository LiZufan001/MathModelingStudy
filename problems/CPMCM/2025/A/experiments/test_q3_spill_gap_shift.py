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
from q3_evaluator import evaluate_q3_solution
from q3_spill_gap_shift import search_q3_critical_spill_gap_shifts


def _spill_gap_fixture() -> tuple[ComputeGraph, Q2Solution]:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L1"),
        Node(1, "USE_A", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(2, "USE_B", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(3, "DOWNSTREAM", pipe="CUBE", cycles=500),
        Node(4, "FREE", 0, 4, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (1, 2), (2, 3), (3, 4)])
    # N=5 -> spill 0 is OUT=5, IN=6. Initially the transfer lies between
    # USE_A and USE_B, so the 316-cycle round trip serializes the 500-cycle
    # downstream chain. Moving the same spill pair to the USE_B/FREE gap lets
    # the transfer overlap DOWNSTREAM without changing traffic or spill records.
    solution = Q2Solution(
        schedule=(0, 1, 5, 6, 2, 3, 4),
        initial_offsets={0: 0},
        spills=(SpillRecord(0, 0),),
    )
    validate_q2_solution(graph, solution).require_ok()
    return graph, solution


def test_spill_gap_shift_moves_same_record_and_improves_overlap() -> None:
    graph, solution = _spill_gap_fixture()
    baseline = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline.require_ok()
    assert baseline.total_cycles == 818

    result = search_q3_critical_spill_gap_shifts(
        graph,
        solution,
        max_spills=4,
        gap_radius=1,
    )
    assert result.improved
    assert result.best_official.total_cycles == 502
    assert result.best_safe.ok
    assert result.best_shift == (0, 2)
    assert result.best_solution.spills == solution.spills
    final_q2 = validate_q2_solution(graph, result.best_solution)
    final_q2.require_ok()
    base_q2 = validate_q2_solution(graph, solution)
    assert final_q2.extra_traffic == base_q2.extra_traffic == 8
    assert final_q2.spill_count == base_q2.spill_count == 1
