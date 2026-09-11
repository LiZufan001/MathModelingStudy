from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution
from q3_reallocator import repack_q3_addresses


def _two_sequential_independent_buffers() -> tuple[ComputeGraph, Q2Solution]:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L1"),
        Node(1, "USE_A", pipe="CUBE", cycles=10, bufs=(0,)),
        Node(2, "FREE", 0, 4, "L1"),
        Node(3, "ALLOC", 1, 4, "L1"),
        Node(4, "USE_B", pipe="VECTOR", cycles=20, bufs=(1,)),
        Node(5, "FREE", 1, 4, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (1, 2), (3, 4), (4, 5)])
    return graph, Q2Solution(tuple(range(6)), {0: 0, 1: 0}, ())


def test_next_fit_can_remove_unnecessary_address_reuse_serialization() -> None:
    graph, solution = _two_sequential_independent_buffers()
    baseline = evaluate_q3_solution(graph, solution)
    baseline.require_ok()
    assert baseline.total_cycles == 30

    repacked = repack_q3_addresses(graph, solution, "next_fit").solution
    validate_q2_solution(graph, repacked).require_ok()
    assert repacked.initial_offsets == {0: 0, 1: 4}

    timing = evaluate_q3_solution(graph, repacked)
    timing.require_ok()
    assert timing.total_cycles == 20
    assert timing.reuse_edge_count == 0


def test_all_address_policies_preserve_q2_spill_and_traffic_on_no_spill_case() -> None:
    graph, solution = _two_sequential_independent_buffers()
    original = validate_q2_solution(graph, solution)
    original.require_ok()
    for policy in ("best_fit", "first_fit_low", "first_fit_high", "next_fit"):
        repacked = repack_q3_addresses(graph, solution, policy).solution
        replay = validate_q2_solution(graph, repacked)
        replay.require_ok()
        assert replay.spill_count == original.spill_count == 0
        assert replay.extra_traffic == original.extra_traffic == 0
