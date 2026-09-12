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
    original_edges,
    pipe_edges,
    residency_safe_reuse_edges,
    spill_edges,
)
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult


@dataclass(frozen=True, slots=True)
class CriticalPipeSwapTrial:
    u: int
    v: int
    pipe: str | None
    q2_valid: bool
    safe_valid: bool
    official_cycles: int | None
    safe_cycles: int | None
    changed_positions: int
    error: str = ""


@dataclass(frozen=True, slots=True)
class CriticalPipeSwapResult:
    baseline_solution: Q2Solution
    baseline_official: Q3TimingResult
    baseline_safe: Q3TimingResult
    best_solution: Q2Solution
    best_official: Q3TimingResult
    best_safe: Q3TimingResult
    best_edge: tuple[int, int] | None
    candidate_edges: tuple[tuple[int, int], ...]
    trials: tuple[CriticalPipeSwapTrial, ...]

    @property
    def improved(self) -> bool:
        return self.best_official.total_cycles < self.baseline_official.total_cycles


def _topological_order(nodes, edges: set[tuple[int, int]], original_pos: dict[int, int]) -> tuple[int, ...]:
    succ: dict[int, set[int]] = {node_id: set() for node_id in nodes}
    indegree: dict[int, int] = {node_id: 0 for node_id in nodes}
    for u, v in edges:
        if u not in nodes or v not in nodes:
            raise ValueError(f"precedence {u}->{v} references absent node")
        if v not in succ[u]:
            succ[u].add(v)
            indegree[v] += 1

    ready: list[tuple[int, int]] = []
    for node_id, degree in indegree.items():
        if degree == 0:
            heapq.heappush(ready, (original_pos[node_id], node_id))

    order: list[int] = []
    while ready:
        _, node_id = heapq.heappop(ready)
        order.append(node_id)
        for nxt in succ[node_id]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                heapq.heappush(ready, (original_pos[nxt], nxt))
    if len(order) != len(nodes):
        raise ValueError("adjacent pipe reversal creates a precedence cycle")
    return tuple(order)


def search_q3_critical_pipe_swaps(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_candidates: int = 16,
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> CriticalPipeSwapResult:
    """Reverse one mutable critical same-Pipe adjacency at fixed layout/traffic.

    A saturated address-only solution with a reuse-free critical path cannot be
    improved by further recoloring at fixed schedule. This operator targets the
    remaining mutable edges on that path: same-Pipe serialization edges that are
    not also original/SPILL/residency-safe correctness precedence.

    For each candidate u->v, every other current same-Pipe adjacency is frozen,
    while u->v is replaced by v->u. A stable topological sort then changes only
    what is necessary to realize that local pipe swap. Acceptance still requires
    strict Q2, residency-safe, and official-literal replay with unchanged traffic
    and SPILL identity/order/count.
    """

    if max_candidates <= 0:
        raise ValueError("max_candidates must be positive")
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
    fixed = (
        original_edges(graph)
        | spill_edges(graph, solution, nodes, pos)
        | residency_safe_reuse_edges(graph, solution)
    )
    pipes = pipe_edges(solution, nodes)
    path_edges = list(zip(baseline_official.critical_path, baseline_official.critical_path[1:]))
    # Prefer downstream critical pipe adjacencies first; they are closest to the
    # terminal makespan and usually have less upstream schedule blast radius.
    candidates = [edge for edge in reversed(path_edges) if edge in pipes and edge not in fixed]
    candidates = candidates[:max_candidates]

    base_spills = tuple(spill.buf_id for spill in solution.spills)
    best_solution = solution
    best_official = baseline_official
    best_safe = baseline_safe
    best_edge: tuple[int, int] | None = None
    trials: list[CriticalPipeSwapTrial] = []

    for u, v in candidates:
        pipe = nodes[u].pipe
        if pipe is None or nodes[v].pipe != pipe:
            raise AssertionError("critical pipe edge endpoints do not share a pipe")
        try:
            constrained = set(fixed)
            constrained.update(pipes - {(u, v)})
            constrained.add((v, u))
            order = _topological_order(nodes, constrained, pos)
            changed = sum(a != b for a, b in zip(order, solution.schedule))
            candidate = Q2Solution(order, solution.initial_offsets, solution.spills)
            q2 = validate_q2_solution(graph, candidate)
            if not q2.ok:
                trials.append(
                    CriticalPipeSwapTrial(
                        u, v, pipe, False, False, None, None, changed, "; ".join(q2.errors[:2])
                    )
                )
                continue
            if q2.extra_traffic != base_q2.extra_traffic or q2.spill_count != base_q2.spill_count:
                raise AssertionError("critical pipe swap changed Q2 traffic/spill count")
            if tuple(spill.buf_id for spill in candidate.spills) != base_spills:
                raise AssertionError("critical pipe swap changed spill victim identity/order")

            safe = evaluate_q3_solution(graph, candidate, reuse_mode="residency_safe")
            if not safe.ok:
                trials.append(
                    CriticalPipeSwapTrial(
                        u, v, pipe, True, False, None, None, changed, "; ".join(safe.errors[:2])
                    )
                )
                continue
            official = evaluate_q3_solution(graph, candidate, reuse_mode="official_literal")
            official.require_ok()
            trials.append(
                CriticalPipeSwapTrial(
                    u, v, pipe, True, True, official.total_cycles, safe.total_cycles, changed
                )
            )
            if (official.total_cycles, safe.total_cycles, u, v) < (
                best_official.total_cycles,
                best_safe.total_cycles,
                best_edge[0] if best_edge is not None else 1 << 60,
                best_edge[1] if best_edge is not None else 1 << 60,
            ):
                best_solution = candidate
                best_official = official
                best_safe = safe
                best_edge = (u, v)
        except Exception as exc:
            trials.append(
                CriticalPipeSwapTrial(
                    u, v, pipe, False, False, None, None, 0, f"{type(exc).__name__}: {exc}"
                )
            )

    final_q2 = validate_q2_solution(graph, best_solution)
    final_q2.require_ok()
    if final_q2.extra_traffic != base_q2.extra_traffic or final_q2.spill_count != base_q2.spill_count:
        raise AssertionError("critical pipe swap final Q2 invariants changed")
    final_official = evaluate_q3_solution(graph, best_solution, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, best_solution, reuse_mode="residency_safe")
    final_safe.require_ok()

    return CriticalPipeSwapResult(
        solution,
        baseline_official,
        baseline_safe,
        best_solution,
        final_official,
        final_safe,
        best_edge,
        tuple(candidates),
        tuple(trials),
    )
