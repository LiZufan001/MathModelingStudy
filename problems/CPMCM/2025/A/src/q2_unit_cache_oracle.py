from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Mapping, Sequence

from model import ComputeGraph
from q2_model import spill_traffic_cost


@dataclass(frozen=True, slots=True)
class UnitCacheOracleResult:
    memory_type: str
    page_size: int
    capacity: int
    slots: int
    spill_count: int
    traffic_per_spill: int
    extra_traffic: int


def solve_uniform_unit_cache_oracle(
    graph: ComputeGraph,
    order: Sequence[int],
    *,
    memory_type: str,
    capacity: int,
) -> UnitCacheOracleResult:
    """Exact offline spill oracle for one uniform-size, uniform-cost cache pool.

    Preconditions are checked rather than assumed: every positive-size buffer in
    ``memory_type`` must have the same size and the same official spill traffic,
    and the pool capacity must be an integer number of such pages.

    Under those conditions contiguous placement cannot fragment the pool: every
    resident page occupies exactly one slot.  The problem therefore reduces to
    offline paging.  Belady/MIN is optimal: whenever one or more pages must be
    inserted, evict the currently resident non-required pages whose next
    residency requirements are farthest in the future.  FREE is treated as a
    residency requirement because Appendix B requires SPILL_IN -> FREE.

    Operations that require several buffers are handled as an atomic protected
    set: all missing required pages are inserted together, and no page required
    by the current operation may be chosen as a victim.
    """

    allocs = {
        node.buf_id: node
        for node in graph.nodes.values()
        if node.is_alloc
        and node.buf_id is not None
        and node.memory_type == memory_type
        and node.size is not None
        and node.size > 0
    }
    if not allocs:
        return UnitCacheOracleResult(memory_type, 0, capacity, 0, 0, 0, 0)

    sizes = {node.size for node in allocs.values()}
    if len(sizes) != 1:
        raise ValueError(
            f"{memory_type}: unit-cache oracle requires one positive size, got {sorted(sizes)}"
        )
    page_size = next(iter(sizes))
    assert page_size is not None and page_size > 0
    if capacity <= 0 or capacity % page_size != 0:
        raise ValueError(
            f"{memory_type}: capacity {capacity} is not a positive multiple of page size {page_size}"
        )
    slots = capacity // page_size

    traffic_values = {spill_traffic_cost(graph, buf_id) for buf_id in allocs}
    if len(traffic_values) != 1:
        raise ValueError(
            f"{memory_type}: unit-cache oracle requires uniform official spill traffic, "
            f"got {sorted(traffic_values)}"
        )
    traffic_per_spill = next(iter(traffic_values))

    if len(order) != graph.node_count or set(order) != set(graph.nodes):
        raise ValueError("order must contain every original graph node exactly once")

    requirement_positions: dict[int, list[int]] = {buf_id: [] for buf_id in allocs}
    for index, node_id in enumerate(order):
        node = graph.nodes[node_id]
        if node.is_free and node.buf_id in allocs:
            requirement_positions[node.buf_id].append(index)
        elif not node.is_memory_event:
            for buf_id in set(node.bufs):
                if buf_id in allocs:
                    requirement_positions[buf_id].append(index)

    resident: set[int] = set()
    live: set[int] = set()
    spill_count = 0

    def next_requirement(buf_id: int, current_index: int) -> int:
        positions = requirement_positions[buf_id]
        j = bisect.bisect_right(positions, current_index)
        if j >= len(positions):
            return 10**18
        return positions[j]

    def ensure_resident(required: set[int], current_index: int) -> None:
        nonlocal spill_count
        if len(required) > slots:
            raise ValueError(
                f"{memory_type}: node {order[current_index]} requires {len(required)} "
                f"uniform pages but pool has only {slots} slots"
            )
        missing = required - resident
        needed_evictions = max(0, len(resident) + len(missing) - slots)
        candidates = resident - required
        if needed_evictions > len(candidates):
            raise ValueError(
                f"{memory_type}: cannot make {len(missing)} slots while protecting "
                f"{len(required & resident)} required resident pages"
            )
        victims = sorted(
            candidates,
            key=lambda buf_id: (next_requirement(buf_id, current_index), buf_id),
            reverse=True,
        )[:needed_evictions]
        for victim in victims:
            resident.remove(victim)
            spill_count += 1
        resident.update(missing)

    for index, node_id in enumerate(order):
        node = graph.nodes[node_id]
        if node.is_alloc and node.buf_id in allocs:
            buf_id = node.buf_id
            assert buf_id is not None
            if buf_id in live:
                raise ValueError(f"buffer {buf_id} allocated twice")
            live.add(buf_id)
            ensure_resident({buf_id}, index)
            continue

        if node.is_free and node.buf_id in allocs:
            buf_id = node.buf_id
            assert buf_id is not None
            if buf_id not in live:
                raise ValueError(f"buffer {buf_id} freed while not live")
            ensure_resident({buf_id}, index)
            resident.remove(buf_id)
            live.remove(buf_id)
            continue

        if node.is_memory_event:
            continue

        required = {buf_id for buf_id in node.bufs if buf_id in allocs}
        if not required.issubset(live):
            missing_live = sorted(required - live)
            raise ValueError(f"node {node_id} uses non-live {memory_type} buffers {missing_live}")
        ensure_resident(required, index)

    if live or resident:
        raise ValueError(
            f"oracle ended with live={sorted(live)[:8]} resident={sorted(resident)[:8]}"
        )

    return UnitCacheOracleResult(
        memory_type=memory_type,
        page_size=page_size,
        capacity=capacity,
        slots=slots,
        spill_count=spill_count,
        traffic_per_spill=traffic_per_spill,
        extra_traffic=spill_count * traffic_per_spill,
    )
