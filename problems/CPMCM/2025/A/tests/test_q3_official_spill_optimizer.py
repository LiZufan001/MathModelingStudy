from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_model import Q2Solution, SpillRecord
from q2_validator import validate_q2_solution
from q3_official_optimizer import optimize_q3_official_zero_traffic
from q3_official_spill_optimizer import optimize_q3_official_with_spill_batches


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


def test_disabled_spill_batch_matches_stable_core() -> None:
    graph, solution = _fixture()
    core = optimize_q3_official_zero_traffic(graph, solution, max_rounds=2)
    wrapped = optimize_q3_official_with_spill_batches(
        graph,
        solution,
        max_rounds=2,
        spill_batch_max_rounds=0,
    )
    assert wrapped.spill_batches is None
    assert wrapped.solution == core.solution
    assert wrapped.official_timing.total_cycles == core.official_timing.total_cycles
    assert wrapped.safe_timing.total_cycles == core.safe_timing.total_cycles
    assert wrapped.spill_count == core.spill_count
    assert wrapped.extra_traffic == core.extra_traffic


def test_enabled_spill_batch_is_monotone_and_keeps_exact_spills() -> None:
    graph, solution = _fixture()
    result = optimize_q3_official_with_spill_batches(
        graph,
        solution,
        max_rounds=2,
        spill_batch_max_rounds=4,
        spill_batch_max_switches=4,
        spill_batch_prefix_sizes=(1, 2, 4),
    )
    assert result.spill_batches is not None
    assert result.official_timing.total_cycles <= result.core.official_timing.total_cycles
    assert result.solution.spills == solution.spills
    final_q2 = validate_q2_solution(graph, result.solution)
    final_q2.require_ok()
    assert final_q2.spill_count == validate_q2_solution(graph, solution).spill_count
    assert final_q2.extra_traffic == validate_q2_solution(graph, solution).extra_traffic
