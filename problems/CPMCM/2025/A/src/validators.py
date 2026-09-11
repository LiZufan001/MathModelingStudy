from __future__ import annotations

from dataclasses import dataclass

from model import ComputeGraph, L0_TYPES


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    errors: tuple[str, ...]

    def require_ok(self) -> None:
        if not self.ok:
            raise ValueError("; ".join(self.errors))


def validate_topological_order(graph: ComputeGraph, order: list[int] | tuple[int, ...]) -> ValidationResult:
    errors: list[str] = []
    if len(order) != graph.node_count:
        errors.append(f"order length {len(order)} != node count {graph.node_count}")
    if len(set(order)) != len(order):
        errors.append("order contains duplicate node ids")
    unknown = [node_id for node_id in order if node_id not in graph.nodes]
    if unknown:
        errors.append(f"order references unknown node ids: {unknown[:8]}")
    missing = set(graph.nodes) - set(order)
    if missing:
        errors.append(f"order misses node ids: {sorted(missing)[:8]}")
    if errors:
        return ValidationResult(False, tuple(errors))

    pos = {node_id: idx for idx, node_id in enumerate(order)}
    for u, succs in graph.successors.items():
        for v in succs:
            if pos[u] >= pos[v]:
                errors.append(f"dependency violated: {u} must precede {v}")
                if len(errors) >= 20:
                    return ValidationResult(False, tuple(errors))
    return ValidationResult(not errors, tuple(errors))


def validate_buffer_lifetimes(graph: ComputeGraph, order: list[int] | tuple[int, ...]) -> ValidationResult:
    topo = validate_topological_order(graph, order)
    if not topo.ok:
        return topo

    errors: list[str] = []
    live: dict[int, int] = {}
    l0_live: dict[str, int] = {kind: 0 for kind in L0_TYPES}

    for node_id in order:
        node = graph.nodes[node_id]
        if node.is_alloc:
            if node.buf_id is None or node.memory_type is None:
                errors.append(f"ALLOC node {node_id} is missing BufId/Type")
            else:
                if node.buf_id in live:
                    errors.append(f"buffer {node.buf_id} allocated while already live")
                live[node.buf_id] = node_id
                if node.memory_type in L0_TYPES:
                    l0_live[node.memory_type] += 1
                    if l0_live[node.memory_type] > 1:
                        errors.append(f"{node.memory_type} has >1 live buffer at node {node_id}")

        elif node.is_free:
            if node.buf_id is None or node.memory_type is None:
                errors.append(f"FREE node {node_id} is missing BufId/Type")
            else:
                if node.buf_id not in live:
                    errors.append(f"buffer {node.buf_id} freed before allocation / after prior free")
                else:
                    live.pop(node.buf_id)
                if node.memory_type in L0_TYPES:
                    l0_live[node.memory_type] -= 1
                    if l0_live[node.memory_type] < 0:
                        errors.append(f"{node.memory_type} live count became negative at node {node_id}")

        else:
            # Bufs is part of the official operation-node description. Checking only
            # graph edges is not enough for an independent oracle: every referenced
            # buffer must actually be resident throughout the operation's schedule point.
            for buf_id in node.bufs:
                if buf_id not in live:
                    errors.append(f"node {node_id} references buffer {buf_id} while it is not live")
                    if len(errors) >= 20:
                        break

        if len(errors) >= 20:
            break

    if live:
        errors.append(f"buffers still live at end: {sorted(live)[:8]}")
    return ValidationResult(not errors, tuple(errors))
