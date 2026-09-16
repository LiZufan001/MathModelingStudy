from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_critical_spill_switch import CriticalSpillSwitchResult, search_q3_critical_spill_switch_bubbles
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult


@dataclass(frozen=True, slots=True)
class GreedyCriticalSpillSwitchResult:
    baseline_solution: Q2Solution
    baseline_official: Q3TimingResult
    baseline_safe: Q3TimingResult
    final_solution: Q2Solution
    final_official: Q3TimingResult
    final_safe: Q3TimingResult
    rounds: tuple[CriticalSpillSwitchResult, ...]

    @property
    def improved(self) -> bool:
        return self.final_official.total_cycles < self.baseline_official.total_cycles

    @property
    def accepted_rounds(self) -> int:
        return sum(1 for result in self.rounds if result.improved)


def optimize_q3_critical_spill_switch_greedy(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_rounds: int = 4,
    max_switches: int = 8,
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> GreedyCriticalSpillSwitchResult:
    """Repeatedly accept the best strict critical-SPILL switch until saturation.

    Every round recomputes the official critical path from the last accepted
    schedule, searches the top critical SPILL switches, and accepts only a
    strictly lower official makespan that also passes residency-safe replay.
    SPILL records, count and official extra traffic are invariant across the
    complete greedy chain.
    """
    if max_rounds <= 0:
        raise ValueError("max_rounds must be positive")
    if max_switches <= 0:
        raise ValueError("max_switches must be positive")

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
    rounds: list[CriticalSpillSwitchResult] = []

    for _ in range(max_rounds):
        result = search_q3_critical_spill_switch_bubbles(
            graph,
            current,
            max_switches=max_switches,
            baseline_official=current_official,
            baseline_safe=current_safe,
        )
        rounds.append(result)
        if result.baseline_official.total_cycles != current_official.total_cycles:
            raise AssertionError("critical-SPILL round baseline official timing drifted")
        if result.baseline_safe.total_cycles != current_safe.total_cycles:
            raise AssertionError("critical-SPILL round baseline safe timing drifted")
        if not result.improved:
            break
        if result.best_official.total_cycles >= current_official.total_cycles:
            raise AssertionError("accepted critical-SPILL round was not strictly improving")
        current = result.best_solution
        current_official = result.best_official
        current_safe = result.best_safe

    final_q2 = validate_q2_solution(graph, current)
    final_q2.require_ok()
    if final_q2.spill_count != base_q2.spill_count:
        raise AssertionError("greedy critical-SPILL switches changed spill count")
    if final_q2.extra_traffic != base_q2.extra_traffic:
        raise AssertionError("greedy critical-SPILL switches changed extra traffic")
    final_spills = tuple((spill.buf_id, spill.new_offset) for spill in current.spills)
    if final_spills != base_spills:
        raise AssertionError("greedy critical-SPILL switches changed spill records")

    final_official = evaluate_q3_solution(graph, current, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, current, reuse_mode="residency_safe")
    final_safe.require_ok()
    if final_official.total_cycles != current_official.total_cycles:
        raise AssertionError("greedy critical-SPILL final official replay mismatch")
    if final_safe.total_cycles != current_safe.total_cycles:
        raise AssertionError("greedy critical-SPILL final safe replay mismatch")
    if final_official.total_cycles > baseline_official.total_cycles:
        raise AssertionError("greedy critical-SPILL switches regressed official cycles")

    return GreedyCriticalSpillSwitchResult(
        solution,
        baseline_official,
        baseline_safe,
        current,
        final_official,
        final_safe,
        tuple(rounds),
    )
