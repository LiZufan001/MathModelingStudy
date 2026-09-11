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


class _L0PrerequisiteAnalyzer:
    """Find same-L0 allocations that must finish before a candidate can start.

    For an L0 allocation A, walk backward from FREE(A). Whenever the walk first hits
    another allocation B of the same L0 type on a predecessor path, B is a hard
    prerequisite: if A were allocated before B had completed, B could never acquire
    the single slot needed to make FREE(A) reachable. We stop that path at B because
    B's own prerequisites are handled when B itself is scheduled.

    The result is static for a graph and cached per allocation. This is a correctness
    guard, not a heuristic score.
    """

    def __init__(self, graph: ComputeGraph) -> None:
        self.graph = graph
        self._cache: dict[int, frozenset[int]] = {}

    def prerequisites(self, alloc_node_id: int) -> frozenset[int]:
        cached = self._cache.get(alloc_node_id)
        if cached is not None:
            return cached

        alloc = self.graph.nodes[alloc_node_id]
        if not alloc.is_alloc or alloc.memory_type not in L0_TYPES or alloc.buf_id is None:
            raise ValueError(f"node {alloc_node_id} is not a valid L0 ALLOC")
        free = self.graph.free_node_for_buffer(alloc.buf_id)
        if free is None:
            raise ValueError(f"L0 buffer {alloc.buf_id} has no matching FREE node")

        required: set[int] = set()
        seen: set[int] = set()
        stack = list(self.graph.predecessors[free.id])
        while stack:
            node_id = stack.pop()
            if node_id in seen:
                continue
            seen.add(node_id)
            if node_id == alloc_node_id:
                # This predecessor path is already rooted in the candidate's own
                # lifetime and therefore introduces no competing L0 allocation.
                continue

            node = self.graph.nodes[node_id]
            if node.is_alloc and node.memory_type == alloc.memory_type:
                required.add(node_id)
                # Stop this predecessor path at the nearest same-type L0 ALLOC.
                continue
            stack.extend(self.graph.predecessors[node_id])

        result = frozenset(required)
        self._cache[alloc_node_id] = result
        return result


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
            counted_release = -delta if delta < 0 else 0
            l0_release = 1 if node.memory_type in L0_TYPES else 0
            keys[node_id] = (0, -counted_release, -l0_release, node.id)
        elif not node.is_alloc:
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
            # ALLOCs remain below all ready FREE/neutral work. Immediate L1/UB
            # pressure is primary; static release information is only a tie-breaker.
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
    """Deterministic Q1 heuristic with hard L0 prerequisite safety.

    The ranking is heuristic, but feasibility is not: DAG dependencies, buffer
    liveness, one-live-buffer-per-L0-type, and transitive same-L0 prerequisites are
    enforced explicitly. The completed schedule is independently checked again by
    ``evaluate_q1``.
    """

    keys = _build_priority_keys(graph)
    l0_prereqs = _L0PrerequisiteAnalyzer(graph)
    indegree = graph.indegrees()

    ready: list[tuple[tuple[int, ...], int]] = []
    l0_safe_ready: dict[str, list[tuple[tuple[int, ...], int]]] = {
        kind: [] for kind in L0_TYPES
    }
    l0_live: dict[str, int] = {kind: 0 for kind in L0_TYPES}
    active_l0_alloc: dict[str, int | None] = {kind: None for kind in L0_TYPES}
    completed_l0_allocs: dict[str, set[int]] = {kind: set() for kind in L0_TYPES}

    # A ready L0 ALLOC whose hard prerequisites are incomplete waits here. Each
    # prerequisite completion decrements its counter exactly once, so blocked nodes
    # are not repeatedly scanned on every scheduling step.
    remaining_prereqs: dict[int, int] = {}
    waiting_by_prereq: dict[int, list[int]] = {}
    blocked_type: dict[int, str] = {}

    live_buffers: set[int] = set()

    def register_l0_ready(node_id: int) -> None:
        node = graph.nodes[node_id]
        if not node.is_alloc or node.memory_type not in L0_TYPES:
            raise AssertionError("register_l0_ready called for non-L0 ALLOC")
        memory_type = node.memory_type
        required = l0_prereqs.prerequisites(node_id)
        missing = [
            prerequisite
            for prerequisite in required
            if prerequisite not in completed_l0_allocs[memory_type]
        ]
        if not missing:
            heapq.heappush(l0_safe_ready[memory_type], (keys[node_id], node_id))
            return

        remaining_prereqs[node_id] = len(missing)
        blocked_type[node_id] = memory_type
        for prerequisite in missing:
            waiting_by_prereq.setdefault(prerequisite, []).append(node_id)

    def enqueue(node_id: int) -> None:
        node = graph.nodes[node_id]
        if node.is_alloc and node.memory_type in L0_TYPES:
            register_l0_ready(node_id)
        else:
            heapq.heappush(ready, (keys[node_id], node_id))

    def mark_l0_completed(alloc_node_id: int, memory_type: str) -> None:
        if alloc_node_id in completed_l0_allocs[memory_type]:
            raise AssertionError(f"L0 allocation {alloc_node_id} completed twice")
        completed_l0_allocs[memory_type].add(alloc_node_id)

        for blocked_id in waiting_by_prereq.pop(alloc_node_id, []):
            remaining = remaining_prereqs.get(blocked_id)
            if remaining is None:
                raise AssertionError(f"missing prerequisite counter for blocked node {blocked_id}")
            remaining -= 1
            if remaining < 0:
                raise AssertionError(f"negative prerequisite counter for blocked node {blocked_id}")
            if remaining == 0:
                remaining_prereqs.pop(blocked_id)
                blocked_memory_type = blocked_type.pop(blocked_id)
                heapq.heappush(
                    l0_safe_ready[blocked_memory_type],
                    (keys[blocked_id], blocked_id),
                )
            else:
                remaining_prereqs[blocked_id] = remaining

    for node_id, degree in indegree.items():
        if degree == 0:
            enqueue(node_id)

    order: list[int] = []
    while len(order) < graph.node_count:
        candidates: list[tuple[tuple[int, ...], str | None, int]] = []
        if ready:
            key, node_id = ready[0]
            candidates.append((key, None, node_id))
        for memory_type, heap in l0_safe_ready.items():
            if heap and l0_live[memory_type] == 0:
                key, node_id = heap[0]
                candidates.append((key, memory_type, node_id))

        if not candidates:
            unresolved = [node_id for node_id, degree in indegree.items() if degree > 0]
            blocked = sorted(remaining_prereqs.items(), key=lambda item: item[0])[:8]
            if unresolved:
                raise ValueError(
                    "graph is cyclic or Q1-unschedulable after L0 prerequisite analysis; "
                    f"unresolved={unresolved[:8]}, blocked_l0={blocked}"
                )
            raise ValueError(
                "no Q1-feasible ready node under L0 constraint; "
                f"blocked_l0={blocked}"
            )

        _, l0_type, chosen = min(candidates, key=lambda item: item[0])
        if l0_type is None:
            _, popped = heapq.heappop(ready)
            if popped != chosen:
                raise AssertionError("ready heap corruption")
        else:
            _, popped = heapq.heappop(l0_safe_ready[l0_type])
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
                if l0_live[node.memory_type] != 0 or active_l0_alloc[node.memory_type] is not None:
                    raise AssertionError(f"{node.memory_type} allocated while already occupied")
                l0_live[node.memory_type] = 1
                active_l0_alloc[node.memory_type] = chosen

        elif node.is_free:
            if node.buf_id is None or node.memory_type is None or node.buf_id not in live_buffers:
                raise ValueError(f"ready FREE node {chosen} has no live buffer")
            live_buffers.remove(node.buf_id)
            if node.memory_type in L0_TYPES:
                alloc = graph.alloc_node_for_buffer(node.buf_id)
                if alloc is None:
                    raise ValueError(f"L0 FREE node {chosen} has no matching ALLOC")
                if active_l0_alloc[node.memory_type] != alloc.id:
                    raise AssertionError(
                        f"{node.memory_type} FREE {chosen} does not match active ALLOC "
                        f"{active_l0_alloc[node.memory_type]}"
                    )
                l0_live[node.memory_type] = 0
                active_l0_alloc[node.memory_type] = None
                mark_l0_completed(alloc.id, node.memory_type)

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
            if indegree[nxt] < 0:
                raise AssertionError(f"negative indegree for node {nxt}")
            if indegree[nxt] == 0:
                enqueue(nxt)

    evaluation = evaluate_q1(graph, order)
    if not evaluation.valid:
        raise ValueError(f"pressure scheduler emitted invalid order: {evaluation.errors}")
    return Q1PressureResult(tuple(order), evaluation)
