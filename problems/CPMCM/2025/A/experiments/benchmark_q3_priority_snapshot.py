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
from q3_evaluator import evaluate_q3_solution
from q3_official_optimizer import optimize_q3_official_zero_traffic
from q3_priority_rescheduler import search_q3_priority_reschedule_portfolio


def _replay_snapshot(graph, promoted_solution: Q2Solution, snapshot: dict):
    core = optimize_q3_official_zero_traffic(
        graph,
        promoted_solution,
        max_rounds=2,
        recolor_max_rounds=0,
    )
    if core.official_timing.total_cycles != snapshot["core_official_cycles"]:
        raise AssertionError("snapshot core official cycles drifted")
    if core.safe_timing.total_cycles != snapshot["core_safe_cycles"]:
        raise AssertionError("snapshot core safe cycles drifted")

    offsets = dict(core.solution.initial_offsets)
    for raw_buf, new_offset in snapshot["offset_overrides"].items():
        buf_id = int(raw_buf)
        if buf_id not in offsets:
            raise AssertionError(f"snapshot override buffer {buf_id} missing from core solution")
        offsets[buf_id] = int(new_offset)
    solution = Q2Solution(core.solution.schedule, offsets, core.solution.spills)
    q2 = validate_q2_solution(graph, solution)
    q2.require_ok()
    official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    official.require_ok()
    safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    safe.require_ok()
    if official.total_cycles != snapshot["saturated_official_cycles"]:
        raise AssertionError("snapshot replay official cycles drifted")
    if safe.total_cycles != snapshot["saturated_safe_cycles"]:
        raise AssertionError("snapshot replay safe cycles drifted")
    return solution, official, safe


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    case = snapshot["case"]
    graph = load_case(args.data_dir, case)
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()

    t0 = time.perf_counter()
    saturated_solution, saturated_official, saturated_safe = _replay_snapshot(
        graph, promoted.allocation.solution, snapshot
    )
    t1 = time.perf_counter()
    result = search_q3_priority_reschedule_portfolio(
        graph,
        saturated_solution,
        baseline_official=saturated_official,
        baseline_safe=saturated_safe,
    )
    t2 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, result.best_solution)
    final_q2.require_ok()
    payload = {
        "case": case,
        "saturated_official_cycles": saturated_official.total_cycles,
        "priority_official_cycles": result.best_official.total_cycles,
        "priority_improvement_cycles": saturated_official.total_cycles - result.best_official.total_cycles,
        "saturated_safe_cycles": saturated_safe.total_cycles,
        "priority_safe_cycles": result.best_safe.total_cycles,
        "improved": result.improved,
        "best_policy": result.best_policy,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(result.best_safe.physical_overlap_errors),
        "valid": result.best_official.ok and result.best_safe.ok,
        "snapshot_replay_seconds": round(t1 - t0, 6),
        "priority_search_seconds": round(t2 - t1, 6),
        "total_seconds": round(t2 - t0, 6),
        "trials": [
            {
                "policy": trial.policy,
                "q2_valid": trial.q2_valid,
                "safe_valid": trial.safe_valid,
                "official_cycles": trial.official_cycles,
                "safe_cycles": trial.safe_cycles,
                "changed_positions": trial.changed_positions,
                "error": trial.error,
            }
            for trial in result.trials
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
