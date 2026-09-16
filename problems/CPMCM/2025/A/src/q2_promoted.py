from __future__ import annotations

from dataclasses import dataclass

from evaluator import Q1Evaluation
from model import ComputeGraph
from q2_allocator import Q2AllocationResult, allocate_q2_baseline
from q2_optimized import Q2ExpectedMetric, schedule_q2_optimized
from q2_reuse_scheduler import Q2ReuseScheduleResult
from q3_tradeoff_scheduler import schedule_q3_critical_window

POLISH_WINDOWS = (0, 1, 2, 3)

EXPECTED_Q2_PROMOTED: dict[str, Q2ExpectedMetric] = {
    "Matmul_Case0": Q2ExpectedMetric(9216, 225, 28800),
    "Matmul_Case1": Q2ExpectedMetric(34816, 3361, 430208),
    "FlashAttention_Case0": Q2ExpectedMetric(26728, 316, 54016),
    "FlashAttention_Case1": Q2ExpectedMetric(106992, 1782, 242552),
    "Conv_Case0": Q2ExpectedMetric(80170, 522, 177904),
    "Conv_Case1": Q2ExpectedMetric(310408, 9646, 721464),
}


@dataclass(frozen=True, slots=True)
class Q2PromotedResult:
    order: tuple[int, ...]
    evaluation: Q1Evaluation
    allocation: Q2AllocationResult
    polish_window: int
    changed_positions: int
    base_schedule: Q2ReuseScheduleResult

    @property
    def solution(self):
        return self.allocation.solution

    @property
    def validation(self):
        return self.allocation.validation

    @property
    def affinity_decisions(self) -> int:
        return self.base_schedule.affinity_decisions

    @property
    def footprint_decisions(self) -> int:
        return self.base_schedule.footprint_decisions


def solve_q2_promoted(graph: ComputeGraph) -> Q2PromotedResult:
    """Return the promoted strict Q2 solution with a small generic polish portfolio.

    The existing footprint-aware scheduler remains the base policy.  Around that
    known-good order we try only windows 0..3 of the graph-generic critical-window
    scheduler.  Candidates must preserve or improve the base Q1 peak and must pass
    the full Q2 allocator/validator.  The production objective is then selected
    lexicographically by official extra traffic, spill count, Q1 peak, amount of
    reordering, and finally smaller window.

    Importantly this function returns the already validated allocation, so callers
    do not pay for the four-candidate portfolio and then allocate the winner again.
    """

    base = schedule_q2_optimized(graph)
    base_peak = base.evaluation.peak_residency
    candidates: list[
        tuple[int, int, int, int, int, tuple[int, ...], Q1Evaluation, Q2AllocationResult]
    ] = []

    for window in POLISH_WINDOWS:
        if window == 0:
            order = base.order
            evaluation = base.evaluation
            changed = 0
        else:
            scheduled = schedule_q3_critical_window(graph, base.order, window=window)
            order = scheduled.order
            evaluation = scheduled.evaluation
            changed = scheduled.changed_positions

        if evaluation.peak_residency > base_peak:
            continue

        allocation = allocate_q2_baseline(graph, order)
        allocation.validation.require_ok()
        candidates.append(
            (
                allocation.validation.extra_traffic,
                allocation.validation.spill_count,
                evaluation.peak_residency,
                changed,
                window,
                order,
                evaluation,
                allocation,
            )
        )

    if not candidates:
        raise RuntimeError("Q2 promoted polish portfolio has no strict-valid candidate")

    (
        _traffic,
        _spills,
        _peak,
        changed,
        window,
        order,
        evaluation,
        allocation,
    ) = min(candidates, key=lambda item: item[:5])
    return Q2PromotedResult(
        order=order,
        evaluation=evaluation,
        allocation=allocation,
        polish_window=window,
        changed_positions=changed,
        base_schedule=base,
    )
