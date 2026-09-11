from __future__ import annotations

import heapq
from dataclasses import dataclass

from evaluator import Q1Evaluation, evaluate_q1
from model import ComputeGraph, L0_TYPES, Q1_COUNTED_TYPES
from q1_advanced import _L0PrerequisiteAnalyzer


@dataclass(frozen=True, slots=True)
class Q1FrontierResult:
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


def _frontier_key(graph: ComputeGraph, node_id: int, ready_epoch: int) -> tuple[int, ...]:
    node = graph.nodes[node_id]
    delta = _memory_delta(graph, node_id)

    if node.is_free:
        counted_release = -delta if delta < 0 else 0
        l0_release = 1 if node.memory_type in L0_TYPES else 0
        return (0, -counted_release, -l0_release, -ready_epoch, node.id)

    if not node.is_alloc:
        # Follow the newest frontier first. Operations touching more buffers are a
        # deterministic tie-breaker because they often sit near joins/last uses, but
        # this is only a heuristic feature; validity is enforced separately.
        return (1, -ready_epoch, -len(node.bufs), node.id)

    if node.memory_type in L0_TYPES:
        return (2, -ready_epoch, node.id)

    # For counted-memory allocations, branch continuity (newer frontier) is primary;
    # immediate allocation size is secondary. This deliberately explores a different
    # trade-off from the baseline's smallest-allocation-first rule.
    return (3, -ready_epoch, max(delta, 0), node.id)


def schedule_q1_frontier(graph: ComputeGraph) -> Q1FrontierResult:
    """Depth-first/frontier greedy scheduler with the same hard Q1 safety gates.

    Ready nodes remember the step at which they became ready. After all ready FREEs
    and neutral operations are exhausted, the policy prefers allocations from the most
    recently advanced branch. This can finish a local lifetime before opening many
    unrelated lifetimes. Same-L0 transitive prerequisites are enforced exactly as in
    the pressure scheduler, so the frontier preference cannot create an L0 deadlock.
    """

    l0_prereqs = _L0PrerequisiteAnalyzer(graph)
    indegree = graph.indegrees()
    ready: list[tuple[tuple[int, ...], int]] = []
    l0_safe_ready: dict[str, list[tuple[tuple[int, ...], int]]] = {
        kind: [] for kind in L0_TYPES
    }
    l0_live: dict[str, int] = {kind: 0 for kind in L0_TYPES}
    active_l0_alloc: dict[str, int | None] = {kind: None for kind in L0_TYPES}
    completed_l0_allocs: dict[str, set[int]] = {kind: set() for kind in L0_TYPES}

    remaining_prereqs: dict[int, int] = {}
    waiting_by_prereq: dict[int, list[int]] = {}
    blocked_type: dict[int, str] = {}
    blocked_epoch: dict[int, int] = {}

    live_buffers: set[int] = set()

    def register_l0_ready(node_id: int, epoch: int) -> None:
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
            heapq.heappush(
                l0_safe_ready[memory_type],
                (_frontier_key(graph, node_id, epoch), node_id),
            )
            return

        remaining_prereqs[node_id] = len(missing)
        blocked_type[node_id] = memory_type
        blocked_epoch[node_id] = epoch
        for prerequisite in missing:
            waiting_by_prereq.setdefault(prerequisite, []).append(node_id)

    def enqueue(node_id: int, epoch: int) -> None:
        node = graph.nodes[node_id]
        if node.is_alloc and node.memory_type in L0_TYPES:
            register_l0_ready(node_id, epoch)
        else:
            heapq.heappush(ready, (_frontier_key(graph, node_id, epoch), node_id))

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
                epoch = blocked_epoch.pop(blocked_id)
                heapq.heappush(
                    l0_safe_ready[blocked_memory_type],
                    (_frontier_key(graph, blocked_id, epoch), blocked_id),
                )
            else:
                remaining_prereqs[blocked_id] = remaining

    for node_id, degree in indegree.items():
        if degree == 0:
            enqueue(node_id, 0)

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
            raise ValueError(f"no Q1-feasible ready node under L0 constraint; blocked_l0={blocked}")

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
                    f"ready operation node {chosen} references non-live buffers {missing[:8]}"
                )

        order.append(chosen)
        epoch = len(order)
        for nxt in graph.successors[chosen]:
            indegree[nxt] -= 1
            if indegree[nxt] < 0:
                raise AssertionError(f"negative indegree for node {nxt}")
            if indegree[nxt] == 0:
                enqueue(nxt, epoch)

    evaluation = evaluate_q1(graph, order)
    if not evaluation.valid:
        raise ValueError(f"frontier scheduler emitted invalid order: {evaluation.errors}")
    return Q1FrontierResult(tuple(order), evaluation)
