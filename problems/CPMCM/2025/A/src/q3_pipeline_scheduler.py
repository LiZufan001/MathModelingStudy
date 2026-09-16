from __future__ import annotations

import heapq
from dataclasses import dataclass

from model import ComputeGraph
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_dependencies import (
    augmented_nodes,
    original_edges,
    residency_safe_reuse_edges,
    spill_edges,
)
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult, node_cycles


@dataclass(frozen=True, slots=True)
class Q3RescheduleResult:
    solution: Q2Solution
    timing: Q3TimingResult
    changed_positions: int


def _fixed_precedence(
    graph: ComputeGraph,
    solution: Q2Solution,
) -> tuple[dict[int, set[int]], dict[int, set[int]]]:
    """Freeze all non-Pipe correctness dependencies of a valid Q2 solution."""

    validate_q2_solution(graph, solution).require_ok()
    nodes = augmented_nodes(graph, solution)
    pos = {node_id: index for index, node_id in enumerate(solution.schedule)}
    edges = (
        original_edges(graph)
        | spill_edges(graph, solution, nodes, pos)
        | residency_safe_reuse_edges(graph, solution)
    )
    succ: dict[int, set[int]] = {node_id: set() for node_id in nodes}
    pred: dict[int, set[int]] = {node_id: set() for node_id in nodes}
    for u, v in edges:
        if pos[u] >= pos[v]:
            raise ValueError(f"fixed precedence {u}->{v} contradicts input schedule")
        succ[u].add(v)
        pred[v].add(u)
    return succ, pred


def _bottom_levels(
    solution: Q2Solution,
    nodes,
    succ: dict[int, set[int]],
) -> dict[int, int]:
    """Longest remaining fixed-precedence path including the current node."""

    bottom: dict[int, int] = {}
    for node_id in reversed(solution.schedule):
        downstream = max((bottom[v] for v in succ[node_id]), default=0)
        bottom[node_id] = node_cycles(nodes[node_id]) + downstream
    return bottom


def reschedule_q3_critical(
    graph: ComputeGraph,
    solution: Q2Solution,
) -> Q3RescheduleResult:
    """Critical-bottom-level topological reorder at fixed Q2 traffic/layout.

    Original DAG, SPILL partition/dependencies, and every physical residency-order
    constraint are frozen. The only freedom is the relative order of otherwise
    independent nodes, which changes same-Pipe instruction order in Appendix C.
    """

    nodes = augmented_nodes(graph, solution)
    succ, pred = _fixed_precedence(graph, solution)
    indegree = {node_id: len(pred[node_id]) for node_id in nodes}
    bottom = _bottom_levels(solution, nodes, succ)
    original_pos = {node_id: index for index, node_id in enumerate(solution.schedule)}

    ready: list[tuple[int, int, int]] = []
    for node_id, degree in indegree.items():
        if degree == 0:
            heapq.heappush(ready, (-bottom[node_id], original_pos[node_id], node_id))

    order: list[int] = []
    while ready:
        _, _, node_id = heapq.heappop(ready)
        order.append(node_id)
        for nxt in succ[node_id]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                heapq.heappush(ready, (-bottom[nxt], original_pos[nxt], nxt))

    if len(order) != len(nodes):
        unresolved = [node_id for node_id, degree in indegree.items() if degree > 0]
        raise ValueError(f"fixed Q3 precedence contains a cycle: {unresolved[:8]}")

    candidate = Q2Solution(tuple(order), solution.initial_offsets, solution.spills)
    replay = validate_q2_solution(graph, candidate)
    replay.require_ok()
    original_replay = validate_q2_solution(graph, solution)
    if (
        replay.spill_count != original_replay.spill_count
        or replay.extra_traffic != original_replay.extra_traffic
    ):
        raise AssertionError("Q3 reschedule changed Q2 spill count or traffic")

    timing = evaluate_q3_solution(graph, candidate, reuse_mode="residency_safe")
    timing.require_ok()
    changed = sum(
        1 for index, node_id in enumerate(candidate.schedule)
        if node_id != solution.schedule[index]
    )
    return Q3RescheduleResult(candidate, timing, changed)
