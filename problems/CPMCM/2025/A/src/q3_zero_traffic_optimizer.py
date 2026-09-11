from __future__ import annotations

from dataclasses import dataclass

from model import ComputeGraph
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_address_portfolio import select_q3_address_portfolio
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult
from q3_pipeline_scheduler import reschedule_q3_critical


@dataclass(frozen=True, slots=True)
class Q3ZeroTrafficStep:
    round_index: int
    transformation: str
    detail: str
    cycles_before: int
    cycles_after: int | None
    accepted: bool
    error: str = ""


@dataclass(frozen=True, slots=True)
class Q3ZeroTrafficResult:
    solution: Q2Solution
    timing: Q3TimingResult
    steps: tuple[Q3ZeroTrafficStep, ...]
    original_cycles: int
    spill_count: int
    extra_traffic: int


def optimize_q3_zero_traffic(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_rounds: int = 2,
) -> Q3ZeroTrafficResult:
    """Monotone alternating address/pipeline optimization at fixed Q2 traffic.

    Each round first chooses the best strictly valid address layout from the
    generic address portfolio, then tries critical-bottom-level pipeline
    rescheduling. A transformation is accepted only when the independent safe Q3
    evaluator reports strictly fewer cycles. Spill victim identity/order/count and
    traffic are immutable throughout the search; only reload offsets may change
    during address recoloring.
    """

    if max_rounds <= 0:
        raise ValueError("max_rounds must be positive")
    original_q2 = validate_q2_solution(graph, solution)
    original_q2.require_ok()
    original_spill_buffers = tuple(spill.buf_id for spill in solution.spills)

    def require_same_spill_decisions(candidate: Q2Solution) -> None:
        candidate_buffers = tuple(spill.buf_id for spill in candidate.spills)
        if candidate_buffers != original_spill_buffers:
            raise AssertionError("zero-traffic Q3 optimization changed spill victim identity/order")

    current = solution
    current_timing = evaluate_q3_solution(graph, current, reuse_mode="residency_safe")
    current_timing.require_ok()
    original_cycles = current_timing.total_cycles
    steps: list[Q3ZeroTrafficStep] = []

    for round_index in range(1, max_rounds + 1):
        round_start_cycles = current_timing.total_cycles

        try:
            address = select_q3_address_portfolio(graph, current)
            require_same_spill_decisions(address.solution)
            accepted = address.timing.total_cycles < current_timing.total_cycles
            steps.append(
                Q3ZeroTrafficStep(
                    round_index,
                    "address_portfolio",
                    address.policy,
                    current_timing.total_cycles,
                    address.timing.total_cycles,
                    accepted,
                )
            )
            if accepted:
                current = address.solution
                current_timing = address.timing
        except Exception as exc:
            steps.append(
                Q3ZeroTrafficStep(
                    round_index,
                    "address_portfolio",
                    "rejected",
                    current_timing.total_cycles,
                    None,
                    False,
                    f"{type(exc).__name__}: {exc}",
                )
            )

        try:
            critical = reschedule_q3_critical(graph, current)
            require_same_spill_decisions(critical.solution)
            accepted = critical.timing.total_cycles < current_timing.total_cycles
            steps.append(
                Q3ZeroTrafficStep(
                    round_index,
                    "critical_reschedule",
                    f"changed_positions={critical.changed_positions}",
                    current_timing.total_cycles,
                    critical.timing.total_cycles,
                    accepted,
                )
            )
            if accepted:
                current = critical.solution
                current_timing = critical.timing
        except Exception as exc:
            steps.append(
                Q3ZeroTrafficStep(
                    round_index,
                    "critical_reschedule",
                    "rejected",
                    current_timing.total_cycles,
                    None,
                    False,
                    f"{type(exc).__name__}: {exc}",
                )
            )

        if current_timing.total_cycles == round_start_cycles:
            break

    require_same_spill_decisions(current)
    final_q2 = validate_q2_solution(graph, current)
    final_q2.require_ok()
    if final_q2.spill_count != original_q2.spill_count:
        raise AssertionError("zero-traffic Q3 optimization changed spill count")
    if final_q2.extra_traffic != original_q2.extra_traffic:
        raise AssertionError("zero-traffic Q3 optimization changed extra traffic")
    final_timing = evaluate_q3_solution(graph, current, reuse_mode="residency_safe")
    final_timing.require_ok()
    if final_timing.total_cycles != current_timing.total_cycles:
        raise AssertionError("final Q3 replay disagrees with accepted timing")
    if final_timing.total_cycles > original_cycles:
        raise AssertionError("monotone Q3 optimizer regressed total cycles")

    return Q3ZeroTrafficResult(
        current,
        final_timing,
        tuple(steps),
        original_cycles,
        final_q2.spill_count,
        final_q2.extra_traffic,
    )
