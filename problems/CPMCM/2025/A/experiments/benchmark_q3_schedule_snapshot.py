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

from benchmark_q3_priority_snapshot import _replay_snapshot
from parser import load_case
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_critical_pipe_swap import search_q3_critical_pipe_swaps
from q3_priority_rescheduler import search_q3_priority_reschedule_portfolio


def _candidate_payload(name, result, baseline_official: int):
    best_edge = getattr(result, "best_edge", None)
    best_policy = getattr(result, "best_policy", None)
    return {
        "name": name,
        "official_cycles": result.best_official.total_cycles,
        "improvement_cycles": baseline_official - result.best_official.total_cycles,
        "safe_cycles": result.best_safe.total_cycles,
        "improved": result.best_official.total_cycles < baseline_official,
        "best_policy": best_policy,
        "best_edge": None if best_edge is None else list(best_edge),
        "safe_overlap_errors": len(result.best_safe.physical_overlap_errors),
        "trials": [
            {
                key: value
                for key, value in vars(trial).items()
            }
            for trial in result.trials
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pipe-candidates", type=int, default=24)
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

    priority = search_q3_priority_reschedule_portfolio(
        graph,
        saturated_solution,
        baseline_official=saturated_official,
        baseline_safe=saturated_safe,
    )
    t2 = time.perf_counter()
    pipe = search_q3_critical_pipe_swaps(
        graph,
        saturated_solution,
        max_candidates=args.pipe_candidates,
        baseline_official=saturated_official,
        baseline_safe=saturated_safe,
    )
    t3 = time.perf_counter()

    candidates = [
        ("baseline", saturated_solution, saturated_official, saturated_safe),
        ("priority", priority.best_solution, priority.best_official, priority.best_safe),
        ("pipe", pipe.best_solution, pipe.best_official, pipe.best_safe),
    ]
    _, first_solution, first_official, first_safe = min(
        candidates,
        key=lambda item: (item[2].total_cycles, item[3].total_cycles, item[0]),
    )

    composed = None
    if first_official.total_cycles < saturated_official.total_cycles:
        priority2 = search_q3_priority_reschedule_portfolio(
            graph,
            first_solution,
            baseline_official=first_official,
            baseline_safe=first_safe,
        )
        pipe2 = search_q3_critical_pipe_swaps(
            graph,
            first_solution,
            max_candidates=args.pipe_candidates,
            baseline_official=first_official,
            baseline_safe=first_safe,
        )
        composed_candidates = [
            ("first", first_solution, first_official, first_safe),
            ("priority_after_first", priority2.best_solution, priority2.best_official, priority2.best_safe),
            ("pipe_after_first", pipe2.best_solution, pipe2.best_official, pipe2.best_safe),
        ]
        composed = min(
            composed_candidates,
            key=lambda item: (item[2].total_cycles, item[3].total_cycles, item[0]),
        )
    t4 = time.perf_counter()

    final_name, final_solution, final_official, final_safe = (
        composed if composed is not None else min(
            candidates,
            key=lambda item: (item[2].total_cycles, item[3].total_cycles, item[0]),
        )
    )
    final_q2 = validate_q2_solution(graph, final_solution)
    final_q2.require_ok()
    if final_q2.spill_count != snapshot["spill_count"]:
        raise AssertionError("schedule probe changed spill count")
    if final_q2.extra_traffic != snapshot["extra_traffic"]:
        raise AssertionError("schedule probe changed extra traffic")
    if not final_safe.ok or not final_official.ok:
        raise AssertionError("schedule probe final timing invalid")

    payload = {
        "case": case,
        "saturated_official_cycles": saturated_official.total_cycles,
        "saturated_safe_cycles": saturated_safe.total_cycles,
        "priority": _candidate_payload("priority", priority, saturated_official.total_cycles),
        "critical_pipe": _candidate_payload("critical_pipe", pipe, saturated_official.total_cycles),
        "final_source": final_name,
        "final_official_cycles": final_official.total_cycles,
        "final_safe_cycles": final_safe.total_cycles,
        "improvement_cycles": saturated_official.total_cycles - final_official.total_cycles,
        "improved": final_official.total_cycles < saturated_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(final_safe.physical_overlap_errors),
        "valid": final_official.ok and final_safe.ok,
        "snapshot_replay_seconds": round(t1 - t0, 6),
        "priority_seconds": round(t2 - t1, 6),
        "critical_pipe_seconds": round(t3 - t2, 6),
        "composition_seconds": round(t4 - t3, 6),
        "total_seconds": round(t4 - t0, 6),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
