from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass

from evaluator import Q1Evaluation, evaluate_q1
from model import ComputeGraph, L0_TYPES, Q1_COUNTED_TYPES
from q1_scheduler import _ready_key


@dataclass(frozen=True, slots=True)
class Q2ReuseScheduleConfig:
    """Configuration for the experimental Q2-aware topological scheduler.

    The scheduler remains operator-agnostic: it never inspects Matmul/Conv/FA
    structure.  It only uses DAG readiness, official buffer metadata, recent
    L1/UB reuse, and bytes that become immediately releasable.
    """

    hot_window: int = 8
    release_weight: int = 1
    probe_per_buffer: int = 8

    def __post_init__(self) -> None:
        if self.hot_window <= 0:
            raise ValueError("hot_window must be positive")
        if self.release_weight < 0:
            raise ValueError("release_weight must be non-negative")
        if self.probe_per_buffer <= 0:
            raise ValueError("probe_per_buffer must be positive")


@dataclass(frozen=True, slots=True)
class Q2ReuseScheduleResult:
    order: tuple[int, ...]
    evaluation: Q1Evaluation
    config: Q2ReuseScheduleConfig
    affinity_decisions: int


def _counted_buffer_sizes(graph: ComputeGraph) -> dict[int, int]:
    result: dict[int, int] = {}
    for node in graph.nodes.values():
        if (
            node.is_alloc
            and node.buf_id is not None
            and node.memory_type in Q1_COUNTED_TYPES
            and node.size is not None
            and node.size > 0
        ):
            result[node.buf_id] = node.size
    return result


def schedule_q2_reuse_aware(
    graph: ComputeGraph,
    config: Q2ReuseScheduleConfig = Q2ReuseScheduleConfig(),
) -> Q2ReuseScheduleResult:
    """Generate a Q1-valid order biased toward Q2 cache reuse.

    This is deliberately an experimental companion to ``schedule_q1_baseline``.
    It preserves the same hard L0 single-live-buffer rule and the same FREE-first
    fallback ordering.  When several neutral ready operations are available, it
    prefers operations that touch recently used L1/UB buffers and operations that
    make a counted-buffer FREE immediately ready.

    Candidate probing is bounded by ``hot_window * probe_per_buffer`` rather than
    scanning the whole ready frontier on every node, which keeps the large official
    graphs practical.
    """

    indegree = graph.indegrees()
    counted_sizes = _counted_buffer_sizes(graph)

    regular_ready: set[int] = set()
    regular_heap: list[tuple[tuple[int, int, int], int]] = []
    l0_ready: dict[str, list[int]] = {kind: [] for kind in L0_TYPES}
    l0_live: dict[str, int] = {kind: 0 for kind in L0_TYPES}

    # Only currently-ready non-memory operations are indexed here.  Removing a
    # selected node from the sets avoids stale affinity candidates.
    ready_by_buf: dict[int, set[int]] = {buf_id: set() for buf_id in counted_sizes}
    touched_by_node: dict[int, tuple[int, ...]] = {}
    for node_id, node in graph.nodes.items():
        if node.is_memory_event:
            continue
        touched = tuple(sorted({buf_id for buf_id in node.bufs if buf_id in counted_sizes}))
        if touched:
            touched_by_node[node_id] = touched

    def enqueue(node_id: int) -> None:
        node = graph.nodes[node_id]
        if node.is_alloc and node.memory_type in L0_TYPES:
            heapq.heappush(l0_ready[node.memory_type], node_id)
            return
        regular_ready.add(node_id)
        heapq.heappush(regular_heap, (_ready_key(graph, node_id), node_id))
        for buf_id in touched_by_node.get(node_id, ()):
            ready_by_buf[buf_id].add(node_id)

    for node_id, degree in indegree.items():
        if degree == 0:
            enqueue(node_id)

    hot_history: deque[tuple[int, ...]] = deque(maxlen=config.hot_window)
    order: list[int] = []
    affinity_decisions = 0

    def clean_regular_heap() -> None:
        while regular_heap and regular_heap[0][1] not in regular_ready:
            heapq.heappop(regular_heap)

    def fallback_candidate() -> int | None:
        clean_regular_heap()
        candidates: list[tuple[tuple[int, int, int], int]] = []
        if regular_heap:
            candidates.append(regular_heap[0])
        for memory_type, heap in l0_ready.items():
            if heap and l0_live[memory_type] == 0:
                node_id = heap[0]
                candidates.append((_ready_key(graph, node_id), node_id))
        if not candidates:
            return None
        return min(candidates)[1]

    def hot_scores() -> dict[int, int]:
        scores: dict[int, int] = {}
        # A buffer's most recent touch determines its recency score.  Repeated old
        # touches do not multiply the reward indefinitely.
        for age, touched in enumerate(reversed(hot_history), start=1):
            weight = config.hot_window - age + 1
            for buf_id in touched:
                scores.setdefault(buf_id, weight)
        return scores

    def release_bytes(node_id: int) -> int:
        total = 0
        for succ in graph.successors[node_id]:
            if indegree[succ] != 1:
                continue
            node = graph.nodes[succ]
            if (
                node.is_free
                and node.buf_id in counted_sizes
                and node.size is not None
            ):
                total += node.size
        return total

    while len(order) < graph.node_count:
        fallback = fallback_candidate()
        if fallback is None:
            unresolved = [node_id for node_id, degree in indegree.items() if degree > 0]
            blocked = {kind: heap[:8] for kind, heap in l0_ready.items() if heap}
            if unresolved:
                raise ValueError(f"graph is cyclic or unschedulable; unresolved={unresolved[:8]}")
            raise ValueError(f"no Q1-feasible ready node under L0 constraint; blocked={blocked}")

        # FREE remains a hard first priority, matching the stable Q1 baseline and
        # ensuring reuse scoring cannot artificially lengthen a lifetime once FREE
        # is already executable.
        if graph.nodes[fallback].is_free:
            chosen = fallback
        else:
            scores = hot_scores()
            candidates: set[int] = {fallback}
            for buf_id in scores:
                ready = ready_by_buf.get(buf_id)
                if not ready:
                    continue
                candidates.update(heapq.nsmallest(config.probe_per_buffer, ready))

            def candidate_key(node_id: int) -> tuple[int, tuple[int, int, int]]:
                affinity = sum(
                    counted_sizes[buf_id] * scores.get(buf_id, 0)
                    for buf_id in touched_by_node.get(node_id, ())
                )
                release = release_bytes(node_id)
                value = affinity + config.release_weight * release
                # Higher Q2-locality value wins; exact baseline key breaks ties so
                # the experiment is deterministic and degrades gracefully.
                return (-value, _ready_key(graph, node_id))

            chosen = min(candidates, key=candidate_key)
            if chosen != fallback:
                affinity_decisions += 1

        node = graph.nodes[chosen]
        if node.is_alloc and node.memory_type in L0_TYPES:
            memory_type = node.memory_type
            assert memory_type is not None
            popped = heapq.heappop(l0_ready[memory_type])
            if popped != chosen:
                raise AssertionError("L0 ready heap lost deterministic head")
            if l0_live[memory_type] != 0:
                raise ValueError(f"{memory_type} ALLOC chosen while another buffer is live")
            l0_live[memory_type] = 1
        else:
            if chosen not in regular_ready:
                raise AssertionError(f"chosen node {chosen} is not regular-ready")
            regular_ready.remove(chosen)
            for buf_id in touched_by_node.get(chosen, ()):
                ready_by_buf[buf_id].discard(chosen)
            if node.is_free and node.memory_type in L0_TYPES:
                memory_type = node.memory_type
                assert memory_type is not None
                l0_live[memory_type] -= 1
                if l0_live[memory_type] < 0:
                    raise ValueError(f"FREE for {memory_type} before a live allocation at node {chosen}")

        order.append(chosen)
        touched = touched_by_node.get(chosen)
        if touched:
            hot_history.append(touched)

        for succ in graph.successors[chosen]:
            indegree[succ] -= 1
            if indegree[succ] < 0:
                raise AssertionError(f"negative indegree for node {succ}")
            if indegree[succ] == 0:
                enqueue(succ)

    evaluation = evaluate_q1(graph, order)
    if not evaluation.valid:
        raise ValueError(f"reuse-aware scheduler emitted invalid order: {evaluation.errors}")
    return Q2ReuseScheduleResult(tuple(order), evaluation, config, affinity_decisions)
