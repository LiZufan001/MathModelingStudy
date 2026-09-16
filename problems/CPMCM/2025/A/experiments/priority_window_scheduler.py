from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Literal, Sequence

from evaluator import Q1Evaluation, evaluate_q1
from model import ComputeGraph
from q3_tradeoff_scheduler import _bottom_levels, _fixed_original_precedence
from validators import validate_buffer_lifetimes

PriorityPolicy = Literal[
    "critical",
    "pipe_remaining",
    "unlock",
    "pipe_unlock",
]
PRIORITY_POLICIES: tuple[PriorityPolicy, ...] = (
    "critical",
    "pipe_remaining",
    "unlock",
    "pipe_unlock",
)


@dataclass(frozen=True, slots=True)
class PriorityWindowScheduleResult:
    order: tuple[int, ...]
    evaluation: Q1Evaluation
    window: int
    policy: PriorityPolicy
    changed_positions: int


def _node_cycles(graph: ComputeGraph, node_id: int) -> int:
    node = graph.nodes[node_id]
    if node.is_memory_event:
        return 0
    return max(0, node.cycles or 0)


def schedule_priority_window(
    graph: ComputeGraph,
    base_order: Sequence[int],
    *,
    window: int,
    policy: PriorityPolicy,
) -> PriorityWindowScheduleResult:
    """Experimental controlled reordering with dynamic pipeline-aware priorities.

    The feasible move set is identical in spirit to the production critical-window
    scheduler: original DAG and the base order's L0 single-residency order are
    frozen, and only ready nodes within ``p_min + window`` may compete.

    Policies only change which eligible node is selected:
    - critical: largest fixed-precedence bottom level (production behavior)
    - pipe_remaining: largest remaining work on the node's Pipe, then criticality
    - unlock: most immediate successors unlocked, then criticality
    - pipe_unlock: remaining Pipe work, then immediate unlock count, then criticality

    This module intentionally lives under experiments/ until a policy earns promotion.
    """

    if window < 0:
        raise ValueError("window must be non-negative")
    if policy not in PRIORITY_POLICIES:
        raise ValueError(f"unknown priority policy {policy!r}")

    base = tuple(base_order)
    if len(base) != graph.node_count or len(set(base)) != graph.node_count:
        raise ValueError("base order must contain every original graph node exactly once")
    validate_buffer_lifetimes(graph, base).require_ok()

    succ, pred = _fixed_original_precedence(graph, base)
    bottom = _bottom_levels(graph, base, succ)
    original_pos = {node_id: index for index, node_id in enumerate(base)}
    indegree = {node_id: len(pred[node_id]) for node_id in graph.nodes}

    remaining_pipe: dict[str, int] = {}
    for node in graph.nodes.values():
        if node.pipe is not None and not node.is_memory_event:
            remaining_pipe[node.pipe] = remaining_pipe.get(node.pipe, 0) + max(
                0, node.cycles or 0
            )

    ready: set[int] = set()
    min_ready: list[tuple[int, int]] = []
    waiting: list[tuple[int, int]] = []
    eligible: set[int] = set()

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

    def dynamic_key(node_id: int) -> tuple[int, int, int, int]:
        node = graph.nodes[node_id]
        pipe_remaining = 0 if node.pipe is None else remaining_pipe.get(node.pipe, 0)
        unlock_count = sum(1 for nxt in succ[node_id] if indegree[nxt] == 1)
        criticality = bottom[node_id]
        stable = -original_pos[node_id]
        if policy == "critical":
            return (criticality, 0, 0, stable)
        if policy == "pipe_remaining":
            return (pipe_remaining, criticality, unlock_count, stable)
        if policy == "unlock":
            return (unlock_count, criticality, pipe_remaining, stable)
        return (pipe_remaining, unlock_count, criticality, stable)

    order: list[int] = []
    while ready:
        while min_ready and min_ready[0][1] not in ready:
            heapq.heappop(min_ready)
        if not min_ready:
            raise AssertionError("ready set is non-empty but min-ready heap is empty")
        frontier = min_ready[0][0] + window

        while waiting and waiting[0][0] <= frontier:
            _, node_id = heapq.heappop(waiting)
            if node_id in ready:
                eligible.add(node_id)

        eligible.intersection_update(ready)
        if not eligible:
            raise AssertionError("priority-window scheduler has no eligible ready node")

        node_id = max(eligible, key=dynamic_key)
        eligible.remove(node_id)
        ready.remove(node_id)
        order.append(node_id)

        node = graph.nodes[node_id]
        if node.pipe is not None and not node.is_memory_event:
            remaining_pipe[node.pipe] -= _node_cycles(graph, node_id)
            if remaining_pipe[node.pipe] < 0:
                raise AssertionError(f"negative remaining Pipe work for {node.pipe}")

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
        raise ValueError(
            "priority-window candidate is Q1-invalid: " + "; ".join(evaluation.errors)
        )
    if window == 0 and candidate != base:
        raise AssertionError("window=0 must reproduce the base order exactly")

    changed = sum(1 for i, node_id in enumerate(candidate) if node_id != base[i])
    return PriorityWindowScheduleResult(
        candidate,
        evaluation,
        window,
        policy,
        changed,
    )
