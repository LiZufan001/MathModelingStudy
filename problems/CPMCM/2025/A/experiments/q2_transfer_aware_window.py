from __future__ import annotations

import heapq
from collections.abc import Callable, Mapping

from q2_allocator import AddressPool, SpillWindowChoice, _free_span_after_victims


def choose_transfer_aware_window(
    pool: AddressPool,
    size: int,
    traffic_costs: Mapping[int, int],
    next_use_distances: Mapping[int, int],
    protected: frozenset[int] | set[int],
    *,
    transfer_cycle_costs: Mapping[int, int],
) -> SpillWindowChoice | None:
    """Minimum-traffic spill window with Q3 transfer cycles as a strict tie-break.

    The production allocator's primary keys are preserved exactly: official extra
    traffic first, then victim count.  Only when both are tied do we prefer the
    victim set whose SPILL_OUT+SPILL_IN work is smaller.  This is useful for Q3
    because equal Q2 traffic can have different transfer work (notably for
    COPY_IN-backed buffers, whose SPILL_OUT cost is zero).
    """

    if size < 0 or size > pool.capacity:
        return None
    if size == 0:
        return SpillWindowChoice(0, (), 0, pool.capacity, 10**9, 10**9)

    limit = pool.capacity - size
    protected_set = set(protected)
    events: dict[int, list[tuple[int, int]]] = {0: []}
    for start, end, buf_id in pool.used_intervals():
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
    active_transfer = 0
    active_distance_sum = 0
    active_protected = 0
    min_distance_heap: list[tuple[int, int]] = []

    best_key: tuple[int, int, int, int, int, int] | None = None
    best_start: int | None = None
    best_victims: tuple[int, ...] = ()
    best_min_distance = 10**9
    best_sum_distance = 10**9

    for position in sorted(events):
        if position > limit:
            break
        for delta, buf_id in events[position]:
            distance = next_use_distances.get(buf_id, 10**9)
            transfer = transfer_cycle_costs[buf_id]
            if delta > 0:
                if buf_id in active:
                    raise AssertionError(f"duplicate overlap-enter event for buffer {buf_id}")
                active.add(buf_id)
                active_cost += traffic_costs[buf_id]
                active_transfer += transfer
                active_distance_sum += distance
                if buf_id in protected_set:
                    active_protected += 1
                heapq.heappush(min_distance_heap, (distance, buf_id))
            else:
                if buf_id not in active:
                    raise AssertionError(f"overlap-leave event without active buffer {buf_id}")
                active.remove(buf_id)
                active_cost -= traffic_costs[buf_id]
                active_transfer -= transfer
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
            active_transfer,
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

    return SpillWindowChoice(
        best_start,
        best_victims,
        best_key[0],
        _free_span_after_victims(pool, best_start, size, set(best_victims)),
        best_min_distance,
        best_sum_distance,
    )


def make_transfer_aware_chooser(
    transfer_cycle_costs: Mapping[int, int],
) -> Callable[..., SpillWindowChoice | None]:
    """Return a drop-in choose_min_cost_window replacement for experiments."""

    def chooser(
        pool: AddressPool,
        size: int,
        traffic_costs: Mapping[int, int],
        next_use_distances: Mapping[int, int],
        protected: frozenset[int] | set[int] = frozenset(),
    ) -> SpillWindowChoice | None:
        return choose_transfer_aware_window(
            pool,
            size,
            traffic_costs,
            next_use_distances,
            protected,
            transfer_cycle_costs=transfer_cycle_costs,
        )

    return chooser
