from __future__ import annotations

import heapq
from collections import defaultdict, deque
from dataclasses import dataclass

from evaluator import Q1Evaluation, evaluate_q1
from model import ComputeGraph, L0_TYPES, Q1_COUNTED_TYPES
from q1_scheduler import _ready_key


@dataclass(frozen=True, slots=True)
class Q2ReuseScheduleConfig:
    """Configuration for the experimental Q2-aware topological scheduler."""

    hot_window: int = 8
    release_weight: int = 1
    probe_per_buffer: int = 8
    footprint_weight: int = 0
    footprint_min_buffers: int = 4

    def __post_init__(self) -> None:
        if self.hot_window <= 0:
            raise ValueError("hot_window must be positive")
        if self.release_weight < 0:
            raise ValueError("release_weight must be non-negative")
        if self.probe_per_buffer <= 0:
            raise ValueError("probe_per_buffer must be positive")
        if self.footprint_weight < 0:
            raise ValueError("footprint_weight must be non-negative")
        if self.footprint_min_buffers <= 0:
            raise ValueError("footprint_min_buffers must be positive")


@dataclass(frozen=True, slots=True)
class Q2ReuseScheduleResult:
    order: tuple[int, ...]
    evaluation: Q1Evaluation
    config: Q2ReuseScheduleConfig
    affinity_decisions: int
    footprint_decisions: int


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


def _build_l0_counted_footprints(
    graph: ComputeGraph,
    counted_sizes: dict[int, int],
) -> dict[int, tuple[int, ...]]:
    """Return a two-hop counted-buffer footprint for every L0 ALLOC node.

    Each operation's Bufs list forms a small undirected co-occurrence hyperedge.
    Two hops express relations such as L0C--L0A/L0B--L1 without naming an
    operator, tensor axis, or model family.
    """

    adjacency: dict[int, set[int]] = defaultdict(set)
    for node in graph.nodes.values():
        if node.is_memory_event:
            continue
        bufs = tuple(dict.fromkeys(node.bufs))
        for i, left in enumerate(bufs):
            for right in bufs[i + 1 :]:
                if left == right:
                    continue
                adjacency[left].add(right)
                adjacency[right].add(left)

    footprints: dict[int, tuple[int, ...]] = {}
    for node in graph.nodes.values():
        if not (node.is_alloc and node.memory_type in L0_TYPES and node.buf_id is not None):
            continue
        seen = {node.buf_id}
        frontier = {node.buf_id}
        counted: set[int] = set()
        for _depth in range(2):
            nxt: set[int] = set()
            for buf_id in frontier:
                for neighbor in adjacency.get(buf_id, ()):
                    if neighbor in counted_sizes:
                        counted.add(neighbor)
                    if neighbor not in seen:
                        seen.add(neighbor)
                        nxt.add(neighbor)
            frontier = nxt
            if not frontier:
                break
        footprints[node.id] = tuple(sorted(counted))
    return footprints


def schedule_q2_reuse_aware(
    graph: ComputeGraph,
    config: Q2ReuseScheduleConfig = Q2ReuseScheduleConfig(),
) -> Q2ReuseScheduleResult:
    """Generate a Q1-valid order biased toward Q2 cache reuse.

    FREE-first and the single-live-buffer rule for each L0 type remain hard.
    Footprint routing is task-coherent: a sufficiently large L0C footprint becomes
    an active task anchor; while it is active, subordinate L0A/L0B allocations and
    counted L1/UB allocations are steered toward that same footprint.  After the
    anchor is freed, the next L0C task is chosen for maximum overlap with the
    just-completed footprint.  Restricting outer anchors to L0C follows the
    architecture's result-buffer role and prevents input-side L0A/L0B buffers from
    incorrectly taking ownership of an unrelated task.
    """

    indegree = graph.indegrees()
    counted_sizes = _counted_buffer_sizes(graph)
    l0_footprints = _build_l0_counted_footprints(graph, counted_sizes)
    counted_alloc_node = {
        node.buf_id: node.id
        for node in graph.nodes.values()
        if node.is_alloc and node.buf_id in counted_sizes
    }

    regular_ready: set[int] = set()
    regular_heap: list[tuple[tuple[int, int, int], int]] = []
    l0_ready_heap: dict[str, list[int]] = {kind: [] for kind in L0_TYPES}
    l0_ready_set: dict[str, set[int]] = {kind: set() for kind in L0_TYPES}
    l0_live: dict[str, int] = {kind: 0 for kind in L0_TYPES}
    active_l0_alloc: dict[str, int | None] = {kind: None for kind in L0_TYPES}
    last_l0_footprint: dict[str, frozenset[int]] = {kind: frozenset() for kind in L0_TYPES}

    task_anchor_alloc: int | None = None
    task_anchor_footprint: frozenset[int] = frozenset()

    ready_by_buf: dict[int, set[int]] = {buf_id: set() for buf_id in counted_sizes}
    ready_l0_by_footprint_buf: dict[int, set[int]] = defaultdict(set)
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
            memory_type = node.memory_type
            assert memory_type is not None
            heapq.heappush(l0_ready_heap[memory_type], node_id)
            l0_ready_set[memory_type].add(node_id)
            for buf_id in l0_footprints.get(node_id, ()):
                ready_l0_by_footprint_buf[buf_id].add(node_id)
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
    footprint_decisions = 0

    def clean_regular_heap() -> None:
        while regular_heap and regular_heap[0][1] not in regular_ready:
            heapq.heappop(regular_heap)

    def clean_l0_heap(memory_type: str) -> None:
        heap = l0_ready_heap[memory_type]
        ready = l0_ready_set[memory_type]
        while heap and heap[0] not in ready:
            heapq.heappop(heap)

    def fallback_candidate() -> int | None:
        clean_regular_heap()
        candidates: list[tuple[tuple[int, int, int], int]] = []
        if regular_heap:
            candidates.append(regular_heap[0])
        for memory_type in L0_TYPES:
            clean_l0_heap(memory_type)
            heap = l0_ready_heap[memory_type]
            if heap and l0_live[memory_type] == 0:
                node_id = heap[0]
                candidates.append((_ready_key(graph, node_id), node_id))
        if not candidates:
            return None
        return min(candidates)[1]

    def hot_scores() -> dict[int, int]:
        scores: dict[int, int] = {}
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
            if node.is_free and node.buf_id in counted_sizes and node.size is not None:
                total += node.size
        return total

    def routing_anchor_for_l0(memory_type: str) -> frozenset[int]:
        if task_anchor_alloc is not None:
            return task_anchor_footprint
        return last_l0_footprint[memory_type]

    def footprint_overlap_bytes(node_id: int) -> int:
        node = graph.nodes[node_id]
        if not (node.is_alloc and node.memory_type in L0_TYPES):
            return 0
        memory_type = node.memory_type
        assert memory_type is not None
        footprint = l0_footprints.get(node_id, ())
        anchor = routing_anchor_for_l0(memory_type)
        if len(anchor) < config.footprint_min_buffers or not footprint:
            return 0
        return sum(counted_sizes[buf_id] for buf_id in footprint if buf_id in anchor)

    def task_counted_alloc_bonus(node_id: int) -> int:
        if task_anchor_alloc is None:
            return 0
        node = graph.nodes[node_id]
        if not (
            node.is_alloc
            and node.buf_id in counted_sizes
            and node.memory_type in Q1_COUNTED_TYPES
        ):
            return 0
        assert node.buf_id is not None
        if node.buf_id not in task_anchor_footprint:
            return 0
        return counted_sizes[node.buf_id]

    def footprint_preferred(fallback: int) -> int:
        nonlocal footprint_decisions, affinity_decisions
        if config.footprint_weight <= 0:
            return fallback
        node = graph.nodes[fallback]
        if not (node.is_alloc and node.memory_type in L0_TYPES):
            return fallback
        memory_type = node.memory_type
        assert memory_type is not None
        anchor = routing_anchor_for_l0(memory_type)
        if len(anchor) < config.footprint_min_buffers:
            return fallback

        candidates: set[int] = {fallback}
        ready_same_type = l0_ready_set[memory_type]
        for buf_id in anchor:
            overlapping = ready_l0_by_footprint_buf.get(buf_id)
            if not overlapping:
                continue
            eligible = overlapping & ready_same_type
            candidates.update(heapq.nsmallest(config.probe_per_buffer, eligible))

        chosen = min(
            candidates,
            key=lambda node_id: (
                -footprint_overlap_bytes(node_id),
                _ready_key(graph, node_id),
            ),
        )
        if chosen != fallback and footprint_overlap_bytes(chosen) > footprint_overlap_bytes(fallback):
            footprint_decisions += 1
            affinity_decisions += 1
        return chosen

    def counted_alloc_preferred(fallback: int) -> int:
        nonlocal footprint_decisions, affinity_decisions
        if config.footprint_weight <= 0 or task_anchor_alloc is None:
            return fallback
        node = graph.nodes[fallback]
        if not (node.is_alloc and node.buf_id in counted_sizes):
            return fallback
        candidates = {fallback}
        for buf_id in task_anchor_footprint:
            alloc_id = counted_alloc_node.get(buf_id)
            if alloc_id is not None and alloc_id in regular_ready:
                candidates.add(alloc_id)
        chosen = min(
            candidates,
            key=lambda node_id: (
                -task_counted_alloc_bonus(node_id),
                _ready_key(graph, node_id),
            ),
        )
        if chosen != fallback and task_counted_alloc_bonus(chosen) > task_counted_alloc_bonus(fallback):
            footprint_decisions += 1
            affinity_decisions += 1
        return chosen

    while len(order) < graph.node_count:
        baseline_fallback = fallback_candidate()
        if baseline_fallback is None:
            unresolved = [node_id for node_id, degree in indegree.items() if degree > 0]
            blocked = {
                kind: sorted(l0_ready_set[kind])[:8]
                for kind in L0_TYPES
                if l0_ready_set[kind]
            }
            raise ValueError(
                "no legal ready node; "
                f"unresolved={unresolved[:8]}, blocked_l0={blocked}, "
                f"active_l0={active_l0_alloc}, task_anchor={task_anchor_alloc}"
            )

        if graph.nodes[baseline_fallback].is_free:
            chosen = baseline_fallback
        else:
            preferred = footprint_preferred(baseline_fallback)
            preferred = counted_alloc_preferred(preferred)
            scores = hot_scores()
            candidates: set[int] = {preferred}
            for buf_id in scores:
                ready = ready_by_buf.get(buf_id)
                if not ready:
                    continue
                candidates.update(heapq.nsmallest(config.probe_per_buffer, ready))

            def candidate_key(node_id: int) -> tuple[int, tuple[int, int, int]]:
                direct_affinity = sum(
                    counted_sizes[buf_id] * scores.get(buf_id, 0)
                    for buf_id in touched_by_node.get(node_id, ())
                )
                release = release_bytes(node_id)
                footprint = config.footprint_weight * footprint_overlap_bytes(node_id)
                task_alloc = config.footprint_weight * task_counted_alloc_bonus(node_id)
                value = direct_affinity + config.release_weight * release + footprint + task_alloc
                return (-value, _ready_key(graph, node_id))

            chosen = min(candidates, key=candidate_key)
            if chosen != preferred:
                affinity_decisions += 1

        node = graph.nodes[chosen]
        if node.is_alloc and node.memory_type in L0_TYPES:
            memory_type = node.memory_type
            assert memory_type is not None
            if chosen not in l0_ready_set[memory_type]:
                raise AssertionError(f"chosen L0 node {chosen} is not ready")
            if l0_live[memory_type] != 0:
                raise ValueError(f"{memory_type} ALLOC chosen while another buffer is live")
            l0_ready_set[memory_type].remove(chosen)
            for buf_id in l0_footprints.get(chosen, ()):
                ready_l0_by_footprint_buf[buf_id].discard(chosen)
            l0_live[memory_type] = 1
            active_l0_alloc[memory_type] = chosen
            footprint = l0_footprints.get(chosen, ())
            if (
                memory_type == "L0C"
                and task_anchor_alloc is None
                and len(footprint) >= config.footprint_min_buffers
            ):
                task_anchor_alloc = chosen
                task_anchor_footprint = frozenset(footprint)
        else:
            if chosen not in regular_ready:
                raise AssertionError(f"chosen node {chosen} is not regular-ready")
            regular_ready.remove(chosen)
            for buf_id in touched_by_node.get(chosen, ()):
                ready_by_buf[buf_id].discard(chosen)
            if node.is_free and node.memory_type in L0_TYPES:
                memory_type = node.memory_type
                assert memory_type is not None
                alloc = graph.alloc_node_for_buffer(node.buf_id) if node.buf_id is not None else None
                if alloc is None or active_l0_alloc[memory_type] != alloc.id:
                    raise ValueError(
                        f"FREE for {memory_type} buffer {node.buf_id} does not match active allocation"
                    )
                l0_live[memory_type] -= 1
                if l0_live[memory_type] < 0:
                    raise ValueError(f"FREE for {memory_type} before a live allocation at node {chosen}")
                active_l0_alloc[memory_type] = None
                footprint = l0_footprints.get(alloc.id, ())
                last_l0_footprint[memory_type] = (
                    frozenset(footprint)
                    if len(footprint) >= config.footprint_min_buffers
                    else frozenset()
                )
                if alloc.id == task_anchor_alloc:
                    task_anchor_alloc = None
                    task_anchor_footprint = frozenset()

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
    return Q2ReuseScheduleResult(
        tuple(order), evaluation, config, affinity_decisions, footprint_decisions
    )
