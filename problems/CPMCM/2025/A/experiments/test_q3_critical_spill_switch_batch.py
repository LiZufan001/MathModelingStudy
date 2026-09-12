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
from q3_critical_spill_switch_batch import search_q3_critical_spill_out_batches


def _fixture() -> tuple[ComputeGraph, Q2Solution]:
    nodes = [
        Node(0, "ALLOC", 0, 1, "L1"),
        Node(1, "MTE3_DISTRACTOR", pipe="MTE3", cycles=100),
        Node(2, "MTE2_DISTRACTOR", pipe="MTE2", cycles=100),
        Node(3, "FREE", 0, 1, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [])
    solution = Q2Solution(
        schedule=(0, 1, 4, 5, 2, 3),
        initial_offsets={0: 0},
        spills=(SpillRecord(0, 0),),
    )
    validate_q2_solution(graph, solution).require_ok()
    return graph, solution


def test_batch_out_bubble_keeps_strict_invariants() -> None:
    graph, solution = _fixture()
    result = search_q3_critical_spill_out_batches(
        graph,
        solution,
        max_switches=4,
        prefix_sizes=(1, 2, 4),
    )
    assert result.improved
    assert result.best_prefix_size == 1
    assert result.best_official.total_cycles == 404
    assert result.best_safe.ok
    final_q2 = validate_q2_solution(graph, result.best_solution)
    final_q2.require_ok()
    assert final_q2.spill_count == 1
    assert result.best_solution.spills == solution.spills
