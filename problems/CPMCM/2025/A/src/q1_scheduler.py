from __future__ import annotations

import heapq
from dataclasses import dataclass

from evaluator import Q1Evaluation, evaluate_q1
from model import ComputeGraph, L0_TYPES, Q1_COUNTED_TYPES


@dataclass(frozen=True, slots=True)
class Q1ScheduleResult:
    order: tuple[int, ...]
    evaluation: Q1Evaluation


def _memory_delta(graph: ComputeGraph, node_id: int) -> int:
    node = graph.nodes[node_id]
    if node.memory_type not in Q1_COUNTED_TYPES or node.size is None:
        return 0
    if node.is_alloc:
        return node.size
    if node.is_free:
        return -node.size
    return 0


def _ready_key(graph: ComputeGraph, node_id: int) -> tuple[int, int, int]:
    node = graph.nodes[node_id]
    delta = _memory_delta(graph, node_id)
    # Deterministic baseline: FREE first, neutral work second, counted-memory ALLOC last.
    # Within a class prefer the action with the most favorable immediate memory delta,
    # then node id for reproducibility.
    if delta < 0:
        cls = 0
    elif delta == 0:
        cls = 1
    else:
        cls = 2
    return (cls, delta, node.id)


def schedule_q1_baseline(graph: ComputeGraph) -> Q1ScheduleResult:
    indegree = graph.indegrees()

    # A blocked L0 ALLOC must not be repeatedly popped and pushed on every scheduling
    # step. Keep each L0 type in its own ready heap and only expose its minimum node
    # while that L0 type is free. This keeps the baseline near O((V+E) log V) even
    # when many independent L0 allocations are simultaneously ready.
    ready: list[tuple[tuple[int, int, int], int]] = []
    l0_alloc_ready: dict[str, list[int]] = {kind: [] for kind in L0_TYPES}
    l0_live: dict[str, int] = {kind: 0 for kind in L0_TYPES}

    def enqueue(node_id: int) -> None:
        node = graph.nodes[node_id]
        if node.is_alloc and node.memory_type in L0_TYPES:
            heapq.heappush(l0_alloc_ready[node.memory_type], node_id)
        else:
            heapq.heappush(ready, (_ready_key(graph, node_id), node_id))

    for node_id, degree in indegree.items():
        if degree == 0:
            enqueue(node_id)

    order: list[int] = []
    while len(order) < graph.node_count:
        candidates: list[tuple[tuple[int, int, int], str | None, int]] = []
        if ready:
            key, node_id = ready[0]
            candidates.append((key, None, node_id))
        for memory_type, heap in l0_alloc_ready.items():
            if heap and l0_live[memory_type] == 0:
                node_id = heap[0]
                candidates.append(((1, 0, node_id), memory_type, node_id))

        if not candidates:
            unresolved = [node_id for node_id, degree in indegree.items() if degree > 0]
            blocked = {
                memory_type: heap[:8]
                for memory_type, heap in l0_alloc_ready.items()
                if heap
            }
            if unresolved:
                raise ValueError(f"graph is cyclic or unschedulable; unresolved={unresolved[:8]}")
            raise ValueError(f"no Q1-feasible ready node under L0 constraint; blocked={blocked}")

        _, l0_type, chosen = min(candidates, key=lambda item: item[0])
        if l0_type is None:
            _, popped = heapq.heappop(ready)
            assert popped == chosen
        else:
            popped = heapq.heappop(l0_alloc_ready[l0_type])
            assert popped == chosen

        node = graph.nodes[chosen]
        order.append(chosen)
        if node.is_alloc and node.memory_type in L0_TYPES:
            l0_live[node.memory_type] += 1
        elif node.is_free and node.memory_type in L0_TYPES:
            l0_live[node.memory_type] -= 1
            if l0_live[node.memory_type] < 0:
                raise ValueError(f"FREE for {node.memory_type} before a live allocation at node {chosen}")

        for nxt in graph.successors[chosen]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                enqueue(nxt)

    evaluation = evaluate_q1(graph, order)
    if not evaluation.valid:
        raise ValueError(f"scheduler emitted invalid order: {evaluation.errors}")
    return Q1ScheduleResult(tuple(order), evaluation)
