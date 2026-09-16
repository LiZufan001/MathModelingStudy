from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_model import Q2Solution, SpillRecord
from q3_evaluator import evaluate_q3_both, evaluate_q3_solution


def test_independent_different_pipes_overlap() -> None:
    graph = ComputeGraph.from_edges(
        [
            Node(0, "CUBE_OP", pipe="CUBE", cycles=10),
            Node(1, "VECTOR_OP", pipe="VECTOR", cycles=20),
        ],
        [],
    )
    result = evaluate_q3_solution(graph, Q2Solution((0, 1), {}, ()))
    result.require_ok()
    assert result.total_cycles == 20
    assert result.start_times == {0: 0, 1: 0}
    assert result.pipe_busy_cycles == {"CUBE": 10, "VECTOR": 20}


def test_same_pipe_is_serialized_in_submitted_order() -> None:
    graph = ComputeGraph.from_edges(
        [
            Node(0, "A", pipe="CUBE", cycles=10),
            Node(1, "B", pipe="CUBE", cycles=20),
        ],
        [],
    )
    result = evaluate_q3_solution(graph, Q2Solution((0, 1), {}, ()))
    result.require_ok()
    assert result.start_times[1] == 10
    assert result.finish_times[1] == 30
    assert result.total_cycles == 30
    assert result.pipe_edge_count == 1


def test_cross_pipe_dependency_prevents_false_parallelism() -> None:
    graph = ComputeGraph.from_edges(
        [
            Node(0, "A", pipe="CUBE", cycles=10),
            Node(1, "B", pipe="VECTOR", cycles=20),
        ],
        [(0, 1)],
    )
    result = evaluate_q3_solution(graph, Q2Solution((0, 1), {}, ()))
    result.require_ok()
    assert result.start_times[1] == 10
    assert result.total_cycles == 30


def test_free_to_alloc_address_reuse_dependency_serializes_epochs() -> None:
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
    result = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    result.require_ok()
    assert result.reuse_edge_count == 1
    assert result.start_times[3] == 10
    assert result.total_cycles == 30


def test_copy_in_backed_spill_cycles_are_used_in_timing() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L1"),
        Node(1, "COPY_IN", pipe="MTE2", cycles=10, bufs=(0,)),
        Node(2, "USE", pipe="VECTOR", cycles=5, bufs=(0,)),
        Node(3, "FREE", 0, 4, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (1, 2), (2, 3)])
    # N=4 -> SPILL_OUT=4, SPILL_IN=5. Size=4 gives SPILL_IN 2*4+150=158;
    # COPY_IN-backed data makes SPILL_OUT cost 0 cycles.
    solution = Q2Solution((0, 1, 4, 5, 2, 3), {0: 0}, (SpillRecord(0, 0),))
    result = evaluate_q3_solution(graph, solution)
    result.require_ok()
    assert result.start_times[4] == 10
    assert result.finish_times[4] == 10
    assert result.start_times[5] == 10
    assert result.finish_times[5] == 168
    assert result.total_cycles == 173


def test_residency_safe_mode_catches_spill_reuse_missing_from_literal_rule() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L1"),
        Node(1, "COPY_IN", pipe="MTE2", cycles=10, bufs=(0,)),
        Node(2, "USE_A_LATE", pipe="VECTOR", cycles=5, bufs=(0,)),
        Node(3, "FREE", 0, 4, "L1"),
        Node(4, "ALLOC", 1, 4, "L1"),
        Node(5, "USE_B", pipe="CUBE", cycles=20, bufs=(1,)),
        Node(6, "FREE", 1, 4, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [(0, 1), (1, 2), (2, 3), (4, 5), (5, 6)],
    )
    # Spill A, reuse its address for B in schedule order, free B, then reload A.
    # N=7 -> OUT=7, IN=8.
    solution = Q2Solution(
        (0, 1, 7, 4, 5, 6, 8, 2, 3),
        {0: 0, 1: 0},
        (SpillRecord(0, 0),),
    )
    result = evaluate_q3_both(graph, solution)
    result.official_literal.require_ok()
    result.residency_safe.require_ok()

    assert result.official_literal.total_cycles == 173
    assert result.official_literal.physical_overlap_errors
    assert result.residency_safe.total_cycles == 193
    assert result.residency_safe.physical_overlap_errors == ()
    assert result.residency_safe.reuse_edge_count > result.official_literal.reuse_edge_count


def test_residency_safe_repeated_spill_serializes_reload_before_next_release() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L1"),
        Node(1, "COPY_IN", pipe="MTE2", cycles=10, bufs=(0,)),
        Node(2, "USE_LATE", pipe="VECTOR", cycles=5, bufs=(0,)),
        Node(3, "FREE", 0, 4, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (1, 2), (2, 3)])
    # N=4: spill0 OUT/IN = 4/5, spill1 OUT/IN = 6/7.  There is no
    # business use between IN(5) and OUT(6), so residency safety itself must
    # preserve the middle epoch's acquire->release lifetime.
    solution = Q2Solution(
        (0, 1, 4, 5, 6, 7, 2, 3),
        {0: 0},
        (SpillRecord(0, 0), SpillRecord(0, 0)),
    )
    result = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    result.require_ok()
    assert result.physical_overlap_errors == ()
    assert result.start_times[6] >= result.finish_times[5]
    assert result.start_times[7] >= result.finish_times[6]


def test_residency_safe_zero_duration_epoch_has_no_phantom_owner() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L1"),
        Node(1, "FREE", 0, 4, "L1"),
        Node(2, "ALLOC", 1, 4, "L1"),
        Node(3, "USE_B", pipe="CUBE", cycles=10, bufs=(1,)),
        Node(4, "FREE", 1, 4, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(2, 3), (3, 4)])
    solution = Q2Solution((0, 1, 2, 3, 4), {0: 0, 1: 0}, ())
    result = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    result.require_ok()
    assert result.total_cycles == 10
    assert result.start_times[0] == result.finish_times[1] == result.start_times[2] == 0
    assert result.physical_overlap_errors == ()
