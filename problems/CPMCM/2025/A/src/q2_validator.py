from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from model import ComputeGraph
from q2_model import CACHE_CAPACITIES, Q2Solution, copy_in_backed_buffers, spill_node_ids


@dataclass(frozen=True, slots=True)
class Q2ValidationResult:
    ok: bool
    errors: tuple[str, ...]
    extra_traffic: int
    spill_count: int

    def require_ok(self) -> None:
        if not self.ok:
            raise ValueError("; ".join(self.errors))


def _overlap(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and b0 < a1


def validate_q2_solution(
    graph: ComputeGraph,
    solution: Q2Solution,
    capacities: Mapping[str, int] = CACHE_CAPACITIES,
) -> Q2ValidationResult:
    """Independently replay a Q2 submission under the official SPILL semantics.

    The validator does not call the allocator.  It reconstructs logical liveness,
    physical residency, contiguous-address conflicts, and SPILL pairing from the
    submitted schedule / memory / spill triplet.
    """

    errors: list[str] = []
    max_errors = 40

    def err(message: str) -> None:
        if len(errors) < max_errors:
            errors.append(message)

    n = graph.node_count
    original_ids = set(graph.nodes)
    if original_ids != set(range(n)):
        err("Q2 official spill ids require original node ids to be exactly 0..N-1")

    alloc_nodes = {
        node.buf_id: node
        for node in graph.nodes.values()
        if node.is_alloc and node.buf_id is not None
    }
    buffers = set(alloc_nodes)

    offset_keys = set(solution.initial_offsets)
    missing_offsets = buffers - offset_keys
    extra_offsets = offset_keys - buffers
    if missing_offsets:
        err(f"memory mapping misses buffers: {sorted(missing_offsets)[:8]}")
    if extra_offsets:
        err(f"memory mapping has unknown buffers: {sorted(extra_offsets)[:8]}")
    for buf_id, offset in solution.initial_offsets.items():
        if not isinstance(offset, int):
            err(f"buffer {buf_id} initial offset is not an integer: {offset!r}")

    for spill_index, spill in enumerate(solution.spills):
        if spill.buf_id not in buffers:
            err(f"spill {spill_index} references unknown buffer {spill.buf_id}")
        if not isinstance(spill.new_offset, int):
            err(f"spill {spill_index} new offset is not an integer: {spill.new_offset!r}")

    m = len(solution.spills)
    spill_ids = set(range(n, n + 2 * m))
    expected_ids = original_ids | spill_ids
    schedule = solution.schedule
    if len(schedule) != n + 2 * m:
        err(f"schedule length {len(schedule)} != N+2M ({n + 2 * m})")
    if len(set(schedule)) != len(schedule):
        err("schedule contains duplicate node ids")
    unknown = set(schedule) - expected_ids
    missing = expected_ids - set(schedule)
    if unknown:
        err(f"schedule references unknown node ids: {sorted(unknown)[:8]}")
    if missing:
        err(f"schedule misses node ids: {sorted(missing)[:8]}")

    # Structural errors make positional/replay diagnostics unreliable.
    if errors:
        return Q2ValidationResult(False, tuple(errors), 0, m)

    pos = {node_id: index for index, node_id in enumerate(schedule)}

    for u, succs in graph.successors.items():
        for v in succs:
            if pos[u] >= pos[v]:
                err(f"original dependency violated: {u} must precede {v}")

    for spill_index, spill in enumerate(solution.spills):
        alloc = graph.alloc_node_for_buffer(spill.buf_id)
        free = graph.free_node_for_buffer(spill.buf_id)
        if alloc is None or free is None:
            err(f"spill {spill_index} buffer {spill.buf_id} lacks ALLOC/FREE")
            continue
        out_id, in_id = spill_node_ids(graph, spill_index)
        if not (pos[alloc.id] < pos[out_id] < pos[in_id] < pos[free.id]):
            err(
                f"spill {spill_index} must satisfy ALLOC({alloc.id}) < "
                f"OUT({out_id}) < IN({in_id}) < FREE({free.id})"
            )

    copy_in_backed = copy_in_backed_buffers(graph)
    extra_traffic = 0
    for spill in solution.spills:
        alloc = alloc_nodes.get(spill.buf_id)
        if alloc is not None and alloc.size is not None:
            extra_traffic += alloc.size if spill.buf_id in copy_in_backed else 2 * alloc.size

    live: set[int] = set()
    # buf -> (memory_type, start, end)
    resident: dict[int, tuple[str, int, int]] = {}
    # At most one unmatched SPILL_OUT per buffer is legal.
    pending_spill: dict[int, int] = {}

    def place(buf_id: int, offset: int, context: str) -> None:
        alloc = alloc_nodes[buf_id]
        if alloc.memory_type is None or alloc.size is None:
            err(f"buffer {buf_id} has incomplete ALLOC metadata")
            return
        memory_type = alloc.memory_type
        size = alloc.size
        capacity = capacities.get(memory_type)
        if capacity is None:
            err(f"no capacity defined for {memory_type}")
            return
        end = offset + size
        if offset < 0 or end > capacity:
            err(
                f"{context}: buffer {buf_id} interval [{offset},{end}) exceeds "
                f"{memory_type} capacity {capacity}"
            )
        for other_buf, (other_type, other_start, other_end) in resident.items():
            if other_type == memory_type and _overlap(offset, end, other_start, other_end):
                err(
                    f"{context}: buffer {buf_id} [{offset},{end}) overlaps resident "
                    f"buffer {other_buf} [{other_start},{other_end}) in {memory_type}"
                )
        resident[buf_id] = (memory_type, offset, end)

    for schedule_index, node_id in enumerate(schedule):
        if node_id < n:
            node = graph.nodes[node_id]
            if node.is_alloc:
                assert node.buf_id is not None
                buf_id = node.buf_id
                if buf_id in live:
                    err(f"node {node_id}: buffer {buf_id} allocated while already live")
                live.add(buf_id)
                place(buf_id, solution.initial_offsets[buf_id], f"ALLOC node {node_id}")

            elif node.is_free:
                assert node.buf_id is not None
                buf_id = node.buf_id
                if buf_id not in live:
                    err(f"node {node_id}: buffer {buf_id} FREE while not logically live")
                if buf_id in pending_spill:
                    err(
                        f"node {node_id}: buffer {buf_id} FREE before matching "
                        f"SPILL_IN for spill {pending_spill[buf_id]}"
                    )
                if buf_id not in resident:
                    err(f"node {node_id}: buffer {buf_id} FREE while not resident")
                resident.pop(buf_id, None)
                live.discard(buf_id)

            else:
                for buf_id in node.bufs:
                    if buf_id not in live:
                        err(f"node {node_id}: buffer {buf_id} is not logically live")
                    if buf_id not in resident:
                        err(f"node {node_id}: buffer {buf_id} is spilled out / not resident")

        else:
            relative = node_id - n
            spill_index = relative // 2
            is_out = relative % 2 == 0
            spill = solution.spills[spill_index]
            buf_id = spill.buf_id

            if is_out:
                if buf_id not in live:
                    err(f"SPILL_OUT {node_id}: buffer {buf_id} is not logically live")
                if buf_id in pending_spill:
                    err(
                        f"SPILL_OUT {node_id}: buffer {buf_id} already has pending "
                        f"spill {pending_spill[buf_id]}"
                    )
                if buf_id not in resident:
                    err(f"SPILL_OUT {node_id}: buffer {buf_id} is not resident")
                else:
                    resident.pop(buf_id)
                pending_spill[buf_id] = spill_index

            else:
                if buf_id not in live:
                    err(f"SPILL_IN {node_id}: buffer {buf_id} is not logically live")
                if pending_spill.get(buf_id) != spill_index:
                    err(
                        f"SPILL_IN {node_id}: expected pending spill {spill_index} "
                        f"for buffer {buf_id}, got {pending_spill.get(buf_id)}"
                    )
                if buf_id in resident:
                    err(f"SPILL_IN {node_id}: buffer {buf_id} is already resident")
                place(buf_id, spill.new_offset, f"SPILL_IN node {node_id}")
                if pending_spill.get(buf_id) == spill_index:
                    pending_spill.pop(buf_id)

        if len(errors) >= max_errors:
            break

    if pending_spill:
        err(f"unmatched SPILL_OUT operations remain: {sorted(pending_spill.items())[:8]}")
    if live:
        err(f"buffers still logically live at end: {sorted(live)[:8]}")
    if resident:
        err(f"buffers still resident at end: {sorted(resident)[:8]}")

    return Q2ValidationResult(not errors, tuple(errors), extra_traffic, m)
