from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from model import ComputeGraph
from q2_allocator import AddressPool
from q2_model import CACHE_CAPACITIES, Q2Solution, SpillRecord
from q2_validator import validate_q2_solution

AddressPolicy = Literal["best_fit", "first_fit_low", "first_fit_high", "next_fit"]


@dataclass(frozen=True, slots=True)
class Q3ReallocationResult:
    solution: Q2Solution
    policy: AddressPolicy


def _choose_start(
    pool: AddressPool,
    size: int,
    policy: AddressPolicy,
    cursor: int,
) -> int | None:
    if size == 0:
        return 0
    if policy == "best_fit":
        return pool.best_fit_start(size)
    if policy == "first_fit_low":
        for start, end in pool.free_intervals:
            if end - start >= size:
                return start
        return None
    if policy == "first_fit_high":
        for start, end in reversed(pool.free_intervals):
            if end - start >= size:
                return end - size
        return None
    if policy != "next_fit":
        raise ValueError(f"unknown address policy {policy!r}")

    # Prefer a placement at/after the rotating cursor, then wrap. This spreads
    # successive residency epochs over the address space without changing spill
    # victims or schedule order.
    for start, end in pool.free_intervals:
        candidate = max(start, cursor)
        if candidate + size <= end:
            return candidate
    for start, end in pool.free_intervals:
        if start >= cursor:
            continue
        if end - start >= size:
            return start
    return None


def repack_q3_addresses(
    graph: ComputeGraph,
    solution: Q2Solution,
    policy: AddressPolicy,
    capacities: Mapping[str, int] = CACHE_CAPACITIES,
) -> Q3ReallocationResult:
    """Recolor physical addresses while keeping schedule/SPILL identities fixed.

    The number/order/target buffer of every SPILL remains unchanged, so official
    extra traffic is identical by construction. Only initial offsets and SPILL_IN
    NewOffset values are regenerated. A full independent Q2 replay is mandatory
    before returning.
    """

    validate_q2_solution(graph, solution, capacities).require_ok()
    pools = {
        memory_type: AddressPool(capacity)
        for memory_type, capacity in capacities.items()
    }
    cursor = {memory_type: 0 for memory_type in capacities}
    initial_offsets: dict[int, int] = {}
    spill_offsets: list[int | None] = [None] * len(solution.spills)
    n = graph.node_count

    alloc_by_buf = {
        node.buf_id: node
        for node in graph.nodes.values()
        if node.is_alloc and node.buf_id is not None
    }

    def acquire(buf_id: int) -> int:
        alloc = alloc_by_buf[buf_id]
        assert alloc.memory_type is not None and alloc.size is not None
        memory_type = alloc.memory_type
        pool = pools[memory_type]
        start = _choose_start(pool, alloc.size, policy, cursor[memory_type])
        if start is None:
            raise ValueError(
                f"{policy}: cannot place buffer {buf_id} size={alloc.size} in {memory_type}"
            )
        pool.reserve_at(buf_id, start, alloc.size)
        if pool.capacity:
            cursor[memory_type] = (start + alloc.size) % pool.capacity
        return start

    def release(buf_id: int) -> None:
        alloc = alloc_by_buf[buf_id]
        assert alloc.memory_type is not None
        pools[alloc.memory_type].release(buf_id)

    for node_id in solution.schedule:
        if node_id < n:
            node = graph.nodes[node_id]
            if node.is_alloc:
                assert node.buf_id is not None
                initial_offsets[node.buf_id] = acquire(node.buf_id)
            elif node.is_free:
                assert node.buf_id is not None
                release(node.buf_id)
        else:
            relative = node_id - n
            spill_index = relative // 2
            spill = solution.spills[spill_index]
            if relative % 2 == 0:
                release(spill.buf_id)
            else:
                spill_offsets[spill_index] = acquire(spill.buf_id)

    if any(offset is None for offset in spill_offsets):
        raise ValueError(f"{policy}: one or more SPILL_IN offsets were not assigned")
    repacked = Q2Solution(
        schedule=solution.schedule,
        initial_offsets=initial_offsets,
        spills=tuple(
            SpillRecord(spill.buf_id, int(spill_offsets[index]))
            for index, spill in enumerate(solution.spills)
        ),
    )
    replay = validate_q2_solution(graph, repacked, capacities)
    replay.require_ok()
    original = validate_q2_solution(graph, solution, capacities)
    if replay.extra_traffic != original.extra_traffic or replay.spill_count != original.spill_count:
        raise AssertionError(f"{policy}: address recoloring changed Q2 traffic/spill count")
    return Q3ReallocationResult(repacked, policy)
