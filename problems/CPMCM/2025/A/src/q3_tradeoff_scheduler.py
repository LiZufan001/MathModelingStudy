from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Sequence

from evaluator import Q1Evaluation, evaluate_q1
from model import ComputeGraph, L0_TYPES
from validators import validate_buffer_lifetimes


@dataclass(frozen=True, slots=True)
class Q3CriticalWindowScheduleResult:
    order: tuple[int, ...]
    evaluation: Q1Evaluation
    window: int
    changed_positions: int


def _node_cycles(graph: ComputeGraph, node_id: int) -> int:
    node = graph.nodes[node_id]
    if node.is_memory_event:
        return 0
    return max(0, node.cycles or 0)


def _fixed_original_precedence(
    graph: ComputeGraph,
    base_order: Sequence[int],
) -> tuple[dict[int, set[int]], dict[int, set[int]]]:
    """Original DAG plus the base order's L0 single-residency serialization.

    Q3 trade-off candidates are allowed to move independent work, but must not
    manufacture illegal overlap between two L0A/L0B/L0C lifetimes.  Consecutive
    ALLOC epochs of each L0 type therefore inherit FREE(prev)->ALLOC(next).
    This is graph-generic and depends only on the already-valid base order.
    """

    base = tuple(base_order)
    validate_buffer_lifetimes(graph, base).require_ok()
    pos = {node_id: index for index, node_id in enumerate(base)}
    succ = {node_id: set(graph.successors[node_id]) for node_id in graph.nodes}
    pred = {node_id: set(graph.predecessors[node_id]) for node_id in graph.nodes}

    def add_edge(u: int, v: int) -> None:
        if u == v:
            raise ValueError(f"self precedence at node {u}")
        if pos[u] >= pos[v]:
            raise ValueError(f"fixed precedence {u}->{v} contradicts base order")
        if v not in succ[u]:
            succ[u].add(v)
            pred[v].add(u)

    for memory_type in sorted(L0_TYPES):
        allocations = [
            graph.nodes[node_id]
            for node_id in base
            if graph.nodes[node_id].is_alloc
            and graph.nodes[node_id].memory_type == memory_type
        ]
        for previous, current in zip(allocations, allocations[1:]):
            if previous.buf_id is None:
                raise ValueError(f"L0 allocation {previous.id} has no BufId")
            free = graph.free_node_for_buffer(previous.buf_id)
            if free is None:
                raise ValueError(f"L0 buffer {previous.buf_id} has no FREE")
            add_edge(free.id, current.id)

    return succ, pred


def _bottom_levels(
    graph: ComputeGraph,
    base_order: Sequence[int],
    succ: dict[int, set[int]],
) -> dict[int, int]:
    bottom: dict[int, int] = {}
    for node_id in reversed(tuple(base_order)):
        downstream = max((bottom[v] for v in succ[node_id]), default=0)
        bottom[node_id] = _node_cycles(graph, node_id) + downstream
    return bottom


def schedule_q3_critical_window(
    graph: ComputeGraph,
    base_order: Sequence[int],
    *,
    window: int,
) -> Q3CriticalWindowScheduleResult:
    """Controlled critical-path deviation from a known-good Q2 order.

    Let p(v) be v's position in the promoted Q2 order. At each Kahn step, let
    p_min be the earliest position among all currently ready nodes. Only ready
    nodes with p(v) <= p_min + window may compete; among those, the node with
    largest fixed-precedence bottom level is chosen. Thus window=0 reproduces the
    base order exactly, while larger windows gradually expose pipeline parallelism
    without permitting arbitrary global permutation.
    """

    if window < 0:
        raise ValueError("window must be non-negative")
    base = tuple(base_order)
    if len(base) != graph.node_count:
        raise ValueError("base order must contain every original graph node")

    succ, pred = _fixed_original_precedence(graph, base)
    bottom = _bottom_levels(graph, base, succ)
    original_pos = {node_id: index for index, node_id in enumerate(base)}
    indegree = {node_id: len(pred[node_id]) for node_id in graph.nodes}

    ready: set[int] = set()
    min_ready: list[tuple[int, int]] = []
    waiting: list[tuple[int, int]] = []
    eligible: list[tuple[int, int, int]] = []

    def enqueue(node_id: int) -> None:
        if node_id in ready:
            return
        ready.add(node_id)
        entry = (original_pos[node_id], node_id)
        heapq.heappush(min_ready, entry)
        heapq.heappush(waiting, entry)

    for node_id, degree in indegree.items():
        if degree == 0:
            enqueue(node_id)

    order: list[int] = []
    while ready:
        while min_ready and min_ready[0][1] not in ready:
            heapq.heappop(min_ready)
        if not min_ready:
            raise AssertionError("ready set is non-empty but min-ready heap is empty")
        frontier = min_ready[0][0] + window

        while waiting and waiting[0][0] <= frontier:
            pos, node_id = heapq.heappop(waiting)
            if node_id not in ready:
                continue
            heapq.heappush(eligible, (-bottom[node_id], pos, node_id))

        while eligible and eligible[0][2] not in ready:
            heapq.heappop(eligible)
        if not eligible:
            raise AssertionError("critical-window scheduler has no eligible ready node")

        _, _, node_id = heapq.heappop(eligible)
        ready.remove(node_id)
        order.append(node_id)
        for nxt in succ[node_id]:
            indegree[nxt] -= 1
            if indegree[nxt] < 0:
                raise AssertionError(f"negative indegree at node {nxt}")
            if indegree[nxt] == 0:
                enqueue(nxt)

    if len(order) != graph.node_count:
        unresolved = [node_id for node_id, degree in indegree.items() if degree > 0]
        raise ValueError(f"fixed original precedence contains a cycle: {unresolved[:8]}")

    candidate = tuple(order)
    evaluation = evaluate_q1(graph, candidate)
    if not evaluation.valid:
        raise ValueError("critical-window candidate is Q1-invalid: " + "; ".join(evaluation.errors))
    if window == 0 and candidate != base:
        raise AssertionError("window=0 must reproduce the base order exactly")

    changed = sum(1 for i, node_id in enumerate(candidate) if node_id != base[i])
    return Q3CriticalWindowScheduleResult(candidate, evaluation, window, changed)
