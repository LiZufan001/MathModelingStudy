from __future__ import annotations

from dataclasses import dataclass

from model import ComputeGraph
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_model import Q3TimingResult
from q3_official_optimizer import Q3OfficialZeroTrafficResult, optimize_q3_official_zero_traffic
from q3_spill_batch_optimizer import (
    IterativeCriticalSpillBatchResult,
    optimize_q3_critical_spill_batches,
)


@dataclass(frozen=True, slots=True)
class Q3OfficialSpillResult:
    solution: Q2Solution
    safe_timing: Q3TimingResult
    official_timing: Q3TimingResult
    core: Q3OfficialZeroTrafficResult
    spill_batches: IterativeCriticalSpillBatchResult | None
    spill_count: int
    extra_traffic: int

    @property
    def spill_batch_improved(self) -> bool:
        return self.spill_batches is not None and self.spill_batches.improved

    @property
    def spill_batch_saturated(self) -> bool:
        return self.spill_batches is not None and self.spill_batches.saturated


def optimize_q3_official_with_spill_batches(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_rounds: int = 2,
    recolor_max_rounds: int = 0,
    recolor_max_targets: int = 6,
    recolor_max_starts: int = 12,
    spill_batch_max_rounds: int = 0,
    spill_batch_max_switches: int = 64,
    spill_batch_prefix_sizes: tuple[int, ...] = (1, 2, 4, 8, 16, 24, 32, 48, 64),
) -> Q3OfficialSpillResult:
    """Compose the formal fixed-traffic optimizer with critical-SPILL batches.

    The existing address/pipeline/recolor optimizer remains the stable first
    stage.  The optional second stage only changes schedule order by reversing
    selected mutable MTE3 serialization edges immediately before critical
    SPILL_OUTs.  Exact SPILL records, count and extra traffic are immutable;
    every accepted candidate must pass both official and residency-safe replay.
    """
    if spill_batch_max_rounds < 0:
        raise ValueError("spill_batch_max_rounds must be nonnegative")

    original_q2 = validate_q2_solution(graph, solution)
    original_q2.require_ok()
    original_spills = tuple((spill.buf_id, spill.new_offset) for spill in solution.spills)

    core = optimize_q3_official_zero_traffic(
        graph,
        solution,
        max_rounds=max_rounds,
        recolor_max_rounds=recolor_max_rounds,
        recolor_max_targets=recolor_max_targets,
        recolor_max_starts=recolor_max_starts,
    )

    if spill_batch_max_rounds == 0:
        final_solution = core.solution
        final_official = core.official_timing
        final_safe = core.safe_timing
        spill_batches = None
    else:
        spill_batches = optimize_q3_critical_spill_batches(
            graph,
            core.solution,
            max_rounds=spill_batch_max_rounds,
            max_switches=spill_batch_max_switches,
            prefix_sizes=spill_batch_prefix_sizes,
            baseline_official=core.official_timing,
            baseline_safe=core.safe_timing,
        )
        final_solution = spill_batches.final_solution
        final_official = spill_batches.final_official
        final_safe = spill_batches.final_safe

    final_q2 = validate_q2_solution(graph, final_solution)
    final_q2.require_ok()
    final_spills = tuple((spill.buf_id, spill.new_offset) for spill in final_solution.spills)
    if final_spills != original_spills:
        raise AssertionError("formal Q3 spill-batch portfolio changed exact SPILL records")
    if final_q2.spill_count != original_q2.spill_count:
        raise AssertionError("formal Q3 spill-batch portfolio changed spill count")
    if final_q2.extra_traffic != original_q2.extra_traffic:
        raise AssertionError("formal Q3 spill-batch portfolio changed extra traffic")
    if final_official.total_cycles > core.official_timing.total_cycles:
        raise AssertionError("formal Q3 spill-batch post-pass regressed official cycles")
    final_safe.require_ok()
    final_official.require_ok()

    return Q3OfficialSpillResult(
        final_solution,
        final_safe,
        final_official,
        core,
        spill_batches,
        final_q2.spill_count,
        final_q2.extra_traffic,
    )
