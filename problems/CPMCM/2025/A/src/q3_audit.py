from __future__ import annotations

from typing import Mapping

from model import ComputeGraph
from q2_model import CACHE_CAPACITIES, Q2Solution
from q3_model import ResidencyEpoch


def physical_epochs(graph: ComputeGraph, solution: Q2Solution) -> list[ResidencyEpoch]:
    n = graph.node_count
    alloc_by_buf = {
        node.buf_id: node
        for node in graph.nodes.values()
        if node.is_alloc and node.buf_id is not None
    }
    current: dict[int, tuple[str, int, int, int]] = {}
    epochs: list[ResidencyEpoch] = []

    def acquire(buf_id: int, offset: int, node_id: int) -> None:
        alloc = alloc_by_buf[buf_id]
        assert alloc.memory_type is not None and alloc.size is not None
        current[buf_id] = (alloc.memory_type, offset, offset + alloc.size, node_id)

    def release(buf_id: int, node_id: int) -> None:
        if buf_id not in current:
            raise ValueError(f"release {node_id}: buffer {buf_id} has no active residency epoch")
        memory_type, start, end, acquire_node = current.pop(buf_id)
        epochs.append(
            ResidencyEpoch(buf_id, memory_type, start, end, acquire_node, node_id)
        )

    for node_id in solution.schedule:
        if node_id < n:
            node = graph.nodes[node_id]
            if node.is_alloc:
                assert node.buf_id is not None
                acquire(node.buf_id, solution.initial_offsets[node.buf_id], node_id)
            elif node.is_free:
                assert node.buf_id is not None
                release(node.buf_id, node_id)
        else:
            relative = node_id - n
            spill = solution.spills[relative // 2]
            if relative % 2 == 0:
                release(spill.buf_id, node_id)
            else:
                acquire(spill.buf_id, spill.new_offset, node_id)

    if current:
        raise ValueError(f"epoch replay ended with resident buffers {sorted(current)[:8]}")
    return epochs


def audit_physical_time_overlap(
    epochs: list[ResidencyEpoch],
    start_times: Mapping[int, int],
    finish_times: Mapping[int, int],
    capacities: Mapping[str, int] = CACHE_CAPACITIES,
    max_errors: int = 20,
) -> tuple[str, ...]:
    """Audit actual execution-time occupancy of every cache byte.

    ALLOC acquires at its zero-cycle start. SPILL_IN starts writing the target at
    its start. SPILL_OUT retains the source until its transfer finishes. FREE is
    zero-cycle. Physical occupancy is treated as a half-open time interval
    [acquire_start, release_finish): a zero-duration epoch therefore occupies no
    cache time and must not leave a phantom owner in the timestamp sweep.

    For non-empty epochs, release events are processed before acquisitions at the
    same timestamp so a later owner may immediately reuse bytes just released by
    an earlier epoch.
    """

    events: list[tuple[int, int, ResidencyEpoch]] = []
    errors: list[str] = []
    for epoch in epochs:
        acquire_time = start_times[epoch.acquire_node]
        release_time = finish_times[epoch.release_node]
        if release_time < acquire_time:
            errors.append(
                f"negative residency interval for buffer {epoch.buf_id} "
                f"epoch@{epoch.acquire_node}: acquire={acquire_time}, release={release_time}"
            )
            if len(errors) >= max_errors:
                return tuple(errors)
            continue
        if release_time == acquire_time:
            # Half-open interval [t, t) is empty.  Emitting release-before-acquire
            # events for it would incorrectly leave the acquire token resident.
            continue
        events.append((release_time, 0, epoch))
        events.append((acquire_time, 1, epoch))
    events.sort(key=lambda item: (item[0], item[1], item[2].acquire_node, item[2].buf_id))

    owner: dict[str, list[tuple[int, int] | None]] = {
        memory_type: [None] * capacity for memory_type, capacity in capacities.items()
    }
    seen_pairs: set[tuple[int, int, int, int]] = set()

    for time, kind, epoch in events:
        slots = owner[epoch.memory_type]
        token = (epoch.buf_id, epoch.acquire_node)
        if kind == 0:
            for address in range(epoch.start, epoch.end):
                if slots[address] == token:
                    slots[address] = None
            continue

        for address in range(epoch.start, epoch.end):
            previous = slots[address]
            if previous is not None and previous != token:
                key = (previous[0], previous[1], epoch.buf_id, epoch.acquire_node)
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    errors.append(
                        f"t={time}: {epoch.memory_type}[{address}] overlaps "
                        f"buffer {previous[0]} epoch@{previous[1]} with "
                        f"buffer {epoch.buf_id} epoch@{epoch.acquire_node}"
                    )
                    if len(errors) >= max_errors:
                        return tuple(errors)
            slots[address] = token
    return tuple(errors)
