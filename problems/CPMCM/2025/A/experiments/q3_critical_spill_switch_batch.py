from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_critical_pipe_swap import _topological_order
from q3_critical_spill_switch import critical_spill_switch_candidates, _pipe_predecessor
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


def search_q3_critical_spill_out_batches(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_switches: int = 8,
    prefix_sizes: tuple[int, ...] = (2, 4, 8),
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> CriticalSpillBatchResult:
    """Try a few batched prefixes of critical SPILL_OUT bubbles.

    This is an experimental evaluator-saving companion to the greedy one-move
    search.  It ranks the same critical SPILL switches, keeps only mutable
    `out_earlier` MTE3 adjacencies, then reverses several top-ranked edges in one
    constrained topological sort.  Only a small set of prefix sizes is replayed.
    Every candidate still passes strict Q2, official-literal and residency-safe
    validation before it can be selected.
    """
    if max_switches <= 0:
        raise ValueError("max_switches must be positive")
    normalized_prefixes = tuple(sorted({int(size) for size in prefix_sizes if int(size) > 0}))
    if not normalized_prefixes:
        raise ValueError("prefix_sizes must contain at least one positive size")

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
    ranked = critical_spill_switch_candidates(
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
            candidate_spills = tuple((s.buf_id, s.new_offset) for s in candidate_solution.spills)
            if candidate_spills != base_spills:
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
