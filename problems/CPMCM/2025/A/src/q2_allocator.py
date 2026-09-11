from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Mapping, Sequence

from model import ComputeGraph
from q2_model import CACHE_CAPACITIES, Q2Solution, SpillRecord, copy_in_backed_buffers, spill_node_ids
from q2_validator import Q2ValidationResult, validate_q2_solution
from validators import validate_topological_order


@dataclass(frozen=True, slots=True)
class SpillWindowChoice:
    start: int
    victims: tuple[int, ...]
    traffic_cost: int
    free_span: int
    min_next_use_distance: int
    sum_next_use_distance: int


@dataclass(frozen=True, slots=True)
class Q2AllocationResult:
    solution: Q2Solution
    validation: Q2ValidationResult


class AddressPool:
    """Contiguous-address allocator for one cache pool."""

    def __init__(self, capacity: int) -> None:
        if capacity < 0:
            raise ValueError("capacity must be non-negative")
        self.capacity = capacity
        self.free_intervals: list[tuple[int, int]] = [(0, capacity)] if capacity else []
        self.placements: dict[int, tuple[int, int]] = {}

    def best_fit_start(self, size: int) -> int | None:
        if size < 0:
            raise ValueError("size must be non-negative")
        if size == 0:
            return 0
        candidates = [
            (end - start - size, start)
            for start, end in self.free_intervals
            if end - start >= size
        ]
        if not candidates:
            return None
        return min(candidates)[1]

    def is_range_free(self, start: int, size: int) -> bool:
        if size < 0 or start < 0 or start + size > self.capacity:
            return False
        if size == 0:
            return True
        end = start + size
        return any(free_start <= start and end <= free_end for free_start, free_end in self.free_intervals)

    def reserve_at(self, buf_id: int, start: int, size: int) -> None:
        if buf_id in self.placements:
            raise ValueError(f"buffer {buf_id} is already placed")
        if not self.is_range_free(start, size):
            raise ValueError(f"range [{start},{start + size}) is not free")
        end = start + size
        self.placements[buf_id] = (start, end)
        if size == 0:
            return
        for i, (free_start, free_end) in enumerate(self.free_intervals):
            if free_start <= start and end <= free_end:
                replacement: list[tuple[int, int]] = []
                if free_start < start:
                    replacement.append((free_start, start))
                if end < free_end:
                    replacement.append((end, free_end))
                self.free_intervals[i : i + 1] = replacement
                return
        raise AssertionError("free interval disappeared before reserve")

    def allocate_best_fit(self, buf_id: int, size: int) -> int | None:
        start = self.best_fit_start(size)
        if start is None:
            return None
        self.reserve_at(buf_id, start, size)
        return start

    def release(self, buf_id: int) -> tuple[int, int]:
        if buf_id not in self.placements:
            raise ValueError(f"buffer {buf_id} is not placed")
        start, end = self.placements.pop(buf_id)
        if start == end:
            return start, end
        bisect.insort(self.free_intervals, (start, end))
        merged: list[tuple[int, int]] = []
        for cur_start, cur_end in self.free_intervals:
            if not merged or merged[-1][1] < cur_start:
                merged.append((cur_start, cur_end))
            else:
                prev_start, prev_end = merged[-1]
                merged[-1] = (prev_start, max(prev_end, cur_end))
        self.free_intervals = merged
        return start, end

    def used_intervals(self) -> list[tuple[int, int, int]]:
        return sorted((start, end, buf_id) for buf_id, (start, end) in self.placements.items())


def _candidate_window_starts(pool: AddressPool, size: int) -> tuple[int, ...]:
    """Enumerate one representative on each integer overlap-set boundary.

    For an occupied interval [s,e), a size-q window [x,x+q) overlaps it for
    integer x in [s-q+1, e-1].  Therefore s-q/s-q+1 and e-1/e are sufficient
    transition representatives.  Unit tests compare the resulting minimum
    traffic cost against brute force over every integer x on small pools.
    """

    if size < 0 or size > pool.capacity:
        return ()
    limit = pool.capacity - size
    starts = {0, limit}
    for start, end, _ in pool.used_intervals():
        for candidate in (start - size, start - size + 1, end - 1, end):
            starts.add(min(limit, max(0, candidate)))
    return tuple(sorted(starts))


def _free_span_after_victims(
    pool: AddressPool,
    window_start: int,
    size: int,
    victims: set[int],
) -> int:
    window_end = window_start + size
    left = 0
    right = pool.capacity
    for start, end, buf_id in pool.used_intervals():
        if buf_id in victims:
            continue
        if end <= window_start:
            left = max(left, end)
        elif start >= window_end:
            right = min(right, start)
    return right - left


def choose_min_cost_window(
    pool: AddressPool,
    size: int,
    traffic_costs: Mapping[int, int],
    next_use_distances: Mapping[int, int],
    protected: frozenset[int] | set[int] = frozenset(),
) -> SpillWindowChoice | None:
    """Choose a contiguous target window with minimum official spill traffic.

    The official traffic objective is the primary key.  Victim count,
    next-use distance, post-spill free span, and address are deterministic
    secondary criteria only.
    """

    if size < 0 or size > pool.capacity:
        return None
    if size == 0:
        return SpillWindowChoice(0, (), 0, pool.capacity, 10**9, 10**9)

    best: tuple[tuple[object, ...], SpillWindowChoice] | None = None
    protected_set = set(protected)
    used = pool.used_intervals()

    for start in _candidate_window_starts(pool, size):
        end = start + size
        victims = tuple(
            sorted(
                buf_id
                for used_start, used_end, buf_id in used
                if start < used_end and used_start < end
            )
        )
        if protected_set.intersection(victims):
            continue
        victim_set = set(victims)
        cost = sum(traffic_costs[buf_id] for buf_id in victims)
        if victims:
            distances = [next_use_distances.get(buf_id, 10**9) for buf_id in victims]
            min_distance = min(distances)
            sum_distance = sum(distances)
        else:
            min_distance = 10**9
            sum_distance = 10**9
        free_span = _free_span_after_victims(pool, start, size, victim_set)
        choice = SpillWindowChoice(
            start,
            victims,
            cost,
            free_span,
            min_distance,
            sum_distance,
        )
        key: tuple[object, ...] = (
            cost,
            len(victims),
            -min_distance,
            -sum_distance,
            -free_span,
            start,
            victims,
        )
        if best is None or key < best[0]:
            best = (key, choice)

    return None if best is None else best[1]


def _validate_base_order(graph: ComputeGraph, order: Sequence[int]) -> None:
    topo = validate_topological_order(graph, tuple(order))
    topo.require_ok()
    pos = {node_id: i for i, node_id in enumerate(order)}
    for node_id in order:
        node = graph.nodes[node_id]
        if node.is_memory_event:
            continue
        for buf_id in node.bufs:
            alloc = graph.alloc_node_for_buffer(buf_id)
            free = graph.free_node_for_buffer(buf_id)
            if alloc is None or free is None:
                raise ValueError(f"node {node_id} buffer {buf_id} lacks ALLOC/FREE")
            if not (pos[alloc.id] < pos[node_id] < pos[free.id]):
                raise ValueError(
                    f"base order uses buffer {buf_id} outside ALLOC/FREE lifetime at node {node_id}"
                )


def allocate_q2_baseline(
    graph: ComputeGraph,
    base_order: Sequence[int],
    capacities: Mapping[str, int] = CACHE_CAPACITIES,
) -> Q2AllocationResult:
    """Best-fit + minimum-traffic-window Q2 baseline on a fixed original order."""

    _validate_base_order(graph, base_order)
    n = graph.node_count

    alloc_nodes = {
        node.buf_id: node
        for node in graph.nodes.values()
        if node.is_alloc and node.buf_id is not None
    }
    copy_in_backed = copy_in_backed_buffers(graph)
    traffic_costs = {
        buf_id: (node.size if buf_id in copy_in_backed else 2 * node.size)
        for buf_id, node in alloc_nodes.items()
        if node.size is not None
    }

    pools: dict[str, AddressPool] = {}
    for memory_type, capacity in capacities.items():
        pools[memory_type] = AddressPool(capacity)

    for buf_id, alloc in alloc_nodes.items():
        if alloc.memory_type not in pools or alloc.size is None:
            raise ValueError(f"buffer {buf_id} has unsupported allocation metadata")
        if alloc.size > pools[alloc.memory_type].capacity:
            raise ValueError(
                f"buffer {buf_id} size {alloc.size} exceeds {alloc.memory_type} "
                f"capacity {pools[alloc.memory_type].capacity}"
            )

    use_positions: dict[int, list[int]] = {buf_id: [] for buf_id in alloc_nodes}
    for index, node_id in enumerate(base_order):
        node = graph.nodes[node_id]
        if node.is_free and node.buf_id is not None:
            use_positions[node.buf_id].append(index)
        elif not node.is_memory_event:
            for buf_id in node.bufs:
                use_positions[buf_id].append(index)

    output_schedule: list[int] = []
    initial_offsets: dict[int, int] = {}
    # Mutable [buf_id, new_offset] records; offset is filled when SPILL_IN occurs.
    mutable_spills: list[list[int | None]] = []
    live: set[int] = set()
    pending_spill: dict[int, int] = {}

    def next_use_distance(buf_id: int, current_index: int) -> int:
        positions = use_positions[buf_id]
        j = bisect.bisect_left(positions, current_index)
        if j >= len(positions):
            return 10**9
        return positions[j] - current_index

    def spill_out(buf_id: int) -> None:
        if buf_id not in live:
            raise ValueError(f"cannot spill non-live buffer {buf_id}")
        if buf_id in pending_spill:
            raise ValueError(f"buffer {buf_id} already has pending spill")
        alloc = alloc_nodes[buf_id]
        assert alloc.memory_type is not None
        pool = pools[alloc.memory_type]
        pool.release(buf_id)
        spill_index = len(mutable_spills)
        mutable_spills.append([buf_id, None])
        out_id, _ = spill_node_ids(graph, spill_index)
        output_schedule.append(out_id)
        pending_spill[buf_id] = spill_index

    def make_space(
        memory_type: str,
        size: int,
        current_index: int,
        protected: set[int],
    ) -> int:
        pool = pools[memory_type]
        start = pool.best_fit_start(size)
        if start is not None:
            return start

        distances = {
            buf_id: next_use_distance(buf_id, current_index)
            for buf_id in pool.placements
        }
        choice = choose_min_cost_window(
            pool,
            size,
            traffic_costs,
            distances,
            protected,
        )
        if choice is None:
            raise ValueError(
                f"cannot make contiguous {memory_type} space of size {size}; "
                f"protected={sorted(protected)[:8]}"
            )
        victim_starts = {
            buf_id: pool.placements[buf_id][0]
            for buf_id in choice.victims
        }
        for victim in sorted(choice.victims, key=lambda b: (victim_starts[b], b)):
            spill_out(victim)
        if not pool.is_range_free(choice.start, size):
            raise AssertionError("selected spill window did not become free")
        return choice.start

    def reload_buffer(buf_id: int, current_index: int, protected: set[int]) -> None:
        spill_index = pending_spill.get(buf_id)
        if spill_index is None:
            raise ValueError(f"buffer {buf_id} is nonresident without pending spill")
        alloc = alloc_nodes[buf_id]
        assert alloc.memory_type is not None and alloc.size is not None
        pool = pools[alloc.memory_type]
        start = make_space(alloc.memory_type, alloc.size, current_index, protected)
        pool.reserve_at(buf_id, start, alloc.size)
        mutable_spills[spill_index][1] = start
        _, in_id = spill_node_ids(graph, spill_index)
        output_schedule.append(in_id)
        pending_spill.pop(buf_id)

    for current_index, node_id in enumerate(base_order):
        node = graph.nodes[node_id]

        if node.is_alloc:
            assert node.buf_id is not None and node.memory_type is not None and node.size is not None
            buf_id = node.buf_id
            if buf_id in live:
                raise ValueError(f"buffer {buf_id} allocated twice")
            pool = pools[node.memory_type]
            start = make_space(node.memory_type, node.size, current_index, set())
            pool.reserve_at(buf_id, start, node.size)
            initial_offsets[buf_id] = start
            live.add(buf_id)
            output_schedule.append(node_id)
            continue

        if node.is_free:
            assert node.buf_id is not None and node.memory_type is not None
            buf_id = node.buf_id
            if buf_id in pending_spill:
                reload_buffer(buf_id, current_index, set())
            pool = pools[node.memory_type]
            if buf_id not in pool.placements:
                raise ValueError(f"FREE node {node_id}: buffer {buf_id} is not resident")
            output_schedule.append(node_id)
            pool.release(buf_id)
            live.remove(buf_id)
            continue

        required = set(node.bufs)
        for buf_id in required:
            if buf_id not in live:
                raise ValueError(f"node {node_id} requires non-live buffer {buf_id}")
        protected = {
            buf_id
            for buf_id in required
            if buf_id in pools[alloc_nodes[buf_id].memory_type].placements  # type: ignore[index]
        }
        missing = [buf_id for buf_id in required if buf_id not in protected]
        missing.sort(
            key=lambda b: (
                -(alloc_nodes[b].size or 0),
                alloc_nodes[b].memory_type or "",
                b,
            )
        )
        for buf_id in missing:
            reload_buffer(buf_id, current_index, protected)
            protected.add(buf_id)
        output_schedule.append(node_id)

    if live:
        raise AssertionError(f"allocator ended with live buffers: {sorted(live)[:8]}")
    if pending_spill:
        raise AssertionError(f"allocator ended with pending spills: {pending_spill}")

    spills: list[SpillRecord] = []
    for spill_index, (buf_id, new_offset) in enumerate(mutable_spills):
        if buf_id is None or new_offset is None:
            raise AssertionError(f"spill {spill_index} was never completed")
        spills.append(SpillRecord(int(buf_id), int(new_offset)))

    solution = Q2Solution(tuple(output_schedule), dict(initial_offsets), tuple(spills))
    validation = validate_q2_solution(graph, solution, capacities)
    validation.require_ok()
    return Q2AllocationResult(solution, validation)
