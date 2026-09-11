from __future__ import annotations

from dataclasses import dataclass

from evaluator import Q1Evaluation, evaluate_q1
from model import ComputeGraph, L0_TYPES, Q1_COUNTED_TYPES


@dataclass(frozen=True, slots=True)
class Q1ExactResult:
    order: tuple[int, ...]
    evaluation: Q1Evaluation
    explored_states: int


def _memory_delta(graph: ComputeGraph, node_id: int) -> int:
    node = graph.nodes[node_id]
    if node.memory_type not in Q1_COUNTED_TYPES or node.size is None:
        return 0
    if node.is_alloc:
        return node.size
    if node.is_free:
        return -node.size
    return 0


def solve_q1_exact(graph: ComputeGraph, *, max_nodes: int = 18) -> Q1ExactResult:
    """Exhaustively solve small Q1 instances with branch-and-bound + mask dominance.

    The oracle is intentionally limited to small graphs. A search state is the set of
    already scheduled nodes. For a fixed set, current L1/UB residency, live buffers and
    L0 occupancy are uniquely determined; therefore a prefix reaching the same mask with
    a larger/equal peak can never lead to a better completion and is safely dominated.
    """

    if graph.node_count > max_nodes:
        raise ValueError(
            f"exact Q1 solver is limited to {max_nodes} nodes, got {graph.node_count}; "
            "use it as a small-instance oracle, not on Appendix-E full cases"
        )

    node_ids = tuple(sorted(graph.nodes))
    index_of = {node_id: idx for idx, node_id in enumerate(node_ids)}
    n = len(node_ids)
    full_mask = (1 << n) - 1

    pred_masks: list[int] = []
    for node_id in node_ids:
        mask = 0
        for pred in graph.predecessors[node_id]:
            mask |= 1 << index_of[pred]
        pred_masks.append(mask)

    deltas = [_memory_delta(graph, node_id) for node_id in node_ids]

    best_peak: int | None = None
    best_order: tuple[int, ...] | None = None
    best_prefix_peak: dict[int, int] = {}
    explored_states = 0

    live_buffers: set[int] = set()
    l0_live: dict[str, int] = {kind: 0 for kind in L0_TYPES}
    order: list[int] = []

    def feasible(idx: int, mask: int) -> bool:
        if pred_masks[idx] & ~mask:
            return False
        node = graph.nodes[node_ids[idx]]
        if node.is_alloc:
            if node.buf_id is None or node.memory_type is None:
                return False
            if node.buf_id in live_buffers:
                return False
            if node.memory_type in L0_TYPES and l0_live[node.memory_type] != 0:
                return False
            return True
        if node.is_free:
            return node.buf_id is not None and node.buf_id in live_buffers
        return all(buf_id in live_buffers for buf_id in node.bufs)

    def candidate_key(idx: int) -> tuple[int, int, int]:
        node = graph.nodes[node_ids[idx]]
        delta = deltas[idx]
        if node.is_free:
            cls = 0
        elif not node.is_alloc:
            cls = 1
        else:
            cls = 2
        return (cls, delta, node.id)

    def dfs(mask: int, resident: int, peak: int) -> None:
        nonlocal best_peak, best_order, explored_states

        if best_peak is not None and peak >= best_peak:
            return
        seen_peak = best_prefix_peak.get(mask)
        if seen_peak is not None and peak >= seen_peak:
            return
        best_prefix_peak[mask] = peak
        explored_states += 1

        if mask == full_mask:
            candidate = tuple(order)
            evaluation = evaluate_q1(graph, candidate)
            if not evaluation.valid:
                return
            if evaluation.peak_residency != peak:
                raise AssertionError(
                    f"exact-search peak {peak} disagrees with independent evaluator "
                    f"{evaluation.peak_residency}"
                )
            best_peak = peak
            best_order = candidate
            return

        candidates = [idx for idx in range(n) if not (mask >> idx) & 1 and feasible(idx, mask)]
        candidates.sort(key=candidate_key)

        for idx in candidates:
            node_id = node_ids[idx]
            node = graph.nodes[node_id]
            new_resident = resident + deltas[idx]
            if new_resident < 0:
                continue
            new_peak = max(peak, new_resident)
            if best_peak is not None and new_peak >= best_peak:
                continue

            changed_l0: str | None = None
            if node.is_alloc:
                assert node.buf_id is not None and node.memory_type is not None
                live_buffers.add(node.buf_id)
                if node.memory_type in L0_TYPES:
                    l0_live[node.memory_type] += 1
                    changed_l0 = node.memory_type
            elif node.is_free:
                assert node.buf_id is not None and node.memory_type is not None
                live_buffers.remove(node.buf_id)
                if node.memory_type in L0_TYPES:
                    l0_live[node.memory_type] -= 1
                    changed_l0 = node.memory_type

            order.append(node_id)
            dfs(mask | (1 << idx), new_resident, new_peak)
            order.pop()

            if node.is_alloc:
                assert node.buf_id is not None
                live_buffers.remove(node.buf_id)
                if changed_l0 is not None:
                    l0_live[changed_l0] -= 1
            elif node.is_free:
                assert node.buf_id is not None
                live_buffers.add(node.buf_id)
                if changed_l0 is not None:
                    l0_live[changed_l0] += 1

    dfs(0, 0, 0)

    if best_order is None:
        raise ValueError("no schedule satisfies DAG, buffer-liveness and L0 constraints")

    evaluation = evaluate_q1(graph, best_order)
    if not evaluation.valid:
        raise AssertionError(f"exact solver returned invalid order: {evaluation.errors}")
    return Q1ExactResult(best_order, evaluation, explored_states)
