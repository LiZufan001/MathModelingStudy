from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_conv_local_recolor import LocalRecolorSearchResult, search_q3_critical_recolor
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult


@dataclass(frozen=True, slots=True)
class GreedyLocalRecolorResult:
    baseline_solution: Q2Solution
    baseline_official: Q3TimingResult
    baseline_safe: Q3TimingResult
    final_solution: Q2Solution
    final_official: Q3TimingResult
    final_safe: Q3TimingResult
    rounds: tuple[LocalRecolorSearchResult, ...]

    @property
    def improved(self) -> bool:
        return self.final_official.total_cycles < self.baseline_official.total_cycles

    @property
    def accepted_rounds(self) -> int:
        return sum(1 for round_result in self.rounds if round_result.improved)


def optimize_q3_critical_recolor_greedy(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_rounds: int = 3,
    max_targets: int = 6,
    max_starts: int = 12,
) -> GreedyLocalRecolorResult:
    """Monotone multi-round local recoloring with strict replay at every move.

    Each round searches only the current official critical-path reuse targets and
    accepts at most one best initial-offset move.  The next round recomputes the
    critical path from the accepted solution, so two or three moves can compose
    without an O(K^2) pair enumeration.  SPILL identity/order/count and official
    extra traffic are asserted invariant relative to the input solution.
    """

    if max_rounds <= 0:
        raise ValueError("max_rounds must be positive")

    base_q2 = validate_q2_solution(graph, solution)
    base_q2.require_ok()
    baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()
    base_spills = tuple(spill.buf_id for spill in solution.spills)

    current = solution
    current_official = baseline_official
    current_safe = baseline_safe
    rounds: list[LocalRecolorSearchResult] = []

    for _ in range(max_rounds):
        result = search_q3_critical_recolor(
            graph,
            current,
            max_targets=max_targets,
            max_starts=max_starts,
        )
        rounds.append(result)
        if result.baseline_official.total_cycles != current_official.total_cycles:
            raise AssertionError("local recolor round baseline official timing drifted")
        if result.baseline_safe.total_cycles != current_safe.total_cycles:
            raise AssertionError("local recolor round baseline safe timing drifted")
        if not result.improved:
            break
        if result.best_official.total_cycles >= current_official.total_cycles:
            raise AssertionError("accepted local recolor round was not strictly improving")
        current = result.best_solution
        current_official = result.best_official
        current_safe = result.best_safe

    final_q2 = validate_q2_solution(graph, current)
    final_q2.require_ok()
    if final_q2.extra_traffic != base_q2.extra_traffic:
        raise AssertionError("greedy local recolor changed extra traffic")
    if final_q2.spill_count != base_q2.spill_count:
        raise AssertionError("greedy local recolor changed spill count")
    if tuple(spill.buf_id for spill in current.spills) != base_spills:
        raise AssertionError("greedy local recolor changed spill victim identity/order")

    final_official = evaluate_q3_solution(graph, current, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, current, reuse_mode="residency_safe")
    final_safe.require_ok()
    if final_official.total_cycles != current_official.total_cycles:
        raise AssertionError("final greedy official replay mismatch")
    if final_safe.total_cycles != current_safe.total_cycles:
        raise AssertionError("final greedy safe replay mismatch")
    if final_official.total_cycles > baseline_official.total_cycles:
        raise AssertionError("greedy local recolor regressed official cycles")

    return GreedyLocalRecolorResult(
        solution,
        baseline_official,
        baseline_safe,
        current,
        final_official,
        final_safe,
        tuple(rounds),
    )
