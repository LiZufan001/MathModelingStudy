from __future__ import annotations

from dataclasses import dataclass

from model import ComputeGraph
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_address_portfolio import PORTFOLIO_POLICIES
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult
from q3_pipeline_scheduler import reschedule_q3_critical
from q3_reallocator import repack_q3_addresses


@dataclass(frozen=True, slots=True)
class Q3OfficialStep:
    round_index: int
    transformation: str
    detail: str
    official_before: int
    official_after: int | None
    safe_before: int
    safe_after: int | None
    accepted: bool
    error: str = ""


@dataclass(frozen=True, slots=True)
class Q3OfficialZeroTrafficResult:
    solution: Q2Solution
    safe_timing: Q3TimingResult
    official_timing: Q3TimingResult
    steps: tuple[Q3OfficialStep, ...]
    original_safe_cycles: int
    original_official_cycles: int
    spill_count: int
    extra_traffic: int


@dataclass(frozen=True, slots=True)
class _OfficialAddressChoice:
    solution: Q2Solution
    safe_timing: Q3TimingResult
    official_timing: Q3TimingResult
    policy: str
    rejected: tuple[tuple[str, str], ...]


def _select_official_address_portfolio(
    graph: ComputeGraph,
    solution: Q2Solution,
) -> _OfficialAddressChoice:
    """Choose the lowest Appendix-C literal cycles among safe-valid recolorings.

    `residency_safe` is a hard feasibility gate, not the ranking objective. The
    supplied layout is always candidate rank 0, so exact official ties avoid
    gratuitous address changes.
    """

    baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()
    baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    candidates: list[
        tuple[int, int, str, Q2Solution, Q3TimingResult, Q3TimingResult]
    ] = [
        (
            baseline_official.total_cycles,
            0,
            "original_q2_addresses",
            solution,
            baseline_safe,
            baseline_official,
        )
    ]
    rejected: list[tuple[str, str]] = []

    for rank, policy in enumerate(PORTFOLIO_POLICIES, start=1):
        try:
            repacked = repack_q3_addresses(graph, solution, policy).solution
            safe = evaluate_q3_solution(graph, repacked, reuse_mode="residency_safe")
            safe.require_ok()
            official = evaluate_q3_solution(graph, repacked, reuse_mode="official_literal")
            official.require_ok()
            candidates.append(
                (
                    official.total_cycles,
                    rank,
                    policy,
                    repacked,
                    safe,
                    official,
                )
            )
        except Exception as exc:
            rejected.append((policy, f"{type(exc).__name__}: {exc}"))

    _, _, policy, best_solution, best_safe, best_official = min(
        candidates,
        key=lambda item: (item[0], item[1], item[2]),
    )
    return _OfficialAddressChoice(
        best_solution,
        best_safe,
        best_official,
        policy,
        tuple(rejected),
    )


def optimize_q3_official_zero_traffic(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_rounds: int = 2,
) -> Q3OfficialZeroTrafficResult:
    """Monotone Q3 optimizer whose acceptance target is Appendix-C literal cycles.

    Q2 traffic, spill count and spill victim identity/order are immutable. Every
    proposed address or pipeline transformation must independently pass the
    stronger `residency_safe` evaluator, but it is accepted only when
    `official_literal` cycles strictly decrease. Safe cycles are reported for
    audit and are not required to be monotone.
    """

    if max_rounds <= 0:
        raise ValueError("max_rounds must be positive")

    original_q2 = validate_q2_solution(graph, solution)
    original_q2.require_ok()
    original_spill_buffers = tuple(spill.buf_id for spill in solution.spills)

    def require_same_spill_decisions(candidate: Q2Solution) -> None:
        candidate_buffers = tuple(spill.buf_id for spill in candidate.spills)
        if candidate_buffers != original_spill_buffers:
            raise AssertionError(
                "official Q3 optimization changed spill victim identity/order"
            )

    current = solution
    current_safe = evaluate_q3_solution(graph, current, reuse_mode="residency_safe")
    current_safe.require_ok()
    current_official = evaluate_q3_solution(graph, current, reuse_mode="official_literal")
    current_official.require_ok()
    original_safe_cycles = current_safe.total_cycles
    original_official_cycles = current_official.total_cycles
    steps: list[Q3OfficialStep] = []

    for round_index in range(1, max_rounds + 1):
        round_start_official = current_official.total_cycles

        try:
            address = _select_official_address_portfolio(graph, current)
            require_same_spill_decisions(address.solution)
            accepted = address.official_timing.total_cycles < current_official.total_cycles
            steps.append(
                Q3OfficialStep(
                    round_index,
                    "address_portfolio",
                    address.policy,
                    current_official.total_cycles,
                    address.official_timing.total_cycles,
                    current_safe.total_cycles,
                    address.safe_timing.total_cycles,
                    accepted,
                )
            )
            if accepted:
                current = address.solution
                current_safe = address.safe_timing
                current_official = address.official_timing
        except Exception as exc:
            steps.append(
                Q3OfficialStep(
                    round_index,
                    "address_portfolio",
                    "rejected",
                    current_official.total_cycles,
                    None,
                    current_safe.total_cycles,
                    None,
                    False,
                    f"{type(exc).__name__}: {exc}",
                )
            )

        try:
            critical = reschedule_q3_critical(graph, current)
            require_same_spill_decisions(critical.solution)
            candidate_safe = critical.timing
            candidate_safe.require_ok()
            candidate_official = evaluate_q3_solution(
                graph,
                critical.solution,
                reuse_mode="official_literal",
            )
            candidate_official.require_ok()
            accepted = candidate_official.total_cycles < current_official.total_cycles
            steps.append(
                Q3OfficialStep(
                    round_index,
                    "critical_reschedule",
                    f"changed_positions={critical.changed_positions}",
                    current_official.total_cycles,
                    candidate_official.total_cycles,
                    current_safe.total_cycles,
                    candidate_safe.total_cycles,
                    accepted,
                )
            )
            if accepted:
                current = critical.solution
                current_safe = candidate_safe
                current_official = candidate_official
        except Exception as exc:
            steps.append(
                Q3OfficialStep(
                    round_index,
                    "critical_reschedule",
                    "rejected",
                    current_official.total_cycles,
                    None,
                    current_safe.total_cycles,
                    None,
                    False,
                    f"{type(exc).__name__}: {exc}",
                )
            )

        if current_official.total_cycles == round_start_official:
            break

    require_same_spill_decisions(current)
    final_q2 = validate_q2_solution(graph, current)
    final_q2.require_ok()
    if final_q2.spill_count != original_q2.spill_count:
        raise AssertionError("official Q3 optimization changed spill count")
    if final_q2.extra_traffic != original_q2.extra_traffic:
        raise AssertionError("official Q3 optimization changed extra traffic")

    final_safe = evaluate_q3_solution(graph, current, reuse_mode="residency_safe")
    final_safe.require_ok()
    final_official = evaluate_q3_solution(graph, current, reuse_mode="official_literal")
    final_official.require_ok()
    if final_safe.total_cycles != current_safe.total_cycles:
        raise AssertionError("final safe replay disagrees with accepted timing")
    if final_official.total_cycles != current_official.total_cycles:
        raise AssertionError("final official replay disagrees with accepted timing")
    if final_official.total_cycles > original_official_cycles:
        raise AssertionError("official-objective Q3 optimizer regressed official cycles")

    return Q3OfficialZeroTrafficResult(
        current,
        final_safe,
        final_official,
        tuple(steps),
        original_safe_cycles,
        original_official_cycles,
        final_q2.spill_count,
        final_q2.extra_traffic,
    )
