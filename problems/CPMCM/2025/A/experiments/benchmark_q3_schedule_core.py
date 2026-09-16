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

from parser import load_case
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_critical_pipe_swap import search_q3_critical_pipe_swaps
from q3_official_optimizer import optimize_q3_official_zero_traffic
from q3_priority_rescheduler import search_q3_priority_reschedule_portfolio


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--case", default="Conv_Case1")
    ap.add_argument("--pipe-candidates", type=int, default=24)
    args = ap.parse_args()

    graph = load_case(args.data_dir, args.case)
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()

    t0 = time.perf_counter()
    core = optimize_q3_official_zero_traffic(
        graph,
        promoted.allocation.solution,
        max_rounds=2,
        recolor_max_rounds=0,
    )
    t1 = time.perf_counter()
    priority = search_q3_priority_reschedule_portfolio(
        graph,
        core.solution,
        baseline_official=core.official_timing,
        baseline_safe=core.safe_timing,
    )
    t2 = time.perf_counter()
    pipe = search_q3_critical_pipe_swaps(
        graph,
        core.solution,
        max_candidates=args.pipe_candidates,
        baseline_official=core.official_timing,
        baseline_safe=core.safe_timing,
    )
    t3 = time.perf_counter()

    choices = [
        ("baseline", core.solution, core.official_timing, core.safe_timing),
        ("priority", priority.best_solution, priority.best_official, priority.best_safe),
        ("critical_pipe", pipe.best_solution, pipe.best_official, pipe.best_safe),
    ]
    source, solution, official, safe = min(
        choices,
        key=lambda x: (x[2].total_cycles, x[3].total_cycles, x[0]),
    )
    q2 = validate_q2_solution(graph, solution)
    q2.require_ok()
    payload = {
        "case": args.case,
        "core_official_cycles": core.official_timing.total_cycles,
        "core_safe_cycles": core.safe_timing.total_cycles,
        "best_source": source,
        "best_official_cycles": official.total_cycles,
        "best_safe_cycles": safe.total_cycles,
        "improvement_cycles": core.official_timing.total_cycles - official.total_cycles,
        "improved": official.total_cycles < core.official_timing.total_cycles,
        "spill_count": q2.spill_count,
        "extra_traffic": q2.extra_traffic,
        "safe_overlap_errors": len(safe.physical_overlap_errors),
        "valid": official.ok and safe.ok,
        "priority": {
            "best_policy": priority.best_policy,
            "official_cycles": priority.best_official.total_cycles,
            "safe_cycles": priority.best_safe.total_cycles,
            "trials": [asdict(t) for t in priority.trials],
        },
        "critical_pipe": {
            "candidate_count": len(pipe.candidate_edges),
            "best_edge": None if pipe.best_edge is None else list(pipe.best_edge),
            "official_cycles": pipe.best_official.total_cycles,
            "safe_cycles": pipe.best_safe.total_cycles,
            "trials": [asdict(t) for t in pipe.trials],
        },
        "core_seconds": round(t1 - t0, 6),
        "priority_seconds": round(t2 - t1, 6),
        "critical_pipe_seconds": round(t3 - t2, 6),
        "total_seconds": round(t3 - t0, 6),
    }
    if args.case == "Conv_Case1" and core.official_timing.total_cycles != 3784892:
        raise AssertionError("Conv1 core official regression")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
