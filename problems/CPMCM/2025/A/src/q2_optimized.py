from __future__ import annotations

from dataclasses import dataclass

from model import ComputeGraph
from q2_reuse_scheduler import (
    Q2ReuseScheduleConfig,
    Q2ReuseScheduleResult,
    schedule_q2_reuse_aware,
)


@dataclass(frozen=True, slots=True)
class Q2ExpectedMetric:
    q1_peak: int
    spill_count: int
    extra_traffic: int


# Promoted Q2 scheduling policy. Keep this as the single source of truth for
# production generation; the experiment harness independently re-derives the
# same winner and CI compares both paths through their strict acceptance data.
Q2_OPTIMIZED_CONFIG = Q2ReuseScheduleConfig(
    hot_window=1,
    direct_affinity_weight=0,
    release_weight=0,
    probe_per_buffer=64,
    footprint_weight=1,
    footprint_min_buffers=8,
)


# Strictly replayed Appendix-E acceptance values at promotion time. These are
# intentionally exact regression gates: validity alone is insufficient if a
# later scheduler edit silently gives back the measured spill reduction.
EXPECTED_Q2_OPTIMIZED: dict[str, Q2ExpectedMetric] = {
    "Matmul_Case0": Q2ExpectedMetric(9216, 225, 28800),
    "Matmul_Case1": Q2ExpectedMetric(34816, 3361, 430208),
    "FlashAttention_Case0": Q2ExpectedMetric(26728, 301, 55188),
    "FlashAttention_Case1": Q2ExpectedMetric(106992, 1782, 242552),
    "Conv_Case0": Q2ExpectedMetric(80170, 493, 178212),
    "Conv_Case1": Q2ExpectedMetric(310408, 9550, 724630),
}


def schedule_q2_optimized(graph: ComputeGraph) -> Q2ReuseScheduleResult:
    """Return the promoted Q2 order before strict address allocation/SPILL."""

    return schedule_q2_reuse_aware(graph, Q2_OPTIMIZED_CONFIG)
