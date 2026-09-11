from __future__ import annotations

from dataclasses import dataclass

from model import ComputeGraph
from q2_model import Q2Solution
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult
from q3_reallocator import AddressPolicy, repack_q3_addresses

PORTFOLIO_POLICIES: tuple[AddressPolicy, ...] = (
    "best_fit",
    "first_fit_low",
    "first_fit_high",
    "next_fit",
)


@dataclass(frozen=True, slots=True)
class Q3AddressPortfolioResult:
    solution: Q2Solution
    timing: Q3TimingResult
    policy: str
    rejected: tuple[tuple[str, str], ...]


def select_q3_address_portfolio(
    graph: ComputeGraph,
    solution: Q2Solution,
) -> Q3AddressPortfolioResult:
    """Choose the lowest safe-cycle physical layout without changing traffic.

    Selection is graph-generic and evaluator-driven: there are no case/operator
    names in the decision. Invalid recolorings are retained as rejection evidence.
    Exact ties prefer the supplied layout, avoiding gratuitous address changes.
    """

    baseline = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline.require_ok()
    candidates: list[tuple[int, int, str, Q2Solution, Q3TimingResult]] = [
        (baseline.total_cycles, 0, "original_q2_addresses", solution, baseline)
    ]
    rejected: list[tuple[str, str]] = []

    for rank, policy in enumerate(PORTFOLIO_POLICIES, start=1):
        try:
            repacked = repack_q3_addresses(graph, solution, policy).solution
            timing = evaluate_q3_solution(graph, repacked, reuse_mode="residency_safe")
            timing.require_ok()
            candidates.append((timing.total_cycles, rank, policy, repacked, timing))
        except Exception as exc:
            rejected.append((policy, f"{type(exc).__name__}: {exc}"))

    _, _, policy, best_solution, best_timing = min(
        candidates,
        key=lambda item: (item[0], item[1], item[2]),
    )
    return Q3AddressPortfolioResult(
        best_solution,
        best_timing,
        policy,
        tuple(rejected),
    )
