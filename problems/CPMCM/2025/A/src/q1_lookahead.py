from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from evaluator import Q1Evaluation, evaluate_q1
from model import ComputeGraph, L0_TYPES, Q1_COUNTED_TYPES
from q1_advanced import _L0PrerequisiteAnalyzer, _release_hints
from q1_scheduler import _ready_key, schedule_q1_baseline

INF = 10**18


@dataclass(frozen=True, slots=True)
class Q1LookaheadResult:
    order: tuple[int, ...]
    evaluation: Q1Evaluation
    lookahead_decisions: int
    baseline_upper_bound: int | None


def _memory_delta(graph: ComputeGraph, node_id: int) -> int:
    node = graph.nodes[node_id]
    if node.memory_type not in Q1_COUNTED_TYPES or node.size is None:
        return 0
    if node.is_alloc:
        return node.size
    if node.is_free:
        return -node.size
    return 0


def _is_positive_counted_alloc(graph: ComputeGraph, node_id: int) -> bool:
    node = graph.nodes[node_id]
    return node.is_alloc and node.memory_type in Q1_COUNTED_TYPES and (node.size or 0) > 0


def _rollout_nonpositive_key(graph: ComputeGraph, node_id: int) -> tuple[int, int, int]:
    node = graph.nodes[node_id]
    delta = _memory_delta(graph, node_id)
    if node.is_free:
        cls = 0
    elif not node.is_alloc:
        cls = 1
    else:
        # Only L0 ALLOC reaches the non-positive rollout queue.
        cls = 2
    return (cls, delta, node.id)


@dataclass(slots=True)
class _RolloutState:
    graph: ComputeGraph
    main_indegree: dict[int, int]
    main_live_buffers: set[int]
    main_l0_live: dict[str, int]
    main_active_l0: dict[str, int | None]
    main_completed_l0: dict[str, set[int]]
    l0_prereqs: _L0PrerequisiteAnalyzer
    resident: int
    peak: int
    horizon: int
    positive_ready: set[int]

    indegree_delta: dict[int, int] = field(default_factory=dict)
    live_override: dict[int, bool] = field(default_factory=dict)
    l0_live: dict[str, int] = field(default_factory=dict)
    active_l0: dict[str, int | None] = field(default_factory=dict)
    completed_l0_local: dict[str, set[int]] = field(default_factory=dict)
    scheduled: set[int] = field(default_factory=set)
    nonpositive_ready: set[int] = field(default_factory=set)
    nonpositive_heap: list[tuple[tuple[int, int, int], int]] = field(default_factory=list)
    blocked_l0: set[int] = field(default_factory=set)
    steps: int = 0
    truncated: bool = False

    def __post_init__(self) -> None:
        if not self.l0_live:
            self.l0_live = dict(self.main_l0_live)
        if not self.active_l0:
            self.active_l0 = dict(self.main_active_l0)
        if not self.completed_l0_local:
            self.completed_l0_local = {kind: set() for kind in L0_TYPES}

    def clone(self) -> "_RolloutState":
        return _RolloutState(
            graph=self.graph,
            main_indegree=self.main_indegree,
            main_live_buffers=self.main_live_buffers,
            main_l0_live=self.main_l0_live,
            main_active_l0=self.main_active_l0,
            main_completed_l0=self.main_completed_l0,
            l0_prereqs=self.l0_prereqs,
            resident=self.resident,
            peak=self.peak,
            horizon=self.horizon,
            positive_ready=set(self.positive_ready),
            indegree_delta=dict(self.indegree_delta),
            live_override=dict(self.live_override),
            l0_live=dict(self.l0_live),
            active_l0=dict(self.active_l0),
            completed_l0_local={kind: set(values) for kind, values in self.completed_l0_local.items()},
            scheduled=set(self.scheduled),
            nonpositive_ready=set(self.nonpositive_ready),
            nonpositive_heap=list(self.nonpositive_heap),
            blocked_l0=set(self.blocked_l0),
            steps=self.steps,
            truncated=self.truncated,
        )

    def is_live(self, buf_id: int) -> bool:
        override = self.live_override.get(buf_id)
        if override is not None:
            return override
        return buf_id in self.main_live_buffers

    def _l0_prereqs_complete(self, node_id: int) -> bool:
        node = self.graph.nodes[node_id]
        assert node.memory_type in L0_TYPES
        completed = self.main_completed_l0[node.memory_type]
        local_completed = self.completed_l0_local[node.memory_type]
        return all(
            prerequisite in completed or prerequisite in local_completed
            for prerequisite in self.l0_prereqs.prerequisites(node_id)
        )

    def _enqueue_new_ready(self, node_id: int) -> None:
        if node_id in self.scheduled:
            return
        if _is_positive_counted_alloc(self.graph, node_id):
            self.positive_ready.add(node_id)
            return

        node = self.graph.nodes[node_id]
        if node.is_alloc and node.memory_type in L0_TYPES:
            if self._l0_prereqs_complete(node_id):
                self.nonpositive_ready.add(node_id)
                heapq.heappush(
                    self.nonpositive_heap,
                    (_rollout_nonpositive_key(self.graph, node_id), node_id),
                )
            else:
                self.blocked_l0.add(node_id)
            return

        self.nonpositive_ready.add(node_id)
        heapq.heappush(
            self.nonpositive_heap,
            (_rollout_nonpositive_key(self.graph, node_id), node_id),
        )

    def _refresh_blocked_l0(self) -> None:
        newly_safe = [node_id for node_id in self.blocked_l0 if self._l0_prereqs_complete(node_id)]
        for node_id in newly_safe:
            self.blocked_l0.remove(node_id)
            self.nonpositive_ready.add(node_id)
            heapq.heappush(
                self.nonpositive_heap,
                (_rollout_nonpositive_key(self.graph, node_id), node_id),
            )

    def apply(self, node_id: int) -> bool:
        if self.steps >= self.horizon:
            self.truncated = True
            return False
        if node_id in self.scheduled:
            return False

        node = self.graph.nodes[node_id]
        if node.is_alloc:
            if node.buf_id is None or node.memory_type is None or self.is_live(node.buf_id):
                return False
            if node.memory_type in L0_TYPES:
                if self.l0_live[node.memory_type] != 0 or not self._l0_prereqs_complete(node_id):
                    return False
                self.l0_live[node.memory_type] = 1
                self.active_l0[node.memory_type] = node_id
            self.live_override[node.buf_id] = True
        elif node.is_free:
            if node.buf_id is None or node.memory_type is None or not self.is_live(node.buf_id):
                return False
            if node.memory_type in L0_TYPES:
                alloc = self.graph.alloc_node_for_buffer(node.buf_id)
                if alloc is None or self.active_l0[node.memory_type] != alloc.id:
                    return False
                self.l0_live[node.memory_type] = 0
                self.active_l0[node.memory_type] = None
                self.completed_l0_local[node.memory_type].add(alloc.id)
            self.live_override[node.buf_id] = False
        else:
            if any(not self.is_live(buf_id) for buf_id in node.bufs):
                return False

        delta = _memory_delta(self.graph, node_id)
        self.resident += delta
        if self.resident < 0:
            return False
        self.peak = max(self.peak, self.resident)

        self.scheduled.add(node_id)
        self.positive_ready.discard(node_id)
        self.nonpositive_ready.discard(node_id)
        self.steps += 1

        for succ in self.graph.successors[node_id]:
            delta_count = self.indegree_delta.get(succ, 0) + 1
            self.indegree_delta[succ] = delta_count
            remaining = self.main_indegree[succ] - delta_count
            if remaining < 0:
                return False
            if remaining == 0:
                self._enqueue_new_ready(succ)

        if node.is_free and node.memory_type in L0_TYPES:
            self._refresh_blocked_l0()
        return True

    def drain_nonpositive(self) -> bool:
        while self.nonpositive_heap:
            if self.steps >= self.horizon:
                self.truncated = True
                return True
            _, node_id = heapq.heappop(self.nonpositive_heap)
            if node_id not in self.nonpositive_ready:
                continue
            node = self.graph.nodes[node_id]
            if node.is_alloc and node.memory_type in L0_TYPES and self.l0_live[node.memory_type] != 0:
                # Keep it available for later; another local L0 FREE may reopen the slot.
                heapq.heappush(
                    self.nonpositive_heap,
                    (_rollout_nonpositive_key(self.graph, node_id), node_id),
                )
                return True
            if not self.apply(node_id):
                return False
        return True


def _terminal_score(state: _RolloutState) -> tuple[int, int, int, int]:
    next_sizes = [
        state.graph.nodes[node_id].size or 0
        for node_id in state.positive_ready
        if node_id not in state.scheduled
    ]
    one_more_peak = state.peak
    if next_sizes:
        one_more_peak = max(one_more_peak, state.resident + min(next_sizes))
    return (one_more_peak, state.resident, 1 if state.truncated else 0, state.steps)


def _search_rollout(state: _RolloutState, depth: int, branch_limit: int) -> tuple[int, int, int, int]:
    if not state.drain_nonpositive():
        return (INF, INF, 1, INF)
    if depth <= 0 or state.truncated or not state.positive_ready:
        return _terminal_score(state)

    candidates = sorted(
        state.positive_ready,
        key=lambda node_id: ((state.graph.nodes[node_id].size or 0), node_id),
    )[:branch_limit]
    best = (INF, INF, 1, INF)
    for node_id in candidates:
        child = state.clone()
        if not child.apply(node_id):
            continue
        score = _search_rollout(child, depth - 1, branch_limit)
        if score < best:
            best = score
    return best


def schedule_q1_lookahead(
    graph: ComputeGraph,
    *,
    depth: int = 2,
    candidate_limit: int = 6,
    rollout_horizon: int = 96,
    trigger_ratio: float = 0.5,
) -> Q1LookaheadResult:
    """Deadlock-safe Q1 scheduler with bounded search only at positive-ALLOC forks.

    The main schedule remains deterministic and greedy for FREE/neutral/L0 work.
    Expensive lookahead is triggered only when at least two L1/UB ALLOCs are ready and
    the current residency is sufficiently close to a known valid baseline upper bound
    (all small graphs are searched regardless of the ratio). Candidate generation mixes
    smallest allocations with allocations whose nearest downstream FREE is attractive.
    Final validity and peak are always recomputed by the independent evaluator.
    """

    if depth < 1 or candidate_limit < 2 or rollout_horizon < 1:
        raise ValueError("depth>=1, candidate_limit>=2 and rollout_horizon>=1 are required")
    if not 0.0 <= trigger_ratio <= 1.0:
        raise ValueError("trigger_ratio must be in [0, 1]")

    try:
        baseline_eval = schedule_q1_baseline(graph).evaluation
        baseline_upper = baseline_eval.peak_residency if baseline_eval.valid else None
    except ValueError:
        baseline_upper = None

    release_hints, _ = _release_hints(graph)
    l0_prereqs = _L0PrerequisiteAnalyzer(graph)
    indegree = graph.indegrees()

    nonpositive_heap: list[tuple[tuple[int, int, int], int]] = []
    positive_ready: set[int] = set()
    positive_size_heap: list[tuple[int, int]] = []
    positive_release_heap: list[tuple[int, int, int, int]] = []
    l0_safe_heap: dict[str, list[int]] = {kind: [] for kind in L0_TYPES}
    l0_live: dict[str, int] = {kind: 0 for kind in L0_TYPES}
    active_l0: dict[str, int | None] = {kind: None for kind in L0_TYPES}
    completed_l0: dict[str, set[int]] = {kind: set() for kind in L0_TYPES}
    blocked_l0: set[int] = set()
    live_buffers: set[int] = set()

    resident = 0
    peak = 0
    lookahead_decisions = 0

    def l0_prereqs_complete(node_id: int) -> bool:
        node = graph.nodes[node_id]
        assert node.memory_type in L0_TYPES
        return all(
            prerequisite in completed_l0[node.memory_type]
            for prerequisite in l0_prereqs.prerequisites(node_id)
        )

    def enqueue(node_id: int) -> None:
        node = graph.nodes[node_id]
        if _is_positive_counted_alloc(graph, node_id):
            positive_ready.add(node_id)
            size = node.size or 0
            heapq.heappush(positive_size_heap, (size, node_id))
            hint = release_hints[node_id]
            hint_size = 0 if hint is None else hint.size
            hint_distance = 10**9 if hint is None else hint.distance
            heapq.heappush(
                positive_release_heap,
                (size - hint_size, hint_distance, size, node_id),
            )
        elif node.is_alloc and node.memory_type in L0_TYPES:
            if l0_prereqs_complete(node_id):
                heapq.heappush(l0_safe_heap[node.memory_type], node_id)
            else:
                blocked_l0.add(node_id)
        else:
            heapq.heappush(nonpositive_heap, (_ready_key(graph, node_id), node_id))

    def refresh_blocked_l0() -> None:
        newly_safe = [node_id for node_id in blocked_l0 if l0_prereqs_complete(node_id)]
        for node_id in newly_safe:
            blocked_l0.remove(node_id)
            node = graph.nodes[node_id]
            assert node.memory_type in L0_TYPES
            heapq.heappush(l0_safe_heap[node.memory_type], node_id)

    def top_active(heap: list[tuple], limit: int, id_index: int) -> list[int]:
        popped: list[tuple] = []
        result: list[int] = []
        while heap and len(result) < limit:
            entry = heapq.heappop(heap)
            node_id = entry[id_index]
            if node_id not in positive_ready:
                continue
            popped.append(entry)
            result.append(node_id)
        for entry in popped:
            heapq.heappush(heap, entry)
        return result

    def candidate_pool() -> list[int]:
        small_n = (candidate_limit + 1) // 2
        release_n = candidate_limit - small_n
        pool: list[int] = []
        for node_id in top_active(positive_size_heap, small_n, 1):
            if node_id not in pool:
                pool.append(node_id)
        for node_id in top_active(positive_release_heap, release_n, 3):
            if node_id not in pool:
                pool.append(node_id)
        if len(pool) < 2:
            for node_id in top_active(positive_size_heap, candidate_limit, 1):
                if node_id not in pool:
                    pool.append(node_id)
                if len(pool) >= candidate_limit:
                    break
        return pool

    def execute_main(node_id: int) -> None:
        nonlocal resident, peak
        node = graph.nodes[node_id]
        if node.is_alloc:
            if node.buf_id is None or node.memory_type is None or node.buf_id in live_buffers:
                raise ValueError(f"invalid ALLOC at node {node_id}")
            if node.memory_type in L0_TYPES:
                if l0_live[node.memory_type] != 0 or not l0_prereqs_complete(node_id):
                    raise ValueError(f"unsafe L0 ALLOC at node {node_id}")
                l0_live[node.memory_type] = 1
                active_l0[node.memory_type] = node_id
            live_buffers.add(node.buf_id)
        elif node.is_free:
            if node.buf_id is None or node.memory_type is None or node.buf_id not in live_buffers:
                raise ValueError(f"invalid FREE at node {node_id}")
            live_buffers.remove(node.buf_id)
            if node.memory_type in L0_TYPES:
                alloc = graph.alloc_node_for_buffer(node.buf_id)
                if alloc is None or active_l0[node.memory_type] != alloc.id:
                    raise ValueError(f"L0 FREE {node_id} does not match active allocation")
                l0_live[node.memory_type] = 0
                active_l0[node.memory_type] = None
                completed_l0[node.memory_type].add(alloc.id)
                refresh_blocked_l0()
        else:
            missing = [buf_id for buf_id in node.bufs if buf_id not in live_buffers]
            if missing:
                raise ValueError(f"operation {node_id} references non-live buffers {missing[:8]}")

        resident += _memory_delta(graph, node_id)
        if resident < 0:
            raise ValueError(f"negative Q1 residency after node {node_id}")
        peak = max(peak, resident)
        positive_ready.discard(node_id)

        for nxt in graph.successors[node_id]:
            indegree[nxt] -= 1
            if indegree[nxt] < 0:
                raise AssertionError(f"negative indegree at node {nxt}")
            if indegree[nxt] == 0:
                enqueue(nxt)

    for node_id, degree in indegree.items():
        if degree == 0:
            enqueue(node_id)

    order: list[int] = []
    while len(order) < graph.node_count:
        candidates: list[tuple[tuple[int, int, int], str | None, int]] = []
        if nonpositive_heap:
            key, node_id = nonpositive_heap[0]
            candidates.append((key, None, node_id))
        for memory_type, heap in l0_safe_heap.items():
            if heap and l0_live[memory_type] == 0:
                node_id = heap[0]
                candidates.append(((1, 0, node_id), memory_type, node_id))

        if candidates:
            _, l0_type, chosen = min(candidates, key=lambda item: item[0])
            if l0_type is None:
                _, popped = heapq.heappop(nonpositive_heap)
                if popped != chosen:
                    raise AssertionError("non-positive ready heap corruption")
            else:
                popped = heapq.heappop(l0_safe_heap[l0_type])
                if popped != chosen:
                    raise AssertionError("L0 ready heap corruption")
        elif positive_ready:
            pool = candidate_pool()
            if not pool:
                raise AssertionError("positive ready set is non-empty but candidate pool is empty")

            should_search = len(pool) >= 2 and (
                graph.node_count <= 100
                or baseline_upper is None
                or resident >= trigger_ratio * baseline_upper
                or resident + min(graph.nodes[node_id].size or 0 for node_id in pool)
                >= trigger_ratio * baseline_upper
            )

            if should_search:
                lookahead_decisions += 1
                best_choice = pool[0]
                best_score = (INF, INF, 1, INF)
                for node_id in pool:
                    state = _RolloutState(
                        graph=graph,
                        main_indegree=indegree,
                        main_live_buffers=live_buffers,
                        main_l0_live=l0_live,
                        main_active_l0=active_l0,
                        main_completed_l0=completed_l0,
                        l0_prereqs=l0_prereqs,
                        resident=resident,
                        peak=peak,
                        horizon=rollout_horizon,
                        positive_ready=set(pool),
                    )
                    if not state.apply(node_id):
                        continue
                    score = _search_rollout(state, depth - 1, candidate_limit)
                    if score < best_score or (score == best_score and node_id < best_choice):
                        best_score = score
                        best_choice = node_id
                chosen = best_choice
            else:
                chosen = min(pool, key=lambda node_id: ((graph.nodes[node_id].size or 0), node_id))
            positive_ready.remove(chosen)
        else:
            unresolved = [node_id for node_id, degree in indegree.items() if degree > 0]
            raise ValueError(
                "Q1 lookahead scheduler has no feasible ready node; "
                f"unresolved={unresolved[:8]}, blocked_l0={sorted(blocked_l0)[:8]}"
            )

        execute_main(chosen)
        order.append(chosen)

    evaluation = evaluate_q1(graph, order)
    if not evaluation.valid:
        raise ValueError(f"lookahead scheduler emitted invalid order: {evaluation.errors}")
    if evaluation.peak_residency != peak:
        raise AssertionError(
            f"incremental peak {peak} disagrees with evaluator peak {evaluation.peak_residency}"
        )
    return Q1LookaheadResult(tuple(order), evaluation, lookahead_decisions, baseline_upper)
