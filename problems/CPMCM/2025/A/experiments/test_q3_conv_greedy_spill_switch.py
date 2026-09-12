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
from q3_conv_greedy_spill_switch import optimize_q3_critical_spill_switch_greedy


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


def test_greedy_critical_spill_switch_stops_after_saturation() -> None:
    graph, solution = _fixture()
    result = optimize_q3_critical_spill_switch_greedy(
        graph,
        solution,
        max_rounds=3,
        max_switches=4,
    )
    assert result.improved
    assert result.accepted_rounds == 1
    assert result.final_official.total_cycles == 404
    assert result.final_safe.ok
    assert len(result.rounds) == 2
    assert result.rounds[0].improved
    assert not result.rounds[1].improved
    final_q2 = validate_q2_solution(graph, result.final_solution)
    final_q2.require_ok()
    assert final_q2.spill_count == 1
    assert result.final_solution.spills == solution.spills
