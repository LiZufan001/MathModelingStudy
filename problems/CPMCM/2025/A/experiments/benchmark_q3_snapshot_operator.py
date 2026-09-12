from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from benchmark_q3_priority_snapshot import _replay_snapshot
from parser import load_case
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_critical_pipe_swap import search_q3_critical_pipe_swaps
from q3_priority_rescheduler import search_q3_priority_reschedule_portfolio
from q3_spill_gap_shift import search_q3_critical_spill_gap_shifts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--operator", choices=("priority", "critical_pipe", "spill_gap"), required=True)
    ap.add_argument("--pipe-candidates", type=int, default=24)
    ap.add_argument("--spill-candidates", type=int, default=8)
    args = ap.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    graph = load_case(args.data_dir, snapshot["case"])
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()

    t0 = time.perf_counter()
    solution, official, safe = _replay_snapshot(graph, promoted.solution, snapshot)
    t1 = time.perf_counter()

    if args.operator == "priority":
        result = search_q3_priority_reschedule_portfolio(
            graph,
            solution,
            baseline_official=official,
            baseline_safe=safe,
        )
        best_solution = result.best_solution
        best_official = result.best_official
        best_safe = result.best_safe
        detail = {
            "best_policy": result.best_policy,
            "trials": [asdict(trial) for trial in result.trials],
        }
    elif args.operator == "critical_pipe":
        result = search_q3_critical_pipe_swaps(
            graph,
            solution,
            max_candidates=args.pipe_candidates,
            baseline_official=official,
            baseline_safe=safe,
        )
        best_solution = result.best_solution
        best_official = result.best_official
        best_safe = result.best_safe
        detail = {
            "candidate_edge_count": len(result.candidate_edges),
            "best_edge": None if result.best_edge is None else list(result.best_edge),
            "trials": [asdict(trial) for trial in result.trials],
        }
    else:
        result = search_q3_critical_spill_gap_shifts(
            graph,
            solution,
            max_spills=args.spill_candidates,
            gap_radius=1,
            baseline_official=official,
            baseline_safe=safe,
        )
        best_solution = result.best_solution
        best_official = result.best_official
        best_safe = result.best_safe
        detail = {
            "critical_spill_count": len(result.critical_spill_indices),
            "critical_spill_indices": list(result.critical_spill_indices),
            "best_shift": None if result.best_shift is None else list(result.best_shift),
            "trials": [asdict(trial) for trial in result.trials],
        }
    t2 = time.perf_counter()

    q2 = validate_q2_solution(graph, best_solution)
    q2.require_ok()
    if q2.extra_traffic != snapshot["extra_traffic"] or q2.spill_count != snapshot["spill_count"]:
        raise AssertionError("snapshot operator changed Q2 traffic/spill count")
    if not best_official.ok or not best_safe.ok:
        raise AssertionError("snapshot operator final timing invalid")

    payload = {
        "case": snapshot["case"],
        "operator": args.operator,
        "baseline_official_cycles": official.total_cycles,
        "best_official_cycles": best_official.total_cycles,
        "improvement_cycles": official.total_cycles - best_official.total_cycles,
        "baseline_safe_cycles": safe.total_cycles,
        "best_safe_cycles": best_safe.total_cycles,
        "improved": best_official.total_cycles < official.total_cycles,
        "spill_count": q2.spill_count,
        "extra_traffic": q2.extra_traffic,
        "safe_overlap_errors": len(best_safe.physical_overlap_errors),
        "valid": best_official.ok and best_safe.ok,
        "snapshot_replay_seconds": round(t1 - t0, 6),
        "operator_seconds": round(t2 - t1, 6),
        "total_seconds": round(t2 - t0, 6),
        "detail": detail,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "detail"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
