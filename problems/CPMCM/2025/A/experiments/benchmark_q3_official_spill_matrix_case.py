from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from parser import load_case
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution
from q3_official_spill_optimizer import optimize_q3_official_with_spill_batches


CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)

# Already-promoted formal zero-traffic baselines. The new post-pass may improve
# them, but the first stage must reproduce them exactly before promotion.
EXPECTED_CORE = {
    "Matmul_Case0": (133_682, 160_005),
    "Matmul_Case1": (1_531_946, 1_669_574),
    "FlashAttention_Case0": (188_562, 204_875),
    "FlashAttention_Case1": (962_022, 1_026_634),
    "Conv_Case0": (604_665, 785_887),
    "Conv_Case1": (3_781_664, 4_113_775),
}


def _trial_payload(trial) -> dict:
    return {
        "prefix_size": trial.prefix_size,
        "spill_indices": list(trial.spill_indices),
        "reversed_edges": [list(edge) for edge in trial.reversed_edges],
        "q2_valid": trial.q2_valid,
        "safe_valid": trial.safe_valid,
        "official_cycles": trial.official_cycles,
        "safe_cycles": trial.safe_cycles,
        "changed_positions": trial.changed_positions,
        "error": trial.error,
    }


def _round_payload(index: int, result) -> dict:
    return {
        "round": index,
        "improved": result.improved,
        "baseline_official_cycles": result.baseline_official.total_cycles,
        "baseline_safe_cycles": result.baseline_safe.total_cycles,
        "best_prefix_size": result.best_prefix_size,
        "best_official_cycles": result.best_official.total_cycles,
        "best_safe_cycles": result.best_safe.total_cycles,
        "improvement_cycles": result.baseline_official.total_cycles - result.best_official.total_cycles,
        "trials": [_trial_payload(trial) for trial in result.trials],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--case", choices=CASES, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--spill-max-rounds", type=int, default=12)
    args = ap.parse_args()

    graph = load_case(args.data_dir, args.case)

    t0 = time.perf_counter()
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()
    promoted_q2 = validate_q2_solution(graph, promoted.solution)
    promoted_q2.require_ok()
    promoted_spill_ids = tuple(spill.buf_id for spill in promoted.solution.spills)
    t1 = time.perf_counter()

    result = optimize_q3_official_with_spill_batches(
        graph,
        promoted.solution,
        max_rounds=2,
        recolor_max_rounds=24,
        recolor_max_targets=12,
        recolor_max_starts=24,
        spill_batch_max_rounds=args.spill_max_rounds,
        spill_batch_max_switches=64,
        spill_batch_prefix_sizes=(1, 2, 4, 8, 16, 24, 32, 48, 64),
    )
    t2 = time.perf_counter()

    expected_core_official, expected_core_safe = EXPECTED_CORE[args.case]
    if result.core.official_timing.total_cycles != expected_core_official:
        raise AssertionError(
            f"formal core official drifted for {args.case}: "
            f"{result.core.official_timing.total_cycles} != {expected_core_official}"
        )
    if result.core.safe_timing.total_cycles != expected_core_safe:
        raise AssertionError(
            f"formal core safe drifted for {args.case}: "
            f"{result.core.safe_timing.total_cycles} != {expected_core_safe}"
        )

    core_q2 = validate_q2_solution(graph, result.core.solution)
    core_q2.require_ok()
    core_spills = tuple((spill.buf_id, spill.new_offset) for spill in result.core.solution.spills)
    if tuple(spill.buf_id for spill in result.core.solution.spills) != promoted_spill_ids:
        raise AssertionError("formal core changed promoted-Q2 SPILL identity/order")
    if core_q2.spill_count != promoted_q2.spill_count:
        raise AssertionError("formal core changed promoted-Q2 spill count")
    if core_q2.extra_traffic != promoted_q2.extra_traffic:
        raise AssertionError("formal core changed promoted-Q2 extra traffic")

    final_q2 = validate_q2_solution(graph, result.solution)
    final_q2.require_ok()
    final_spills = tuple((spill.buf_id, spill.new_offset) for spill in result.solution.spills)
    if final_spills != core_spills:
        raise AssertionError("formal spill-batch post-pass changed core SPILL records")
    if tuple(spill.buf_id for spill in result.solution.spills) != promoted_spill_ids:
        raise AssertionError("formal matrix changed promoted-Q2 SPILL identity/order")
    if final_q2.spill_count != promoted_q2.spill_count:
        raise AssertionError("formal matrix changed promoted-Q2 spill count")
    if final_q2.extra_traffic != promoted_q2.extra_traffic:
        raise AssertionError("formal matrix changed promoted-Q2 extra traffic")

    replay_official = evaluate_q3_solution(graph, result.solution, reuse_mode="official_literal")
    replay_official.require_ok()
    replay_safe = evaluate_q3_solution(graph, result.solution, reuse_mode="residency_safe")
    replay_safe.require_ok()
    if replay_official.total_cycles != result.official_timing.total_cycles:
        raise AssertionError("formal matrix official replay mismatch")
    if replay_safe.total_cycles != result.safe_timing.total_cycles:
        raise AssertionError("formal matrix residency-safe replay mismatch")
    if result.official_timing.total_cycles > result.core.official_timing.total_cycles:
        raise AssertionError("formal spill-batch post-pass regressed official cycles")

    spill = result.spill_batches
    rounds = [] if spill is None else [_round_payload(i, round_result) for i, round_result in enumerate(spill.rounds, 1)]
    payload = {
        "case": args.case,
        "route": "promoted_q2->formal_zero_traffic->formal_iterative_spill_batch",
        "promoted_q2": {
            "spill_count": promoted_q2.spill_count,
            "extra_traffic": promoted_q2.extra_traffic,
        },
        "core": {
            "official_cycles": result.core.official_timing.total_cycles,
            "safe_cycles": result.core.safe_timing.total_cycles,
            "expected_official_cycles": expected_core_official,
            "expected_safe_cycles": expected_core_safe,
            "step_count": len(result.core.steps),
            "spill_offsets_recolored": core_spills != tuple(
                (spill.buf_id, spill.new_offset) for spill in promoted.solution.spills
            ),
        },
        "spill_batch": {
            "enabled": spill is not None,
            "improved": result.spill_batch_improved,
            "saturated": result.spill_batch_saturated,
            "accepted_rounds": 0 if spill is None else spill.accepted_rounds,
            "round_count": 0 if spill is None else len(spill.rounds),
            "max_rounds": args.spill_max_rounds,
            "max_switches": 64,
            "prefix_sizes": [1, 2, 4, 8, 16, 24, 32, 48, 64],
            "rounds": rounds,
        },
        "final": {
            "official_cycles": result.official_timing.total_cycles,
            "safe_cycles": result.safe_timing.total_cycles,
            "improvement_cycles": result.core.official_timing.total_cycles - result.official_timing.total_cycles,
            "spill_count": final_q2.spill_count,
            "extra_traffic": final_q2.extra_traffic,
            "safe_overlap_errors": len(replay_safe.physical_overlap_errors),
            "valid": replay_official.ok and replay_safe.ok,
        },
        "seconds": {
            "promoted_q2": round(t1 - t0, 6),
            "formal_q3": round(t2 - t1, 6),
            "total": round(t2 - t0, 6),
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
