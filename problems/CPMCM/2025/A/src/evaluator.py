from __future__ import annotations

from dataclasses import dataclass

from model import ComputeGraph, Q1_COUNTED_TYPES
from validators import validate_buffer_lifetimes


@dataclass(frozen=True, slots=True)
class Q1Evaluation:
    valid: bool
    peak_residency: int | None
    final_residency: int | None
    peak_position: int | None
    errors: tuple[str, ...]


def evaluate_q1(graph: ComputeGraph, order: list[int] | tuple[int, ...]) -> Q1Evaluation:
    validation = validate_buffer_lifetimes(graph, order)
    if not validation.ok:
        return Q1Evaluation(False, None, None, None, validation.errors)

    resident = 0
    peak = 0
    peak_pos = -1
    for pos, node_id in enumerate(order):
        node = graph.nodes[node_id]
        if node.memory_type in Q1_COUNTED_TYPES and node.size is not None:
            if node.is_alloc:
                resident += node.size
            elif node.is_free:
                resident -= node.size
                if resident < 0:
                    return Q1Evaluation(False, None, None, None, (f"negative Q1 residency at node {node_id}",))
        if resident > peak:
            peak = resident
            peak_pos = pos

    if resident != 0:
        return Q1Evaluation(False, None, resident, None, (f"non-zero final Q1 residency {resident}",))
    return Q1Evaluation(True, peak, resident, peak_pos, ())
