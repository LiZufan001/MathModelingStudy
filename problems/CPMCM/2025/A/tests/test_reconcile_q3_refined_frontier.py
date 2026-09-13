from __future__ import annotations

import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1] / "experiments"
sys.path.insert(0, str(EXP))

from reconcile_q3_refined_frontier import _pareto


def _row(case: str, variant: str, traffic: int, cycles: int) -> dict[str, str]:
    return {
        "case": case,
        "variant": variant,
        "sequence": "0" if variant == "zero_traffic" else "1",
        "extra_traffic": str(traffic),
        "traffic_delta": "0",
        "traffic_delta_pct": "0.0",
        "official_cycles": str(cycles),
        "official_improvement_pct": "0.0",
        "safe_cycles": str(cycles),
        "strict_valid": "True",
    }


def test_fixed_traffic_point_removes_strictly_dominated_tradeoff() -> None:
    fixed = _row("FlashAttention_Case0", "zero_traffic", 54_016, 187_945)
    old_tradeoff = _row("FlashAttention_Case0", "refined_tradeoff", 55_036, 191_230)

    kept, dominated = _pareto([fixed, old_tradeoff])

    assert kept == [fixed]
    assert dominated == [old_tradeoff]


def test_more_traffic_lower_cycles_tradeoff_remains_on_frontier() -> None:
    fixed = _row("FlashAttention_Case1", "zero_traffic", 242_552, 962_022)
    tradeoff_1 = _row("FlashAttention_Case1", "refined_tradeoff", 244_048, 947_002)
    tradeoff_2 = _row("FlashAttention_Case1", "refined_tradeoff", 245_060, 912_556)

    kept, dominated = _pareto([fixed, tradeoff_1, tradeoff_2])

    assert kept == [fixed, tradeoff_1, tradeoff_2]
    assert dominated == []


def test_invalid_candidate_is_never_kept() -> None:
    valid = _row("Conv_Case0", "zero_traffic", 177_904, 597_969)
    invalid = _row("Conv_Case0", "refined_tradeoff", 170_000, 590_000)
    invalid["strict_valid"] = "False"

    kept, dominated = _pareto([valid, invalid])

    assert kept == [valid]
    assert dominated == []
