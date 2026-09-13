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

from model import ComputeGraph
from parser import load_case
from probe_q3_single_switch_checkpoint import _read_solution, _write_solution
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution
from q3_official_spill_optimizer import optimize_q3_official_with_spill_batches


def _step_payload(step) -> dict[str, object]:
    return {
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


def _batch_trial_payload(trial) -> dict[str, object]:
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


def _batch_round_payload(index: int, result) -> dict[str, object]:
    return {
        "round": index,
        "improved": result.improved,
        "baseline_official_cycles": result.baseline_official.total_cycles,
        "baseline_safe_cycles": result.baseline_safe.total_cycles,
        "best_prefix_size": result.best_prefix_size,
        "best_official_cycles": result.best_official.total_cycles,
        "best_safe_cycles": result.best_safe.total_cycles,
        "improvement_cycles": result.baseline_official.total_cycles - result.best_official.total_cycles,
        "trials": [_batch_trial_payload(trial) for trial in result.trials],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Bounded formal Q3 coordinate-descent probe from a checkpoint")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--expected-official", type=int)
    ap.add_argument("--core-max-rounds", type=int, default=1)
    ap.add_argument("--recolor-max-rounds", type=int, default=2)
    ap.add_argument("--recolor-max-targets", type=int, default=6)
    ap.add_argument("--recolor-max-starts", type=int, default=12)
    ap.add_argument("--spill-max-rounds", type=int, default=4)
    ap.add_argument("--spill-max-switches", type=int, default=64)
    args = ap.parse_args()
    if args.core_max_rounds <= 0:
        raise ValueError("core-max-rounds must be positive")
    if args.recolor_max_rounds < 0 or args.spill_max_rounds < 0:
        raise ValueError("recolor/spill max rounds must be nonnegative")

    graph: ComputeGraph = load_case(args.data_dir, args.case)
    solution = _read_solution(args.input_dir, args.case)
    baseline_q2 = validate_q2_solution(graph, solution)
    baseline_q2.require_ok()
    baseline_spill_ids = tuple(spill.buf_id for spill in solution.spills)
    baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()
    if args.expected_official is not None and baseline_official.total_cycles != args.expected_official:
        raise AssertionError(
            f"input official timing drifted: {baseline_official.total_cycles} != {args.expected_official}"
        )

    t0 = time.perf_counter()
    result = optimize_q3_official_with_spill_batches(
        graph,
        solution,
        max_rounds=args.core_max_rounds,
        recolor_max_rounds=args.recolor_max_rounds,
        recolor_max_targets=args.recolor_max_targets,
        recolor_max_starts=args.recolor_max_starts,
        spill_batch_max_rounds=args.spill_max_rounds,
        spill_batch_max_switches=args.spill_max_switches,
        spill_batch_prefix_sizes=(1, 2, 4, 8, 16, 24, 32, 48, 64),
    )
    elapsed = time.perf_counter() - t0

    final_q2 = validate_q2_solution(graph, result.solution)
    final_q2.require_ok()
    if tuple(spill.buf_id for spill in result.solution.spills) != baseline_spill_ids:
        raise AssertionError("coordinate probe changed SPILL identity/order")
    if final_q2.spill_count != baseline_q2.spill_count:
        raise AssertionError("coordinate probe changed spill count")
    if final_q2.extra_traffic != baseline_q2.extra_traffic:
        raise AssertionError("coordinate probe changed extra traffic")

    replay_official = evaluate_q3_solution(graph, result.solution, reuse_mode="official_literal")
    replay_official.require_ok()
    replay_safe = evaluate_q3_solution(graph, result.solution, reuse_mode="residency_safe")
    replay_safe.require_ok()
    if replay_official.total_cycles != result.official_timing.total_cycles:
        raise AssertionError("coordinate probe official replay mismatch")
    if replay_safe.total_cycles != result.safe_timing.total_cycles:
        raise AssertionError("coordinate probe safe replay mismatch")
    if result.official_timing.total_cycles > baseline_official.total_cycles:
        raise AssertionError("coordinate probe regressed official cycles")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_solution(args.out_dir / "next", args.case, result.solution)

    spill = result.spill_batches
    payload = {
        "case": args.case,
        "route": "checkpoint->formal_zero_traffic_bounded->fresh_spill_batch_bounded",
        "settings": {
            "core_max_rounds": args.core_max_rounds,
            "recolor_max_rounds": args.recolor_max_rounds,
            "recolor_max_targets": args.recolor_max_targets,
            "recolor_max_starts": args.recolor_max_starts,
            "spill_max_rounds": args.spill_max_rounds,
            "spill_max_switches": args.spill_max_switches,
        },
        "baseline": {
            "official_cycles": baseline_official.total_cycles,
            "safe_cycles": baseline_safe.total_cycles,
            "spill_count": baseline_q2.spill_count,
            "extra_traffic": baseline_q2.extra_traffic,
        },
        "core": {
            "official_cycles": result.core.official_timing.total_cycles,
            "safe_cycles": result.core.safe_timing.total_cycles,
            "improvement_cycles": baseline_official.total_cycles - result.core.official_timing.total_cycles,
            "steps": [_step_payload(step) for step in result.core.steps],
        },
        "spill_batch": {
            "enabled": spill is not None,
            "improved": result.spill_batch_improved,
            "saturated": result.spill_batch_saturated,
            "accepted_rounds": 0 if spill is None else spill.accepted_rounds,
            "round_count": 0 if spill is None else len(spill.rounds),
            "rounds": [] if spill is None else [
                _batch_round_payload(i, round_result) for i, round_result in enumerate(spill.rounds, 1)
            ],
        },
        "final": {
            "official_cycles": result.official_timing.total_cycles,
            "safe_cycles": result.safe_timing.total_cycles,
            "improvement_cycles": baseline_official.total_cycles - result.official_timing.total_cycles,
            "spill_count": final_q2.spill_count,
            "extra_traffic": final_q2.extra_traffic,
            "safe_overlap_errors": len(replay_safe.physical_overlap_errors),
            "valid": replay_official.ok and replay_safe.ok,
        },
        "seconds": round(elapsed, 6),
        "checkpoint": "next",
    }
    (args.out_dir / "coordinate-descent.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
