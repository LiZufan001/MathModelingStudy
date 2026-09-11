from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_allocator import AddressPool, allocate_q2_baseline, choose_min_cost_window
from q2_model import Q2Solution, SpillRecord, spill_cycles, spill_traffic_cost
from q2_validator import validate_q2_solution


def _two_buffer_graph() -> ComputeGraph:
    nodes = [
        Node(0, "ALLOC", 0, 6, "L1"),
        Node(1, "ALLOC", 1, 6, "L1"),
        Node(2, "USE", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(3, "USE", pipe="VECTOR", cycles=1, bufs=(1,)),
        Node(4, "FREE", 0, 6, "L1"),
        Node(5, "FREE", 1, 6, "L1"),
    ]
    return ComputeGraph.from_edges(nodes, [(0, 2), (2, 4), (1, 3), (3, 5)])


def test_spill_traffic_and_cycles_follow_appendix_d() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 10, "L1"),
        Node(1, "COPY_IN", pipe="MTE2", cycles=1, bufs=(0,)),
        Node(2, "FREE", 0, 10, "L1"),
        Node(3, "ALLOC", 1, 10, "L1"),
        Node(4, "USE", pipe="VECTOR", cycles=1, bufs=(1,)),
        Node(5, "FREE", 1, 10, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (1, 2), (3, 4), (4, 5)])

    assert spill_traffic_cost(graph, 0) == 10
    assert spill_cycles(graph, 0) == (0, 170)
    assert spill_traffic_cost(graph, 1) == 20
    assert spill_cycles(graph, 1) == (170, 170)


def test_q2_validator_accepts_nonoverlapping_no_spill_solution() -> None:
    graph = _two_buffer_graph()
    solution = Q2Solution(
        schedule=(0, 2, 4, 1, 3, 5),
        initial_offsets={0: 0, 1: 0},
        spills=(),
    )
    result = validate_q2_solution(graph, solution, {"L1": 10})
    assert result.ok, result.errors
    assert result.extra_traffic == 0


def test_q2_validator_rejects_overlapping_live_ranges() -> None:
    graph = _two_buffer_graph()
    solution = Q2Solution(
        schedule=(0, 1, 2, 3, 4, 5),
        initial_offsets={0: 0, 1: 4},
        spills=(),
    )
    result = validate_q2_solution(graph, solution, {"L1": 10})
    assert not result.ok
    assert any("overlaps resident buffer" in error for error in result.errors)


def test_q2_validator_accepts_official_single_spill_pair() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 6, "L1"),
        Node(1, "USE", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(2, "USE", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(3, "FREE", 0, 6, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (1, 2), (2, 3)])
    # N=4 => first official SPILL_OUT/SPILL_IN ids are 4 and 5.
    solution = Q2Solution(
        schedule=(0, 1, 4, 5, 2, 3),
        initial_offsets={0: 0},
        spills=(SpillRecord(0, 0),),
    )
    result = validate_q2_solution(graph, solution, {"L1": 6})
    assert result.ok, result.errors
    assert result.spill_count == 1
    assert result.extra_traffic == 12


def test_q2_validator_rejects_buffer_use_between_spill_out_and_in() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 6, "L1"),
        Node(1, "USE", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(2, "USE", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(3, "FREE", 0, 6, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (1, 2), (2, 3)])
    solution = Q2Solution(
        schedule=(0, 4, 1, 5, 2, 3),
        initial_offsets={0: 0},
        spills=(SpillRecord(0, 0),),
    )
    result = validate_q2_solution(graph, solution, {"L1": 6})
    assert not result.ok
    assert any("spilled out / not resident" in error for error in result.errors)


def test_q2_validator_rejects_wrong_spill_pair_order() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 6, "L1"),
        Node(1, "USE", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(2, "FREE", 0, 6, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (1, 2)])
    # N=3, but IN(4) is placed before OUT(3).
    solution = Q2Solution(
        schedule=(0, 4, 3, 1, 2),
        initial_offsets={0: 0},
        spills=(SpillRecord(0, 0),),
    )
    result = validate_q2_solution(graph, solution, {"L1": 6})
    assert not result.ok
    assert any("must satisfy" in error for error in result.errors)


def _brute_min_window_cost(
    pool: AddressPool,
    size: int,
    traffic_costs: dict[int, int],
    protected: set[int],
) -> int | None:
    best: int | None = None
    for start in range(pool.capacity - size + 1):
        end = start + size
        victims = {
            buf_id
            for used_start, used_end, buf_id in pool.used_intervals()
            if start < used_end and used_start < end
        }
        if protected.intersection(victims):
            continue
        cost = sum(traffic_costs[buf_id] for buf_id in victims)
        best = cost if best is None else min(best, cost)
    return best


def test_min_cost_window_matches_integer_bruteforce() -> None:
    rng = random.Random(20260911)
    for _ in range(250):
        capacity = rng.randint(6, 16)
        pool = AddressPool(capacity)
        next_buf = 0

        # Random valid occupancy; reserve only ranges that are currently free.
        for _attempt in range(30):
            if next_buf >= 6:
                break
            size = rng.randint(1, min(5, capacity))
            start = rng.randint(0, capacity - size)
            if pool.is_range_free(start, size):
                pool.reserve_at(next_buf, start, size)
                next_buf += 1

        costs = {buf_id: rng.randint(1, 30) for _, _, buf_id in pool.used_intervals()}
        distances = {buf_id: rng.randint(1, 50) for buf_id in costs}
        protected = {
            buf_id
            for buf_id in costs
            if rng.random() < 0.2
        }
        request = rng.randint(1, capacity)

        brute = _brute_min_window_cost(pool, request, costs, protected)
        choice = choose_min_cost_window(pool, request, costs, distances, protected)
        assert (choice is None) == (brute is None)
        if choice is not None:
            assert choice.traffic_cost == brute
            assert not protected.intersection(choice.victims)


def test_min_cost_window_prefers_lower_official_traffic() -> None:
    pool = AddressPool(12)
    pool.reserve_at(0, 0, 5)
    pool.reserve_at(1, 7, 5)
    choice = choose_min_cost_window(
        pool,
        size=7,
        traffic_costs={0: 10, 1: 5},
        next_use_distances={0: 100, 1: 1},
    )
    assert choice is not None
    assert choice.victims == (1,)
    assert choice.traffic_cost == 5
    assert choice.start == 5


def test_q2_baseline_forced_spill_is_valid_and_has_expected_cost() -> None:
    # L1 capacity is 10.  Buf0(size=6) remains live while Buf1(size=6) is
    # allocated, so Buf0 must be temporarily spilled.  Buf1 is freed before the
    # second use of Buf0, allowing the reload to reuse offset 0.
    nodes = [
        Node(0, "ALLOC", 0, 6, "L1"),
        Node(1, "USE", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(2, "ALLOC", 1, 6, "L1"),
        Node(3, "USE", pipe="VECTOR", cycles=1, bufs=(1,)),
        Node(4, "FREE", 1, 6, "L1"),
        Node(5, "USE", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(6, "FREE", 0, 6, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [(0, 1), (1, 5), (5, 6), (2, 3), (3, 4)],
    )
    result = allocate_q2_baseline(
        graph,
        base_order=(0, 1, 2, 3, 4, 5, 6),
        capacities={"L1": 10},
    )
    assert result.validation.ok, result.validation.errors
    assert result.validation.spill_count == 1
    assert result.validation.extra_traffic == 12
    assert result.solution.spills == (SpillRecord(0, 0),)
    # N=7: OUT=7 before Buf1 allocation; IN=8 before Buf0's second use.
    assert result.solution.schedule == (0, 1, 7, 2, 3, 4, 8, 5, 6)


def test_q2_baseline_rejects_single_buffer_larger_than_pool() -> None:
    graph = ComputeGraph.from_edges(
        [Node(0, "ALLOC", 0, 11, "L1"), Node(1, "FREE", 0, 11, "L1")],
        [(0, 1)],
    )
    with pytest.raises(ValueError, match="exceeds L1 capacity"):
        allocate_q2_baseline(graph, (0, 1), {"L1": 10})
