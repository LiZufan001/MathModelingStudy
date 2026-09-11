from __future__ import annotations

import bisect
import heapq
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
    """Choose a contiguous target window with exact minimum official spill traffic.

    For an occupied interval [s,e) and an integer start x, a size-q window
    [x,x+q) overlaps that interval exactly for x in [s-q+1, e-1]. Therefore the
    victim set changes only at two events per resident buffer. Sweeping those
    events evaluates every distinct victim set in O(R log R), rather than
    rescanning all R residents for O(R) candidate starts.

    The official extra-DDR traffic is the primary objective. Deterministic
    secondary keys prefer fewer victims, farther next use, then lower offset.
    They never override a lower official traffic cost.
    """

    if size < 0 or size > pool.capacity:
        return None
    if size == 0:
        return SpillWindowChoice(0, (), 0, pool.capacity, 10**9, 10**9)

    limit = pool.capacity - size
    protected_set = set(protected)
    # position -> [(+1 enter / -1 leave, buf_id)]
    events: dict[int, list[tuple[int, int]]] = {0: []}
    for start, end, buf_id in pool.used_intervals():
        # Zero-sized placements do not physically overlap any non-empty window.
        if start >= end:
            continue
        lo = max(0, start - size + 1)
        hi = min(limit, end - 1)
        if lo > hi:
            continue
        events.setdefault(lo, []).append((1, buf_id))
        events.setdefault(hi + 1, []).append((-1, buf_id))

    active: set[int] = set()
    active_cost = 0
    active_distance_sum = 0
    active_protected = 0
    min_distance_heap: list[tuple[int, int]] = []

    best_key: tuple[int, int, int, int, int] | None = None
    best_start: int | None = None
    best_victims: tuple[int, ...] = ()
    best_min_distance = 10**9
    best_sum_distance = 10**9

    for position in sorted(events):
        if position > limit:
            break
        for delta, buf_id in events[position]:
            distance = next_use_distances.get(buf_id, 10**9)
            if delta > 0:
                if buf_id in active:
                    raise AssertionError(f"duplicate overlap-enter event for buffer {buf_id}")
                active.add(buf_id)
                active_cost += traffic_costs[buf_id]
                active_distance_sum += distance
                if buf_id in protected_set:
                    active_protected += 1
                heapq.heappush(min_distance_heap, (distance, buf_id))
            else:
                if buf_id not in active:
                    raise AssertionError(f"overlap-leave event without active buffer {buf_id}")
                active.remove(buf_id)
                active_cost -= traffic_costs[buf_id]
                active_distance_sum -= distance
                if buf_id in protected_set:
                    active_protected -= 1

        if active_protected:
            continue

        while min_distance_heap and min_distance_heap[0][1] not in active:
            heapq.heappop(min_distance_heap)

        if active:
            min_distance = min_distance_heap[0][0]
            sum_distance = active_distance_sum
        else:
            min_distance = 10**9
            sum_distance = 10**9

        key = (
            active_cost,
            len(active),
            -min_distance,
            -sum_distance,
            position,
        )
        if best_key is None or key < best_key:
            best_key = key
            best_start = position
            best_victims = tuple(sorted(active))
            best_min_distance = min_distance
            best_sum_distance = sum_distance

    if best_key is None or best_start is None:
        return None

    victim_set = set(best_victims)
    return SpillWindowChoice(
        best_start,
        best_victims,
        best_key[0],
        _free_span_after_victims(pool, best_start, size, victim_set),
        best_min_distance,
        best_sum_distance,
    )


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

    pools: dict[str, AddressPool] = {
        memory_type: AddressPool(capacity)
        for memory_type, capacity in capacities.items()
    }

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

    def reload_at(buf_id: int, start: int) -> None:
        spill_index = pending_spill.get(buf_id)
        if spill_index is None:
            raise ValueError(f"buffer {buf_id} is nonresident without pending spill")
        alloc = alloc_nodes[buf_id]
        assert alloc.memory_type is not None and alloc.size is not None
        pool = pools[alloc.memory_type]
        pool.reserve_at(buf_id, start, alloc.size)
        mutable_spills[spill_index][1] = start
        _, in_id = spill_node_ids(graph, spill_index)
        output_schedule.append(in_id)
        pending_spill.pop(buf_id)

    def reload_buffer(buf_id: int, current_index: int, protected: set[int]) -> None:
        spill_index = pending_spill.get(buf_id)
        if spill_index is None:
            raise ValueError(f"buffer {buf_id} is nonresident without pending spill")
        alloc = alloc_nodes[buf_id]
        assert alloc.memory_type is not None and alloc.size is not None
        start = make_space(alloc.memory_type, alloc.size, current_index, protected)
        reload_at(buf_id, start)

    def repack_required_group(
        memory_type: str,
        group: set[int],
        current_index: int,
        node_id: int,
    ) -> None:
        """Compact one operation's simultaneous same-pool requirements.

        Sequential reload can fail when already-required buffers are themselves
        fragmented across the address space. In that case, spill every resident
        member of the required set, create one contiguous super-window for the
        whole set, and reload the set compactly. This is a correctness fallback:
        it may introduce extra traffic, but it never relaxes the official
        capacity/residency rules and is used only after protected placement has
        actually failed.
        """

        pool = pools[memory_type]
        ordered = sorted(
            group,
            key=lambda b: (-(alloc_nodes[b].size or 0), b),
        )
        total_size = sum(alloc_nodes[b].size or 0 for b in ordered)
        if total_size > pool.capacity:
            raise ValueError(
                f"node {node_id} simultaneously requires {total_size} bytes in "
                f"{memory_type}, exceeding capacity {pool.capacity}; "
                f"buffers={ordered[:12]}"
            )

        # Capture physical order before mutating placements. Members that were
        # already pending remain pending; members reloaded during a failed first
        # attempt are spilled again, yielding a new official spill pair.
        resident_required = sorted(
            (
                pool.placements[buf_id][0],
                buf_id,
            )
            for buf_id in group
            if buf_id in pool.placements
        )
        for _, buf_id in resident_required:
            spill_out(buf_id)

        not_pending = [buf_id for buf_id in ordered if buf_id not in pending_spill]
        if not_pending:
            raise AssertionError(
                f"required-set repack left resident/nonpending buffers: {not_pending[:8]}"
            )

        super_start = make_space(memory_type, total_size, current_index, set())
        cursor = super_start
        for buf_id in ordered:
            size = alloc_nodes[buf_id].size
            assert size is not None
            reload_at(buf_id, cursor)
            cursor += size

        for buf_id in group:
            if buf_id not in pool.placements:
                raise AssertionError(
                    f"node {node_id}: repack did not restore required buffer {buf_id}"
                )

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

        groups: dict[str, set[int]] = {}
        for buf_id in required:
            alloc = alloc_nodes[buf_id]
            assert alloc.memory_type is not None
            groups.setdefault(alloc.memory_type, set()).add(buf_id)

        for memory_type in sorted(groups):
            group = groups[memory_type]
            pool = pools[memory_type]
            total_required = sum(alloc_nodes[b].size or 0 for b in group)
            if total_required > pool.capacity:
                raise ValueError(
                    f"node {node_id} simultaneously requires {total_required} bytes in "
                    f"{memory_type}, exceeding capacity {pool.capacity}; "
                    f"buffers={sorted(group)[:12]}"
                )

            protected = {buf_id for buf_id in group if buf_id in pool.placements}
            missing = [buf_id for buf_id in group if buf_id not in protected]
            missing.sort(key=lambda b: (-(alloc_nodes[b].size or 0), b))

            try:
                for buf_id in missing:
                    reload_buffer(buf_id, current_index, protected)
                    protected.add(buf_id)
            except ValueError as exc:
                prefix = f"cannot make contiguous {memory_type} space"
                if not str(exc).startswith(prefix):
                    raise
                repack_required_group(memory_type, group, current_index, node_id)

            unresolved = [buf_id for buf_id in group if buf_id not in pool.placements]
            if unresolved:
                raise AssertionError(
                    f"node {node_id}: required {memory_type} buffers are not all resident: "
                    f"{unresolved[:8]}"
                )

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
