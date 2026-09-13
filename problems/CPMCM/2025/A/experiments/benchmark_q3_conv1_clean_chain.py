from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from benchmark_q3_spill_switch_batch_snapshot import _serialize_solution
from parser import load_case
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_conv_iterative_spill_batch import optimize_q3_critical_spill_batch_iterative
from q3_evaluator import evaluate_q3_solution
from q3_official_optimizer import optimize_q3_official_zero_traffic


CASE = "Conv_Case1"
EXPECTED_DEEP_OFFICIAL = 3_781_664
EXPECTED_DEEP_SAFE = 4_113_775
EXPECTED_SPILL_COUNT = 9_646
EXPECTED_EXTRA_TRAFFIC = 721_464


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
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--solution-out", type=Path, required=True)
    ap.add_argument("--iterative-max-rounds", type=int, default=12)
    args = ap.parse_args()

    graph = load_case(args.data_dir, CASE)

    t0 = time.perf_counter()
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()
    promoted_solution = promoted.solution
    promoted_q2 = validate_q2_solution(graph, promoted_solution)
    promoted_q2.require_ok()
    if promoted_q2.spill_count != EXPECTED_SPILL_COUNT:
        raise AssertionError("promoted-Q2 spill count drifted")
    if promoted_q2.extra_traffic != EXPECTED_EXTRA_TRAFFIC:
        raise AssertionError("promoted-Q2 extra traffic drifted")
    promoted_spills = tuple((s.buf_id, s.new_offset) for s in promoted_solution.spills)
    t1 = time.perf_counter()

    deep = optimize_q3_official_zero_traffic(
        graph,
        promoted_solution,
        max_rounds=2,
        recolor_max_rounds=24,
        recolor_max_targets=12,
        recolor_max_starts=24,
    )
    deep_q2 = validate_q2_solution(graph, deep.solution)
    deep_q2.require_ok()
    deep_spills = tuple((s.buf_id, s.new_offset) for s in deep.solution.spills)
    if deep.official_timing.total_cycles != EXPECTED_DEEP_OFFICIAL:
        raise AssertionError(
            f"deep official baseline drifted: {deep.official_timing.total_cycles} != {EXPECTED_DEEP_OFFICIAL}"
        )
    if deep.safe_timing.total_cycles != EXPECTED_DEEP_SAFE:
        raise AssertionError(
            f"deep safe baseline drifted: {deep.safe_timing.total_cycles} != {EXPECTED_DEEP_SAFE}"
        )
    if deep_spills != promoted_spills:
        raise AssertionError("deep recolor changed promoted-Q2 spill records")
    if deep_q2.spill_count != promoted_q2.spill_count or deep_q2.extra_traffic != promoted_q2.extra_traffic:
        raise AssertionError("deep recolor changed promoted-Q2 traffic/spill count")
    if deep.solution.schedule != promoted_solution.schedule:
        raise AssertionError("deep recolor unexpectedly changed promoted-Q2 schedule")
    t2 = time.perf_counter()

    iterative = optimize_q3_critical_spill_batch_iterative(
        graph,
        deep.solution,
        max_rounds=args.iterative_max_rounds,
        max_switches=64,
        prefix_sizes=(1, 2, 4, 8, 16, 24, 32, 48, 64),
        baseline_official=deep.official_timing,
        baseline_safe=deep.safe_timing,
    )
    t3 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, iterative.final_solution)
    final_q2.require_ok()
    final_spills = tuple((s.buf_id, s.new_offset) for s in iterative.final_solution.spills)
    if final_spills != promoted_spills:
        raise AssertionError("iterative clean chain changed promoted-Q2 spill records")
    if final_q2.spill_count != promoted_q2.spill_count:
        raise AssertionError("iterative clean chain changed spill count")
    if final_q2.extra_traffic != promoted_q2.extra_traffic:
        raise AssertionError("iterative clean chain changed extra traffic")

    final_official = evaluate_q3_solution(
        graph,
        iterative.final_solution,
        reuse_mode="official_literal",
    )
    final_official.require_ok()
    final_safe = evaluate_q3_solution(
        graph,
        iterative.final_solution,
        reuse_mode="residency_safe",
    )
    final_safe.require_ok()
    if final_official.total_cycles != iterative.final_official.total_cycles:
        raise AssertionError("clean-chain final official replay mismatch")
    if final_safe.total_cycles != iterative.final_safe.total_cycles:
        raise AssertionError("clean-chain final safe replay mismatch")

    snapshot = _serialize_solution(
        CASE,
        iterative.final_solution,
        final_official,
        final_safe,
        final_q2,
        {
            "route": "promoted_q2->official_zero_traffic_deep_recolor->iterative_spill_batch",
            "deep_recolor": {
                "max_rounds": 2,
                "recolor_max_rounds": 24,
                "recolor_max_targets": 12,
                "recolor_max_starts": 24,
                "official_cycles": deep.official_timing.total_cycles,
                "safe_cycles": deep.safe_timing.total_cycles,
            },
            "iterative": {
                "max_rounds": args.iterative_max_rounds,
                "max_switches": 64,
                "prefix_sizes": [1, 2, 4, 8, 16, 24, 32, 48, 64],
                "accepted_rounds": iterative.accepted_rounds,
                "saturated": iterative.saturated,
                "round_best_prefixes": [result.best_prefix_size for result in iterative.rounds],
            },
        },
    )
    args.solution_out.parent.mkdir(parents=True, exist_ok=True)
    args.solution_out.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    payload = {
        "case": CASE,
        "route": "promoted_q2->official_zero_traffic_deep_recolor->iterative_spill_batch",
        "promoted_q2_spill_count": promoted_q2.spill_count,
        "promoted_q2_extra_traffic": promoted_q2.extra_traffic,
        "deep_official_cycles": deep.official_timing.total_cycles,
        "deep_safe_cycles": deep.safe_timing.total_cycles,
        "deep_step_count": len(deep.steps),
        "iterative_max_rounds": args.iterative_max_rounds,
        "iterative_accepted_rounds": iterative.accepted_rounds,
        "iterative_round_count": len(iterative.rounds),
        "iterative_saturated": iterative.saturated,
        "final_official_cycles": final_official.total_cycles,
        "final_safe_cycles": final_safe.total_cycles,
        "improvement_vs_deep_cycles": deep.official_timing.total_cycles - final_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(final_safe.physical_overlap_errors),
        "valid": final_official.ok and final_safe.ok,
        "promoted_q2_seconds": round(t1 - t0, 6),
        "deep_recolor_seconds": round(t2 - t1, 6),
        "iterative_seconds": round(t3 - t2, 6),
        "total_seconds": round(t3 - t0, 6),
        "deep_steps": [
            {
                "round_index": step.round_index,
                "transformation": step.transformation,
                "detail": step.detail,
                "official_before": step.official_before,
                "official_after": step.official_after,
                "safe_before": step.safe_before,
                "safe_after": step.safe_after,
                "accepted": step.accepted,
                "error": step.error,
            }
            for step in deep.steps
        ],
        "rounds": [_round_payload(i, result) for i, result in enumerate(iterative.rounds, 1)],
        "solution_snapshot_written": str(args.solution_out),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
