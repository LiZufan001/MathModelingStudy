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
from q3_conv_local_recolor import (
    OfficialFastContext,
    candidate_initial_offsets,
    critical_reuse_targets,
    move_initial_offset,
    search_q3_critical_recolor,
)
from q3_evaluator import evaluate_q3_solution


def _two_independent_buffers(shared_offset: bool = True) -> tuple[ComputeGraph, Q2Solution]:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L1"),
        Node(1, "A", pipe="CUBE", cycles=100, bufs=(0,)),
        Node(2, "FREE", 0, 4, "L1"),
        Node(3, "ALLOC", 1, 4, "L1"),
        Node(4, "B", pipe="VECTOR", cycles=100, bufs=(1,)),
        Node(5, "FREE", 1, 4, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [(0, 1), (1, 2), (3, 4), (4, 5)],
    )
    solution = Q2Solution(
        schedule=(0, 1, 2, 3, 4, 5),
        initial_offsets={0: 0, 1: 0 if shared_offset else 4},
        spills=(),
    )
    validate_q2_solution(graph, solution).require_ok()
    return graph, solution


def test_critical_reuse_target_and_low_pressure_candidate() -> None:
    graph, solution = _two_independent_buffers(shared_offset=True)
    official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    official.require_ok()
    assert official.total_cycles == 200
    assert critical_reuse_targets(graph, solution, max_targets=4) == (1,)
    starts = candidate_initial_offsets(graph, solution, 1, max_starts=4)
    assert 0 not in starts
    assert any(start >= 4 for start in starts)


def test_cached_official_score_matches_full_evaluator() -> None:
    graph, solution = _two_independent_buffers(shared_offset=True)
    context = OfficialFastContext.build(graph, solution)

    baseline_fast = context.score(graph, solution)
    baseline_full = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_full.require_ok()
    assert baseline_fast.total_cycles == baseline_full.total_cycles == 200
    assert baseline_fast.reuse_edge_count == baseline_full.reuse_edge_count == 1

    moved = move_initial_offset(solution, 1, 4)
    validate_q2_solution(graph, moved).require_ok()
    moved_fast = context.score(graph, moved)
    moved_full = evaluate_q3_solution(graph, moved, reuse_mode="official_literal")
    moved_full.require_ok()
    assert moved_fast.total_cycles == moved_full.total_cycles == 100
    assert moved_fast.reuse_edge_count == moved_full.reuse_edge_count == 0


def test_local_recolor_removes_critical_reuse_serialization() -> None:
    graph, solution = _two_independent_buffers(shared_offset=True)
    result = search_q3_critical_recolor(
        graph,
        solution,
        max_targets=2,
        max_starts=4,
    )
    assert result.improved
    assert result.baseline_official.total_cycles == 200
    assert result.best_official.total_cycles == 100
    assert result.best_safe.total_cycles == 100
    assert result.best_solution.initial_offsets[1] != 0
    validate_q2_solution(graph, result.best_solution).require_ok()


def test_no_reuse_bottleneck_produces_no_move() -> None:
    graph, solution = _two_independent_buffers(shared_offset=False)
    result = search_q3_critical_recolor(
        graph,
        solution,
        max_targets=2,
        max_starts=4,
    )
    assert result.target_buffers == ()
    assert not result.improved
    assert result.best_solution == solution
