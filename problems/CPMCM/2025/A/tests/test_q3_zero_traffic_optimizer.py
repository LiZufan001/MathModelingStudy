from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_zero_traffic_optimizer import optimize_q3_zero_traffic


def test_zero_traffic_optimizer_is_monotone_and_preserves_q2_metrics() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L1"),
        Node(1, "A", pipe="CUBE", cycles=1, bufs=(0,)),
        Node(2, "X", pipe="VECTOR", cycles=200, bufs=(0,)),
        Node(3, "FREE", 0, 4, "L1"),
        Node(4, "ALLOC", 1, 4, "L1"),
        Node(5, "B", pipe="CUBE", cycles=100, bufs=(1,)),
        Node(6, "Y", pipe="VECTOR", cycles=1, bufs=(1,)),
        Node(7, "FREE", 1, 4, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [(0, 1), (1, 2), (2, 3), (4, 5), (5, 6), (6, 7)],
    )
    # The two buffers are simultaneously live in this legal Q2 order, so they
    # deliberately use disjoint physical ranges.  The slow part is only the
    # submitted same-pipe order: long CUBE B runs before short CUBE A, delaying
    # A's long VECTOR successor.  This gives the zero-traffic optimizer a real
    # Q3 improvement opportunity without smuggling an invalid Q2 overlap into
    # the fixture.
    solution = Q2Solution((4, 5, 0, 1, 2, 3, 6, 7), {0: 0, 1: 4}, ())
    before = validate_q2_solution(graph, solution)
    before.require_ok()

    result = optimize_q3_zero_traffic(graph, solution, max_rounds=2)
    after = validate_q2_solution(graph, result.solution)
    after.require_ok()
    assert result.timing.total_cycles <= result.original_cycles
    assert after.spill_count == before.spill_count == 0
    assert after.extra_traffic == before.extra_traffic == 0
    accepted = [step for step in result.steps if step.accepted]
    assert accepted
    assert all(
        step.cycles_after is not None and step.cycles_after < step.cycles_before
        for step in accepted
    )
