from __future__ import annotations

from typing import Mapping

from model import ComputeGraph, Node
from q2_model import CACHE_CAPACITIES, Q2Solution, make_spill_nodes, spill_node_ids


def augmented_nodes(graph: ComputeGraph, solution: Q2Solution) -> dict[int, Node]:
    nodes = dict(graph.nodes)
    for spill_index, spill in enumerate(solution.spills):
        out_node, in_node = make_spill_nodes(graph, spill_index, spill.buf_id)
        if out_node.id in nodes or in_node.id in nodes:
            raise ValueError(f"spill node id collision at spill {spill_index}")
        nodes[out_node.id] = out_node
        nodes[in_node.id] = in_node
    return nodes


def original_edges(graph: ComputeGraph) -> set[tuple[int, int]]:
    return {(u, v) for u, succs in graph.successors.items() for v in succs}


def spill_edges(
    graph: ComputeGraph,
    solution: Q2Solution,
    nodes: Mapping[int, Node],
    pos: Mapping[int, int],
) -> set[tuple[int, int]]:
    """Appendix-B spill dependencies, including repeated spill epochs."""

    edges: set[tuple[int, int]] = set()
    uses: dict[int, list[int]] = {}
    for node_id, node in nodes.items():
        if node.is_memory_event:
            continue
        for buf_id in node.bufs:
            uses.setdefault(buf_id, []).append(node_id)

    for spill_index, spill in enumerate(solution.spills):
        alloc = graph.alloc_node_for_buffer(spill.buf_id)
        free = graph.free_node_for_buffer(spill.buf_id)
        if alloc is None or free is None:
            raise ValueError(f"spill {spill_index} buffer {spill.buf_id} lacks ALLOC/FREE")
        out_id, in_id = spill_node_ids(graph, spill_index)
        edges.update({(alloc.id, out_id), (out_id, in_id), (in_id, free.id)})
        out_pos = pos[out_id]
        for node_id in uses.get(spill.buf_id, ()):
            if node_id in {out_id, in_id}:
                continue
            if pos[node_id] < out_pos:
                edges.add((node_id, out_id))
            elif pos[node_id] > out_pos:
                edges.add((in_id, node_id))
    return edges


def pipe_edges(solution: Q2Solution, nodes: Mapping[int, Node]) -> set[tuple[int, int]]:
    edges: set[tuple[int, int]] = set()
    previous: dict[str, int] = {}
    for node_id in solution.schedule:
        pipe = nodes[node_id].pipe
        if pipe is None:
            continue
        if pipe in previous:
            edges.add((previous[pipe], node_id))
        previous[pipe] = node_id
    return edges


def official_literal_reuse_edges(
    graph: ComputeGraph,
    solution: Q2Solution,
    pos: Mapping[int, int],
    capacities: Mapping[str, int] = CACHE_CAPACITIES,
) -> set[tuple[int, int]]:
    """Appendix-C step 2 literally: FREE(previous)->ALLOC(current).

    Initial buffers are visited in submitted ALLOC order. Per-byte last-owner
    state finds the most recent previous allocation of each reused address range.
    A range vacated only by SPILL_OUT is intentionally left to residency-safe mode.
    """

    last_owner: dict[str, list[int | None]] = {
        memory_type: [None] * capacity for memory_type, capacity in capacities.items()
    }
    allocs = sorted(
        (node for node in graph.nodes.values() if node.is_alloc),
        key=lambda node: pos[node.id],
    )
    edges: set[tuple[int, int]] = set()

    for alloc in allocs:
        if alloc.buf_id is None or alloc.memory_type is None or alloc.size is None:
            raise ValueError(f"ALLOC node {alloc.id} has incomplete metadata")
        start = solution.initial_offsets[alloc.buf_id]
        end = start + alloc.size
        owners = last_owner[alloc.memory_type]
        if start < 0 or end > len(owners):
            raise ValueError(f"buffer {alloc.buf_id} initial range exceeds {alloc.memory_type}")
        for previous_buf in {owner for owner in owners[start:end] if owner is not None}:
            free = graph.free_node_for_buffer(previous_buf)
            if free is None:
                raise ValueError(f"buffer {previous_buf} lacks FREE")
            if pos[free.id] < pos[alloc.id]:
                edges.add((free.id, alloc.id))
        for address in range(start, end):
            owners[address] = alloc.buf_id
    return edges


def residency_epoch_edges(
    graph: ComputeGraph,
    solution: Q2Solution,
) -> set[tuple[int, int]]:
    """Preserve acquire->release order for every physical residency epoch.

    Q2 is validated as a sequential event stream, but Q3 executes different
    Pipes in parallel.  A SPILL_IN epoch with no intervening business use can
    otherwise have its next SPILL_OUT race ahead of the reload.  These lifetime
    edges are timing-safety constraints, not address-reuse edges, so callers keep
    them separate from reuse-edge statistics.
    """

    edges: set[tuple[int, int]] = set()
    active_acquire: dict[int, int] = {}
    n = graph.node_count

    def acquire(buf_id: int, node_id: int) -> None:
        if buf_id in active_acquire:
            raise ValueError(f"acquire {node_id}: buffer {buf_id} already has active epoch")
        active_acquire[buf_id] = node_id

    def release(buf_id: int, node_id: int) -> None:
        acquire_node = active_acquire.pop(buf_id, None)
        if acquire_node is None:
            raise ValueError(f"release {node_id}: buffer {buf_id} has no active epoch")
        if acquire_node != node_id:
            edges.add((acquire_node, node_id))

    for node_id in solution.schedule:
        if node_id < n:
            node = graph.nodes[node_id]
            if node.is_alloc:
                assert node.buf_id is not None
                acquire(node.buf_id, node_id)
            elif node.is_free:
                assert node.buf_id is not None
                release(node.buf_id, node_id)
        else:
            relative = node_id - n
            spill = solution.spills[relative // 2]
            if relative % 2 == 0:
                release(spill.buf_id, node_id)
            else:
                acquire(spill.buf_id, node_id)

    if active_acquire:
        raise ValueError(f"residency lifetime replay ended with buffers {sorted(active_acquire)[:8]}")
    return edges


def residency_safe_reuse_edges(
    graph: ComputeGraph,
    solution: Q2Solution,
    capacities: Mapping[str, int] = CACHE_CAPACITIES,
) -> set[tuple[int, int]]:
    """Release->acquire edges between actual physical residency epochs.

    This strengthens literal FREE/ALLOC reuse when SPILL temporarily releases an
    address: SPILL_OUT/FREE must finish before a later ALLOC/SPILL_IN starts using
    any of the same bytes.  Epoch-internal acquire->release ordering is handled
    separately by :func:`residency_epoch_edges` so reuse statistics stay stable.
    """

    current_owner: dict[str, list[int | None]] = {
        memory_type: [None] * capacity for memory_type, capacity in capacities.items()
    }
    last_release: dict[str, list[int | None]] = {
        memory_type: [None] * capacity for memory_type, capacity in capacities.items()
    }
    placement: dict[int, tuple[str, int, int]] = {}
    edges: set[tuple[int, int]] = set()
    n = graph.node_count
    alloc_by_buf = {
        node.buf_id: node
        for node in graph.nodes.values()
        if node.is_alloc and node.buf_id is not None
    }

    def acquire(buf_id: int, start: int, node_id: int) -> None:
        alloc = alloc_by_buf[buf_id]
        assert alloc.memory_type is not None and alloc.size is not None
        memory_type = alloc.memory_type
        end = start + alloc.size
        owners = current_owner[memory_type]
        releases = last_release[memory_type]
        if start < 0 or end > len(owners):
            raise ValueError(f"acquire {node_id}: buffer {buf_id} range exceeds {memory_type}")
        for release_node in {r for r in releases[start:end] if r is not None}:
            edges.add((release_node, node_id))
        for address in range(start, end):
            if owners[address] is not None:
                raise ValueError(
                    f"acquire {node_id}: {memory_type}[{address}] still owned by {owners[address]}"
                )
            owners[address] = buf_id
        placement[buf_id] = (memory_type, start, end)

    def release(buf_id: int, node_id: int) -> None:
        if buf_id not in placement:
            raise ValueError(f"release {node_id}: buffer {buf_id} not resident")
        memory_type, start, end = placement.pop(buf_id)
        owners = current_owner[memory_type]
        releases = last_release[memory_type]
        for address in range(start, end):
            if owners[address] != buf_id:
                raise ValueError(
                    f"release {node_id}: {memory_type}[{address}] owner={owners[address]}, expected={buf_id}"
                )
            owners[address] = None
            releases[address] = node_id

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

    if placement:
        raise ValueError(f"residency replay ended with buffers {sorted(placement)[:8]}")
    return edges
