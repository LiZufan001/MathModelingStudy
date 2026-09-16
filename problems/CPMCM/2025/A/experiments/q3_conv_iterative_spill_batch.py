from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_critical_spill_switch_batch import (
    CriticalSpillBatchResult,
    search_q3_critical_spill_out_batches,
)
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult


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
        return bool(self.rounds and not self.rounds[-1].improved)


def optimize_q3_critical_spill_batch_iterative(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_rounds: int = 4,
    max_switches: int = 64,
    prefix_sizes: tuple[int, ...] = (1, 2, 4, 8, 16, 24, 32, 48, 64),
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> IterativeCriticalSpillBatchResult:
    """Fresh-rerank critical SPILL_OUT batches until strict local saturation.

    Each accepted round recomputes the official critical path from the newly
    accepted schedule before ranking the next set of SPILL_OUT/MTE3 bubbles.
    This differs from merely extending one static ranked prefix: the bottleneck
    is allowed to move between rounds.  Selection minimizes official-literal
    cycles, while every accepted candidate must also pass residency-safe replay
    and preserve the exact Q2 SPILL records, spill count and extra traffic.
    """
    if max_rounds <= 0:
        raise ValueError("max_rounds must be positive")
    if max_switches <= 0:
        raise ValueError("max_switches must be positive")
    normalized_prefixes = tuple(
        sorted({int(size) for size in prefix_sizes if 0 < int(size) <= max_switches})
    )
    if not normalized_prefixes:
        raise ValueError("prefix_sizes must contain a positive size <= max_switches")

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
        result = search_q3_critical_spill_out_batches(
            graph,
            current,
            max_switches=max_switches,
            prefix_sizes=normalized_prefixes,
            baseline_official=current_official,
            baseline_safe=current_safe,
        )
        rounds.append(result)
        if result.baseline_official.total_cycles != current_official.total_cycles:
            raise AssertionError("iterative batch baseline official timing drifted")
        if result.baseline_safe.total_cycles != current_safe.total_cycles:
            raise AssertionError("iterative batch baseline safe timing drifted")
        if not result.improved:
            break
        if result.best_official.total_cycles >= current_official.total_cycles:
            raise AssertionError("accepted iterative batch round was not strictly improving")
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
        raise AssertionError("iterative batch final official replay mismatch")
    if final_safe.total_cycles != current_safe.total_cycles:
        raise AssertionError("iterative batch final safe replay mismatch")
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
