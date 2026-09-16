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

from parser import load_case
from q2_model import Q2Solution
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_conv_iterative_spill_batch import optimize_q3_critical_spill_batch_iterative
from q3_evaluator import evaluate_q3_solution
from q3_official_optimizer import optimize_q3_official_zero_traffic


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-rounds", type=int, default=12)
    args = ap.parse_args()

    snap = json.loads(args.snapshot.read_text(encoding="utf-8"))
    graph = load_case(args.data_dir, snap["case"])

    t0 = time.perf_counter()
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()
    promoted_q2 = validate_q2_solution(graph, promoted.solution)
    promoted_q2.require_ok()

    core = optimize_q3_official_zero_traffic(graph, promoted.solution, max_rounds=2)
    if core.official_timing.total_cycles != int(snap["core_official_cycles"]):
        raise AssertionError("formal core official timing drifted")
    if core.safe_timing.total_cycles != int(snap["core_safe_cycles"]):
        raise AssertionError("formal core safe timing drifted")

    offsets = dict(core.solution.initial_offsets)
    for key, value in snap["offset_overrides"].items():
        offsets[int(key)] = int(value)
    saturated = Q2Solution(core.solution.schedule, offsets, core.solution.spills)
    saturated_q2 = validate_q2_solution(graph, saturated)
    saturated_q2.require_ok()
    saturated_official = evaluate_q3_solution(graph, saturated, reuse_mode="official_literal")
    saturated_official.require_ok()
    saturated_safe = evaluate_q3_solution(graph, saturated, reuse_mode="residency_safe")
    saturated_safe.require_ok()
    if saturated_official.total_cycles != int(snap["saturated_official_cycles"]):
        raise AssertionError("offset snapshot official timing drifted")
    if saturated_safe.total_cycles != int(snap["saturated_safe_cycles"]):
        raise AssertionError("offset snapshot safe timing drifted")
    if saturated_q2.spill_count != int(snap["spill_count"]):
        raise AssertionError("offset snapshot spill count drifted")
    if saturated_q2.extra_traffic != int(snap["extra_traffic"]):
        raise AssertionError("offset snapshot extra traffic drifted")
    if saturated.spills != core.solution.spills:
        raise AssertionError("offset snapshot changed spill records")
    if saturated.schedule != core.solution.schedule:
        raise AssertionError("offset snapshot changed schedule")
    t1 = time.perf_counter()

    iterative = optimize_q3_critical_spill_batch_iterative(
        graph,
        saturated,
        max_rounds=args.max_rounds,
        max_switches=64,
        prefix_sizes=(1, 2, 4, 8, 16, 24, 32, 48, 64),
        baseline_official=saturated_official,
        baseline_safe=saturated_safe,
    )
    t2 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, iterative.final_solution)
    final_q2.require_ok()
    if iterative.final_solution.spills != saturated.spills:
        raise AssertionError("iterative search changed spill records")
    if final_q2.spill_count != saturated_q2.spill_count:
        raise AssertionError("iterative search changed spill count")
    if final_q2.extra_traffic != saturated_q2.extra_traffic:
        raise AssertionError("iterative search changed extra traffic")

    payload = {
        "case": snap["case"],
        "core_official_cycles": core.official_timing.total_cycles,
        "core_safe_cycles": core.safe_timing.total_cycles,
        "saturated_official_cycles": saturated_official.total_cycles,
        "saturated_safe_cycles": saturated_safe.total_cycles,
        "offset_override_count": len(snap["offset_overrides"]),
        "iterative_accepted_rounds": iterative.accepted_rounds,
        "iterative_round_count": len(iterative.rounds),
        "iterative_saturated": iterative.saturated,
        "final_official_cycles": iterative.final_official.total_cycles,
        "final_safe_cycles": iterative.final_safe.total_cycles,
        "improvement_vs_saturated_cycles": saturated_official.total_cycles - iterative.final_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(iterative.final_safe.physical_overlap_errors),
        "valid": iterative.final_official.ok and iterative.final_safe.ok,
        "setup_seconds": round(t1 - t0, 6),
        "iterative_seconds": round(t2 - t1, 6),
        "total_seconds": round(t2 - t0, 6),
        "rounds": [
            {
                "round": i,
                "improved": result.improved,
                "baseline_official_cycles": result.baseline_official.total_cycles,
                "best_prefix_size": result.best_prefix_size,
                "best_official_cycles": result.best_official.total_cycles,
                "best_safe_cycles": result.best_safe.total_cycles,
                "improvement_cycles": result.baseline_official.total_cycles - result.best_official.total_cycles,
                "trials": [_trial_payload(trial) for trial in result.trials],
            }
            for i, result in enumerate(iterative.rounds, 1)
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
