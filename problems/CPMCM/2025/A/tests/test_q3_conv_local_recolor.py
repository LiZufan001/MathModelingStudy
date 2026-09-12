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


def _four_serial_buffers() -> tuple[ComputeGraph, Q2Solution]:
    sizes = (4, 3, 5, 2)
    nodes: list[Node] = []
    edges: list[tuple[int, int]] = []
    for buf_id, size in enumerate(sizes):
        alloc_id = 3 * buf_id
        use_id = alloc_id + 1
        free_id = alloc_id + 2
        nodes.extend(
            [
                Node(alloc_id, "ALLOC", buf_id, size, "L1"),
                Node(use_id, f"USE_{buf_id}", pipe=f"P{buf_id}", cycles=10 + buf_id, bufs=(buf_id,)),
                Node(free_id, "FREE", buf_id, size, "L1"),
            ]
        )
        edges.extend([(alloc_id, use_id), (use_id, free_id)])
    graph = ComputeGraph.from_edges(nodes, edges)
    solution = Q2Solution(
        schedule=tuple(range(len(nodes))),
        initial_offsets={0: 0, 1: 2, 2: 5, 3: 1},
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


def test_incremental_single_move_matches_exact_replay_over_many_offsets() -> None:
    graph, solution = _four_serial_buffers()
    context = OfficialFastContext.build(graph, solution)

    for buf_id in range(4):
        alloc = graph.alloc_node_for_buffer(buf_id)
        assert alloc is not None and alloc.size is not None
        for new_offset in range(0, 12 - alloc.size + 1):
            moved = move_initial_offset(solution, buf_id, new_offset)
            validate_q2_solution(graph, moved).require_ok()
            fast = context.score(graph, moved)
            exact = evaluate_q3_solution(graph, moved, reuse_mode="official_literal")
            exact.require_ok()
            assert fast.total_cycles == exact.total_cycles, (buf_id, new_offset)
            assert fast.reuse_edge_count == exact.reuse_edge_count, (buf_id, new_offset)


def test_multiple_moves_fall_back_to_exact_replay() -> None:
    graph, solution = _four_serial_buffers()
    context = OfficialFastContext.build(graph, solution)
    moved = move_initial_offset(solution, 1, 7)
    moved = move_initial_offset(moved, 2, 0)
    validate_q2_solution(graph, moved).require_ok()
    fast = context.score(graph, moved)
    exact = evaluate_q3_solution(graph, moved, reuse_mode="official_literal")
    exact.require_ok()
    assert fast.total_cycles == exact.total_cycles
    assert fast.reuse_edge_count == exact.reuse_edge_count


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
