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
    if delta < 0:
        cls = 0
    elif delta == 0:
        cls = 1
    else:
        cls = 2
    return (cls, delta, node.id)


def schedule_q1_baseline(graph: ComputeGraph) -> Q1ScheduleResult:
    indegree = graph.indegrees()
    ready: list[tuple[tuple[int, int, int], int]] = []
    for node_id, degree in indegree.items():
        if degree == 0:
            heapq.heappush(ready, (_ready_key(graph, node_id), node_id))

    order: list[int] = []
    l0_live: dict[str, int] = {kind: 0 for kind in L0_TYPES}

    while ready:
        deferred: list[tuple[tuple[int, int, int], int]] = []
        chosen: int | None = None
        while ready:
            item = heapq.heappop(ready)
            node_id = item[1]
            node = graph.nodes[node_id]
            if node.is_alloc and node.memory_type in L0_TYPES and l0_live[node.memory_type] >= 1:
                deferred.append(item)
                continue
            chosen = node_id
            break
        for item in deferred:
            heapq.heappush(ready, item)

        if chosen is None:
            blocked = [node_id for _, node_id in ready]
            raise ValueError(f"no Q1-feasible ready node under L0 constraint; blocked={blocked[:8]}")

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
                heapq.heappush(ready, (_ready_key(graph, nxt), nxt))

    if len(order) != graph.node_count:
        unresolved = [node_id for node_id, degree in indegree.items() if degree > 0]
        raise ValueError(f"graph is cyclic or unschedulable; unresolved={unresolved[:8]}")

    evaluation = evaluate_q1(graph, order)
    if not evaluation.valid:
        raise ValueError(f"scheduler emitted invalid order: {evaluation.errors}")
    return Q1ScheduleResult(tuple(order), evaluation)
