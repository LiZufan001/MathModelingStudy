from __future__ import annotations

import heapq
from dataclasses import dataclass

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
from q3_model import Q3TimingResult, node_cycles


@dataclass(frozen=True, slots=True)
class CriticalSpillCandidate:
    spill_index: int
    out_id: int
    in_id: int
    left_run_cycles: int
    right_run_cycles: int

    @property
    def combined_run_cycles(self) -> int:
        return self.left_run_cycles + self.right_run_cycles


@dataclass(frozen=True, slots=True)
class CriticalSpillBatchTrial:
    prefix_size: int
    spill_indices: tuple[int, ...]
    reversed_edges: tuple[tuple[int, int], ...]
    q2_valid: bool
    safe_valid: bool | None
    official_cycles: int | None
    safe_cycles: int | None
    changed_positions: int
    error: str = ""


@dataclass(frozen=True, slots=True)
class CriticalSpillBatchResult:
    baseline_solution: Q2Solution
    baseline_official: Q3TimingResult
    baseline_safe: Q3TimingResult
    best_solution: Q2Solution
    best_official: Q3TimingResult
    best_safe: Q3TimingResult
    best_prefix_size: int | None
    trials: tuple[CriticalSpillBatchTrial, ...]

    @property
    def improved(self) -> bool:
        return self.best_official.total_cycles < self.baseline_official.total_cycles


@dataclass(frozen=True, slots=True)
class IterativeCriticalSpillBatchResult:
    baseline_solution: Q2Solution
    baseline_official: Q3TimingResult
    baseline_safe: Q3TimingResult
    final_solution: Q2Solution
    final_official: Q3TimingResult
    final_safe: Q3TimingResult
    rounds: tuple[CriticalSpillBatchResult, ...]

    @property
    def improved(self) -> bool:
        return self.final_official.total_cycles < self.baseline_official.total_cycles

    @property
    def accepted_rounds(self) -> int:
        return sum(1 for result in self.rounds if result.improved)

    @property
    def saturated(self) -> bool:
        return bool(self.rounds) and not self.rounds[-1].improved


def _topological_order(
    nodes,
    edges: set[tuple[int, int]],
    original_pos: dict[int, int],
) -> tuple[int, ...]:
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
        raise ValueError("critical SPILL batch reversal creates a precedence cycle")
    return tuple(order)


def _pipe_predecessor(solution: Q2Solution, nodes, node_id: int) -> int | None:
    pipe = nodes[node_id].pipe
    if pipe is None:
        return None
    previous: int | None = None
    for current in solution.schedule:
        if nodes[current].pipe != pipe:
            continue
        if current == node_id:
            return previous
        previous = current
    raise ValueError(f"node {node_id} absent from its pipe sequence")


def critical_spill_candidates(
    graph: ComputeGraph,
    solution: Q2Solution,
    official_timing: Q3TimingResult,
    *,
    max_switches: int = 64,
) -> tuple[CriticalSpillCandidate, ...]:
    """Rank critical SPILL_OUT->SPILL_IN boundaries by serialized run weight."""
    if max_switches <= 0:
        return ()

    nodes = augmented_nodes(graph, solution)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    s_edges = spill_edges(graph, solution, nodes, pos)
    path = official_timing.critical_path
    n = graph.node_count
    ranked: list[tuple[int, int, int, CriticalSpillCandidate]] = []

    for i, (u, v) in enumerate(zip(path, path[1:])):
        if (u, v) not in s_edges or u < n or v < n:
            continue
        if nodes[u].op != "SPILL_OUT" or nodes[v].op != "SPILL_IN":
            continue
        out_relative = u - n
        in_relative = v - n
        if out_relative % 2 != 0 or in_relative % 2 != 1:
            continue
        spill_index = out_relative // 2
        if in_relative // 2 != spill_index:
            continue
        if nodes[u].pipe != "MTE3" or nodes[v].pipe != "MTE2":
            continue

        left_cycles = 0
        j = i
        while j >= 0 and nodes[path[j]].pipe == "MTE3":
            left_cycles += node_cycles(nodes[path[j]])
            j -= 1
        right_cycles = 0
        j = i + 1
        while j < len(path) and nodes[path[j]].pipe == "MTE2":
            right_cycles += node_cycles(nodes[path[j]])
            j += 1

        candidate = CriticalSpillCandidate(
            spill_index,
            u,
            v,
            left_cycles,
            right_cycles,
        )
        ranked.append(
            (
                -candidate.combined_run_cycles,
                -max(left_cycles, right_cycles),
                spill_index,
                candidate,
            )
        )

    ranked.sort()
    return tuple(item[-1] for item in ranked[:max_switches])


def search_q3_critical_spill_batches(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_switches: int = 64,
    prefix_sizes: tuple[int, ...] = (1, 2, 4, 8, 16, 24, 32, 48, 64),
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> CriticalSpillBatchResult:
    """Reverse ranked prefixes of mutable MTE3 edges before critical SPILL_OUTs.

    Original graph, SPILL dependency, and residency-safe reuse edges remain fixed.
    Every candidate must preserve exact SPILL records, spill count and extra
    traffic, and must pass strict Q2 plus both official and residency-safe Q3
    replay before it can be selected.
    """
    if max_switches <= 0:
        raise ValueError("max_switches must be positive")
    normalized_prefixes = tuple(sorted({int(size) for size in prefix_sizes if 0 < int(size) <= max_switches}))
    if not normalized_prefixes:
        raise ValueError("prefix_sizes must contain at least one positive size <= max_switches")

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
    ranked = critical_spill_candidates(
        graph,
        solution,
        baseline_official,
        max_switches=max_switches,
    )

    mutable: list[tuple[int, tuple[int, int]]] = []
    for candidate in ranked:
        prev_out = _pipe_predecessor(solution, nodes, candidate.out_id)
        if prev_out is None:
            continue
        edge = (prev_out, candidate.out_id)
        if edge in pipes and edge not in fixed:
            mutable.append((candidate.spill_index, edge))

    base_spills = tuple((spill.buf_id, spill.new_offset) for spill in solution.spills)
    best_solution = solution
    best_official = baseline_official
    best_safe = baseline_safe
    best_prefix_size: int | None = None
    trials: list[CriticalSpillBatchTrial] = []

    actual_sizes = sorted({min(size, len(mutable)) for size in normalized_prefixes if mutable})
    for size in actual_sizes:
        selected = mutable[:size]
        spill_indices = tuple(item[0] for item in selected)
        reverse_edges = tuple(item[1] for item in selected)
        try:
            constrained = set(fixed)
            constrained.update(pipes - set(reverse_edges))
            constrained.update((v, u) for u, v in reverse_edges)
            order = _topological_order(nodes, constrained, pos)
            changed = sum(a != b for a, b in zip(order, solution.schedule))
            candidate_solution = Q2Solution(order, solution.initial_offsets, solution.spills)
            q2 = validate_q2_solution(graph, candidate_solution)
            if not q2.ok:
                trials.append(
                    CriticalSpillBatchTrial(
                        size,
                        spill_indices,
                        reverse_edges,
                        False,
                        False,
                        None,
                        None,
                        changed,
                        "; ".join(q2.errors[:2]),
                    )
                )
                continue
            if q2.spill_count != base_q2.spill_count or q2.extra_traffic != base_q2.extra_traffic:
                raise AssertionError("critical SPILL batch changed Q2 traffic/spill count")
            if tuple((s.buf_id, s.new_offset) for s in candidate_solution.spills) != base_spills:
                raise AssertionError("critical SPILL batch changed spill records")

            official = evaluate_q3_solution(graph, candidate_solution, reuse_mode="official_literal")
            official.require_ok()
            if official.total_cycles > best_official.total_cycles:
                trials.append(
                    CriticalSpillBatchTrial(
                        size,
                        spill_indices,
                        reverse_edges,
                        True,
                        None,
                        official.total_cycles,
                        None,
                        changed,
                        "residency-safe replay skipped: official score not competitive",
                    )
                )
                continue

            safe = evaluate_q3_solution(graph, candidate_solution, reuse_mode="residency_safe")
            if not safe.ok:
                trials.append(
                    CriticalSpillBatchTrial(
                        size,
                        spill_indices,
                        reverse_edges,
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
                CriticalSpillBatchTrial(
                    size,
                    spill_indices,
                    reverse_edges,
                    True,
                    True,
                    official.total_cycles,
                    safe.total_cycles,
                    changed,
                )
            )
            if (official.total_cycles, safe.total_cycles, size) < (
                best_official.total_cycles,
                best_safe.total_cycles,
                best_prefix_size if best_prefix_size is not None else 1 << 60,
            ):
                best_solution = candidate_solution
                best_official = official
                best_safe = safe
                best_prefix_size = size
        except Exception as exc:
            trials.append(
                CriticalSpillBatchTrial(
                    size,
                    spill_indices,
                    reverse_edges,
                    False,
                    False,
                    None,
                    None,
                    0,
                    f"{type(exc).__name__}: {exc}",
                )
            )

    final_q2 = validate_q2_solution(graph, best_solution)
    final_q2.require_ok()
    if final_q2.spill_count != base_q2.spill_count or final_q2.extra_traffic != base_q2.extra_traffic:
        raise AssertionError("critical SPILL batch final Q2 invariants changed")
    if tuple((s.buf_id, s.new_offset) for s in best_solution.spills) != base_spills:
        raise AssertionError("critical SPILL batch final spill records changed")
    final_official = evaluate_q3_solution(graph, best_solution, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, best_solution, reuse_mode="residency_safe")
    final_safe.require_ok()

    return CriticalSpillBatchResult(
        solution,
        baseline_official,
        baseline_safe,
        best_solution,
        final_official,
        final_safe,
        best_prefix_size,
        tuple(trials),
    )


def optimize_q3_critical_spill_batches(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_rounds: int = 12,
    max_switches: int = 64,
    prefix_sizes: tuple[int, ...] = (1, 2, 4, 8, 16, 24, 32, 48, 64),
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> IterativeCriticalSpillBatchResult:
    """Fresh-rerank critical-SPILL batches until the first non-improving round."""
    if max_rounds <= 0:
        raise ValueError("max_rounds must be positive")
    if max_switches <= 0:
        raise ValueError("max_switches must be positive")
    normalized_prefixes = tuple(sorted({int(size) for size in prefix_sizes if 0 < int(size) <= max_switches}))
    if not normalized_prefixes:
        raise ValueError("prefix_sizes must contain at least one positive size <= max_switches")

    base_q2 = validate_q2_solution(graph, solution)
    base_q2.require_ok()
    if baseline_official is None:
        baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    if baseline_safe is None:
        baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()
    base_spills = tuple((spill.buf_id, spill.new_offset) for spill in solution.spills)

    current = solution
    current_official = baseline_official
    current_safe = baseline_safe
    rounds: list[CriticalSpillBatchResult] = []

    for _ in range(max_rounds):
        result = search_q3_critical_spill_batches(
            graph,
            current,
            max_switches=max_switches,
            prefix_sizes=normalized_prefixes,
            baseline_official=current_official,
            baseline_safe=current_safe,
        )
        rounds.append(result)
        if result.baseline_official.total_cycles != current_official.total_cycles:
            raise AssertionError("critical-SPILL batch round official baseline drifted")
        if result.baseline_safe.total_cycles != current_safe.total_cycles:
            raise AssertionError("critical-SPILL batch round safe baseline drifted")
        if not result.improved:
            break
        if result.best_official.total_cycles >= current_official.total_cycles:
            raise AssertionError("accepted critical-SPILL batch round was not strictly improving")
        current = result.best_solution
        current_official = result.best_official
        current_safe = result.best_safe

    final_q2 = validate_q2_solution(graph, current)
    final_q2.require_ok()
    if final_q2.spill_count != base_q2.spill_count:
        raise AssertionError("iterative critical-SPILL batches changed spill count")
    if final_q2.extra_traffic != base_q2.extra_traffic:
        raise AssertionError("iterative critical-SPILL batches changed extra traffic")
    if tuple((spill.buf_id, spill.new_offset) for spill in current.spills) != base_spills:
        raise AssertionError("iterative critical-SPILL batches changed spill records")

    final_official = evaluate_q3_solution(graph, current, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, current, reuse_mode="residency_safe")
    final_safe.require_ok()
    if final_official.total_cycles != current_official.total_cycles:
        raise AssertionError("iterative critical-SPILL final official replay mismatch")
    if final_safe.total_cycles != current_safe.total_cycles:
        raise AssertionError("iterative critical-SPILL final safe replay mismatch")
    if final_official.total_cycles > baseline_official.total_cycles:
        raise AssertionError("iterative critical-SPILL batches regressed official cycles")

    return IterativeCriticalSpillBatchResult(
        solution,
        baseline_official,
        baseline_safe,
        current,
        final_official,
        final_safe,
        tuple(rounds),
    )
