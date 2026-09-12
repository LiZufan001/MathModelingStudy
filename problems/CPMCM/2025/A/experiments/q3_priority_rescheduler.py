from __future__ import annotations

import heapq
import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_dependencies import (
    augmented_nodes,
    official_literal_reuse_edges,
    original_edges,
    residency_safe_reuse_edges,
    spill_edges,
)
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult, node_cycles


@dataclass(frozen=True, slots=True)
class PriorityRescheduleTrial:
    policy: str
    q2_valid: bool
    safe_valid: bool | None
    official_cycles: int | None
    safe_cycles: int | None
    changed_positions: int
    error: str = ""


@dataclass(frozen=True, slots=True)
class PriorityRescheduleResult:
    baseline_solution: Q2Solution
    baseline_official: Q3TimingResult
    baseline_safe: Q3TimingResult
    best_solution: Q2Solution
    best_official: Q3TimingResult
    best_safe: Q3TimingResult
    best_policy: str
    trials: tuple[PriorityRescheduleTrial, ...]

    @property
    def improved(self) -> bool:
        return self.best_official.total_cycles < self.baseline_official.total_cycles


def _edge_graph(nodes, edges: set[tuple[int, int]], pos: dict[int, int]):
    succ: dict[int, set[int]] = {node_id: set() for node_id in nodes}
    pred: dict[int, set[int]] = {node_id: set() for node_id in nodes}
    for u, v in edges:
        if u not in pos or v not in pos:
            raise ValueError(f"precedence {u}->{v} references node absent from schedule")
        if pos[u] >= pos[v]:
            raise ValueError(f"precedence {u}->{v} contradicts baseline schedule")
        succ[u].add(v)
        pred[v].add(u)
    return succ, pred


def _bottom_levels(schedule: tuple[int, ...], nodes, succ: dict[int, set[int]]) -> dict[int, int]:
    bottom: dict[int, int] = {}
    for node_id in reversed(schedule):
        downstream = max((bottom[v] for v in succ[node_id]), default=0)
        bottom[node_id] = node_cycles(nodes[node_id]) + downstream
    return bottom


def _candidate_order(
    solution: Q2Solution,
    nodes,
    legal_succ: dict[int, set[int]],
    legal_pred: dict[int, set[int]],
    priority_bottom: dict[int, int],
    *,
    long_first_tiebreak: bool,
) -> tuple[int, ...]:
    indegree = {node_id: len(legal_pred[node_id]) for node_id in nodes}
    original_pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    ready: list[tuple[int, int, int, int]] = []

    def push(node_id: int) -> None:
        cycle_key = -node_cycles(nodes[node_id]) if long_first_tiebreak else 0
        heapq.heappush(
            ready,
            (-priority_bottom[node_id], cycle_key, original_pos[node_id], node_id),
        )

    for node_id, degree in indegree.items():
        if degree == 0:
            push(node_id)

    order: list[int] = []
    while ready:
        _, _, _, node_id = heapq.heappop(ready)
        order.append(node_id)
        for nxt in legal_succ[node_id]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                push(nxt)
    if len(order) != len(nodes):
        unresolved = [node_id for node_id, degree in indegree.items() if degree > 0]
        raise ValueError(f"legal precedence contains a cycle: {unresolved[:8]}")
    return tuple(order)


def search_q3_priority_reschedule_portfolio(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> PriorityRescheduleResult:
    """Try objective-aligned topological priority rules at fixed Q2 layout/traffic.

    Every candidate obeys the same frozen correctness precedence used by the
    production critical rescheduler: original DAG + SPILL + residency-safe reuse.
    Only the ready-queue ranking changes. Priority bottom-levels are computed from
    safe, official-literal, or structural (original+SPILL) dependency graphs.
    Candidates are accepted only after strict Q2, official, and residency-safe
    replay, with SPILL identity/order/count and extra traffic invariant. Official
    timing is evaluated first so clearly noncompetitive candidates can skip the
    more expensive residency-safe replay without weakening the acceptance gate.
    """

    base_q2 = validate_q2_solution(graph, solution)
    base_q2.require_ok()
    if baseline_official is None:
        baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    if baseline_safe is None:
        baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()

    nodes = augmented_nodes(graph, solution)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    base_edges = original_edges(graph)
    s_edges = spill_edges(graph, solution, nodes, pos)
    safe_reuse = residency_safe_reuse_edges(graph, solution)
    official_reuse = official_literal_reuse_edges(graph, solution, pos)

    legal_edges = base_edges | s_edges | safe_reuse
    legal_succ, legal_pred = _edge_graph(nodes, legal_edges, pos)

    priority_edge_sets = {
        "safe_bottom": legal_edges,
        "official_bottom": base_edges | s_edges | official_reuse,
        "structural_bottom": base_edges | s_edges,
    }
    policies = [
        ("safe_bottom", False),
        ("official_bottom", False),
        ("structural_bottom", False),
        ("official_bottom_long_first", True),
        ("structural_bottom_long_first", True),
    ]
    bottoms = {
        name: _bottom_levels(
            solution.schedule,
            nodes,
            _edge_graph(nodes, edges, pos)[0],
        )
        for name, edges in priority_edge_sets.items()
    }

    base_spills = tuple(spill.buf_id for spill in solution.spills)
    best_solution = solution
    best_official = baseline_official
    best_safe = baseline_safe
    best_policy = "baseline"
    trials: list[PriorityRescheduleTrial] = []

    for policy, long_first in policies:
        bottom_name = policy.removesuffix("_long_first")
        try:
            order = _candidate_order(
                solution,
                nodes,
                legal_succ,
                legal_pred,
                bottoms[bottom_name],
                long_first_tiebreak=long_first,
            )
            candidate = Q2Solution(order, solution.initial_offsets, solution.spills)
            changed = sum(a != b for a, b in zip(order, solution.schedule))
            q2 = validate_q2_solution(graph, candidate)
            if not q2.ok:
                trials.append(
                    PriorityRescheduleTrial(
                        policy, False, False, None, None, changed, "; ".join(q2.errors[:2])
                    )
                )
                continue
            if q2.extra_traffic != base_q2.extra_traffic or q2.spill_count != base_q2.spill_count:
                raise AssertionError("priority reschedule changed Q2 traffic/spill count")
            if tuple(spill.buf_id for spill in candidate.spills) != base_spills:
                raise AssertionError("priority reschedule changed spill victim identity/order")

            official = evaluate_q3_solution(graph, candidate, reuse_mode="official_literal")
            official.require_ok()
            if official.total_cycles > best_official.total_cycles:
                trials.append(
                    PriorityRescheduleTrial(
                        policy,
                        True,
                        None,
                        official.total_cycles,
                        None,
                        changed,
                        "residency-safe replay skipped: official score not competitive",
                    )
                )
                continue

            safe = evaluate_q3_solution(graph, candidate, reuse_mode="residency_safe")
            if not safe.ok:
                trials.append(
                    PriorityRescheduleTrial(
                        policy,
                        True,
                        False,
                        official.total_cycles,
                        None,
                        changed,
                        "; ".join(safe.errors[:2]),
                    )
                )
                continue
            trials.append(
                PriorityRescheduleTrial(
                    policy,
                    True,
                    True,
                    official.total_cycles,
                    safe.total_cycles,
                    changed,
                )
            )
            if (official.total_cycles, safe.total_cycles, policy) < (
                best_official.total_cycles,
                best_safe.total_cycles,
                best_policy,
            ):
                best_solution = candidate
                best_official = official
                best_safe = safe
                best_policy = policy
        except Exception as exc:
            trials.append(
                PriorityRescheduleTrial(
                    policy, False, False, None, None, 0, f"{type(exc).__name__}: {exc}"
                )
            )

    final_q2 = validate_q2_solution(graph, best_solution)
    final_q2.require_ok()
    if final_q2.extra_traffic != base_q2.extra_traffic or final_q2.spill_count != base_q2.spill_count:
        raise AssertionError("priority portfolio final Q2 invariants changed")
    final_official = evaluate_q3_solution(graph, best_solution, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, best_solution, reuse_mode="residency_safe")
    final_safe.require_ok()

    return PriorityRescheduleResult(
        solution,
        baseline_official,
        baseline_safe,
        best_solution,
        final_official,
        final_safe,
        best_policy,
        tuple(trials),
    )
