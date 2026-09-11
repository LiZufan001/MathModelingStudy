from __future__ import annotations

import heapq
from dataclasses import dataclass

from evaluator import Q1Evaluation, evaluate_q1
from model import ComputeGraph, L0_TYPES, Q1_COUNTED_TYPES

INF_DISTANCE = 10**9


@dataclass(frozen=True, slots=True)
class ReleaseHint:
    distance: int
    size: int
    free_node_id: int


@dataclass(frozen=True, slots=True)
class Q1PressureResult:
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


def _plain_topological_order(graph: ComputeGraph) -> tuple[int, ...]:
    indegree = graph.indegrees()
    ready = [node_id for node_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    order: list[int] = []
    while ready:
        node_id = heapq.heappop(ready)
        order.append(node_id)
        for nxt in graph.successors[node_id]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                heapq.heappush(ready, nxt)
    if len(order) != graph.node_count:
        raise ValueError("graph contains a cycle")
    return tuple(order)


def _choose_hint(a: ReleaseHint | None, b: ReleaseHint | None) -> ReleaseHint | None:
    if a is None:
        return b
    if b is None:
        return a
    # Prefer a release that is topologically nearer; for equal distance prefer the
    # larger counted-memory release, then smaller node id for determinism.
    if (b.distance, -b.size, b.free_node_id) < (a.distance, -a.size, a.free_node_id):
        return b
    return a


def _release_hints(graph: ComputeGraph) -> tuple[dict[int, ReleaseHint | None], dict[int, int]]:
    topo = _plain_topological_order(graph)
    counted: dict[int, ReleaseHint | None] = {node_id: None for node_id in graph.nodes}
    l0_distance: dict[int, int] = {node_id: INF_DISTANCE for node_id in graph.nodes}

    for node_id in reversed(topo):
        node = graph.nodes[node_id]
        best_counted: ReleaseHint | None = None
        best_l0 = INF_DISTANCE

        if node.is_free and node.memory_type in Q1_COUNTED_TYPES and node.size is not None:
            best_counted = ReleaseHint(0, node.size, node.id)
        if node.is_free and node.memory_type in L0_TYPES:
            best_l0 = 0

        for succ in graph.successors[node_id]:
            hint = counted[succ]
            if hint is not None:
                best_counted = _choose_hint(
                    best_counted,
                    ReleaseHint(hint.distance + 1, hint.size, hint.free_node_id),
                )
            if l0_distance[succ] < INF_DISTANCE:
                best_l0 = min(best_l0, l0_distance[succ] + 1)

        counted[node_id] = best_counted
        l0_distance[node_id] = best_l0

    return counted, l0_distance


def _build_priority_keys(graph: ComputeGraph) -> dict[int, tuple[int, ...]]:
    counted_hint, l0_distance = _release_hints(graph)
    keys: dict[int, tuple[int, ...]] = {}

    for node_id, node in graph.nodes.items():
        direct_counted_release = 0
        direct_l0_release = 0
        for succ_id in graph.successors[node_id]:
            succ = graph.nodes[succ_id]
            if succ.is_free and succ.memory_type in Q1_COUNTED_TYPES and succ.size is not None:
                direct_counted_release += succ.size
            elif succ.is_free and succ.memory_type in L0_TYPES:
                direct_l0_release += 1

        hint = counted_hint[node_id]
        hint_distance = INF_DISTANCE if hint is None else hint.distance
        hint_size = 0 if hint is None else hint.size
        l0_dist = l0_distance[node_id]
        delta = _memory_delta(graph, node_id)

        if node.is_free:
            # Ready FREE nodes are dominance-safe for Q1: executing them immediately
            # cannot raise peak residency and can only release memory/resource state.
            counted_release = -delta if delta < 0 else 0
            l0_release = 1 if node.memory_type in L0_TYPES else 0
            keys[node_id] = (0, -counted_release, -l0_release, node.id)
        elif not node.is_alloc:
            # Neutral operations do not alter residency. Prefer work that lies closer
            # to a counted-memory FREE, with L0 release and direct unlocks as tie-breakers.
            keys[node_id] = (
                1,
                hint_distance,
                -hint_size,
                l0_dist,
                -direct_counted_release,
                -direct_l0_release,
                node.id,
            )
        else:
            # All ALLOCs are delayed until no FREE/neutral work is available. Among
            # allocations, immediate L1/UB pressure remains the primary criterion;
            # downstream release hints only break ties, so this policy stays conservative.
            keys[node_id] = (
                2,
                max(delta, 0),
                hint_distance,
                -hint_size,
                l0_dist,
                -direct_counted_release,
                -direct_l0_release,
                node.id,
            )

    return keys


def schedule_q1_pressure(graph: ComputeGraph) -> Q1PressureResult:
    """Deterministic Q1 heuristic with downstream release pressure.

    This is deliberately not presented as an exact algorithm. It preserves the hard
    DAG/L0 constraints, delays all ALLOCs behind ready FREE/neutral work, and uses only
    static, explainable downstream-release features for allocation tie-breaking.
    Every emitted order is independently revalidated by ``evaluate_q1``.
    """

    keys = _build_priority_keys(graph)
    indegree = graph.indegrees()
    ready: list[tuple[tuple[int, ...], int]] = []
    l0_alloc_ready: dict[str, list[tuple[tuple[int, ...], int]]] = {kind: [] for kind in L0_TYPES}
    l0_live: dict[str, int] = {kind: 0 for kind in L0_TYPES}
    live_buffers: set[int] = set()

    def enqueue(node_id: int) -> None:
        node = graph.nodes[node_id]
        entry = (keys[node_id], node_id)
        if node.is_alloc and node.memory_type in L0_TYPES:
            heapq.heappush(l0_alloc_ready[node.memory_type], entry)
        else:
            heapq.heappush(ready, entry)

    for node_id, degree in indegree.items():
        if degree == 0:
            enqueue(node_id)

    order: list[int] = []
    while len(order) < graph.node_count:
        candidates: list[tuple[tuple[int, ...], str | None, int]] = []
        if ready:
            key, node_id = ready[0]
            candidates.append((key, None, node_id))
        for memory_type, heap in l0_alloc_ready.items():
            if heap and l0_live[memory_type] == 0:
                key, node_id = heap[0]
                candidates.append((key, memory_type, node_id))

        if not candidates:
            unresolved = [node_id for node_id, degree in indegree.items() if degree > 0]
            blocked = {
                memory_type: [node_id for _, node_id in heap[:8]]
                for memory_type, heap in l0_alloc_ready.items()
                if heap
            }
            if unresolved:
                raise ValueError(f"graph is cyclic or Q1-unschedulable; unresolved={unresolved[:8]}")
            raise ValueError(f"no Q1-feasible ready node under L0 constraint; blocked={blocked}")

        _, l0_type, chosen = min(candidates, key=lambda item: item[0])
        if l0_type is None:
            _, popped = heapq.heappop(ready)
            if popped != chosen:
                raise AssertionError("ready heap corruption")
        else:
            _, popped = heapq.heappop(l0_alloc_ready[l0_type])
            if popped != chosen:
                raise AssertionError("L0 ready heap corruption")

        node = graph.nodes[chosen]
        if node.is_alloc:
            if node.buf_id is None or node.memory_type is None:
                raise ValueError(f"ALLOC node {chosen} missing buffer metadata")
            if node.buf_id in live_buffers:
                raise ValueError(f"buffer {node.buf_id} allocated twice before FREE")
            live_buffers.add(node.buf_id)
            if node.memory_type in L0_TYPES:
                l0_live[node.memory_type] += 1
                if l0_live[node.memory_type] > 1:
                    raise AssertionError(f"{node.memory_type} occupancy exceeded one")
        elif node.is_free:
            if node.buf_id is None or node.memory_type is None or node.buf_id not in live_buffers:
                raise ValueError(f"ready FREE node {chosen} has no live buffer")
            live_buffers.remove(node.buf_id)
            if node.memory_type in L0_TYPES:
                l0_live[node.memory_type] -= 1
                if l0_live[node.memory_type] < 0:
                    raise AssertionError(f"{node.memory_type} occupancy became negative")
        else:
            missing = [buf_id for buf_id in node.bufs if buf_id not in live_buffers]
            if missing:
                raise ValueError(
                    f"ready operation node {chosen} references non-live buffers {missing[:8]}; "
                    "input dependencies are insufficient for a valid Q1 schedule"
                )

        order.append(chosen)
        for nxt in graph.successors[chosen]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                enqueue(nxt)

    evaluation = evaluate_q1(graph, order)
    if not evaluation.valid:
        raise ValueError(f"pressure scheduler emitted invalid order: {evaluation.errors}")
    return Q1PressureResult(tuple(order), evaluation)
