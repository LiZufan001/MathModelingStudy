from __future__ import annotations

from dataclasses import dataclass

from model import ComputeGraph, Node

# Authoritative capacities from Table 1 of the original statement.
CACHE_CAPACITIES: dict[str, int] = {
    "L1": 4096,
    "UB": 1024,
    "L0A": 256,
    "L0B": 256,
    "L0C": 512,
}


@dataclass(frozen=True, slots=True)
class SpillRecord:
    """One official SPILL operation pair, ordered by SPILL_OUT creation time.

    The m-th record corresponds to node ids N+2m and N+2m+1 (zero-based m).
    new_offset is the target cache offset used by the matching SPILL_IN.
    """

    buf_id: int
    new_offset: int


@dataclass(frozen=True, slots=True)
class Q2Solution:
    schedule: tuple[int, ...]
    initial_offsets: dict[int, int]
    spills: tuple[SpillRecord, ...]


def copy_in_backed_buffers(graph: ComputeGraph) -> frozenset[int]:
    return frozenset(
        buf_id
        for node in graph.nodes.values()
        if node.op == "COPY_IN"
        for buf_id in node.bufs
    )


def is_copy_in_backed(graph: ComputeGraph, buf_id: int) -> bool:
    return buf_id in copy_in_backed_buffers(graph)


def spill_traffic_cost(graph: ComputeGraph, buf_id: int) -> int:
    alloc = graph.alloc_node_for_buffer(buf_id)
    if alloc is None or alloc.size is None:
        raise ValueError(f"unknown buffer {buf_id}")
    return alloc.size if is_copy_in_backed(graph, buf_id) else 2 * alloc.size


def spill_cycles(graph: ComputeGraph, buf_id: int) -> tuple[int, int]:
    """Return (SPILL_OUT cycles, SPILL_IN cycles) from Appendix D."""

    alloc = graph.alloc_node_for_buffer(buf_id)
    if alloc is None or alloc.size is None:
        raise ValueError(f"unknown buffer {buf_id}")
    transfer_cycles = 2 * alloc.size + 150
    if is_copy_in_backed(graph, buf_id):
        return 0, transfer_cycles
    return transfer_cycles, transfer_cycles


def spill_node_ids(graph: ComputeGraph, spill_index: int) -> tuple[int, int]:
    if spill_index < 0:
        raise ValueError("spill_index must be non-negative")
    n = graph.node_count
    return n + 2 * spill_index, n + 2 * spill_index + 1


def make_spill_nodes(graph: ComputeGraph, spill_index: int, buf_id: int) -> tuple[Node, Node]:
    out_id, in_id = spill_node_ids(graph, spill_index)
    out_cycles, in_cycles = spill_cycles(graph, buf_id)
    return (
        Node(out_id, "SPILL_OUT", pipe="MTE3", cycles=out_cycles, bufs=(buf_id,)),
        Node(in_id, "SPILL_IN", pipe="MTE2", cycles=in_cycles, bufs=(buf_id,)),
    )
