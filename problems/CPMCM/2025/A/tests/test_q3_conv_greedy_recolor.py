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
from q3_conv_greedy_recolor import optimize_q3_critical_recolor_greedy


def _three_independent_buffers() -> tuple[ComputeGraph, Q2Solution]:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L1"),
        Node(1, "A", pipe="CUBE", cycles=100, bufs=(0,)),
        Node(2, "FREE", 0, 4, "L1"),
        Node(3, "ALLOC", 1, 4, "L1"),
        Node(4, "B", pipe="VECTOR", cycles=100, bufs=(1,)),
        Node(5, "FREE", 1, 4, "L1"),
        Node(6, "ALLOC", 2, 4, "L1"),
        Node(7, "C", pipe="MTE2", cycles=100, bufs=(2,)),
        Node(8, "FREE", 2, 4, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [
            (0, 1), (1, 2),
            (3, 4), (4, 5),
            (6, 7), (7, 8),
        ],
    )
    solution = Q2Solution(
        schedule=(0, 1, 2, 3, 4, 5, 6, 7, 8),
        initial_offsets={0: 0, 1: 0, 2: 0},
        spills=(),
    )
    validate_q2_solution(graph, solution).require_ok()
    return graph, solution


def test_greedy_recolor_composes_two_single_moves() -> None:
    graph, solution = _three_independent_buffers()
    result = optimize_q3_critical_recolor_greedy(
        graph,
        solution,
        max_rounds=3,
        max_targets=1,
        max_starts=4,
    )
    assert result.baseline_official.total_cycles == 300
    assert result.final_official.total_cycles == 100
    assert result.final_safe.total_cycles == 100
    assert result.accepted_rounds == 2
    assert len(result.rounds) == 3
    assert result.rounds[0].best_official.total_cycles == 200
    assert result.rounds[1].best_official.total_cycles == 100
    assert not result.rounds[2].improved
    validate_q2_solution(graph, result.final_solution).require_ok()
