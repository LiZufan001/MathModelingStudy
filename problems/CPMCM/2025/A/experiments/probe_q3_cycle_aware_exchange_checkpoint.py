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

from model import ComputeGraph
from parser import load_case
from probe_q3_single_switch_checkpoint import _read_solution, _write_solution
from q2_validator import validate_q2_solution
from q3_cycle_aware_spill_exchange import search_q3_cycle_aware_spill_exchanges
from q3_evaluator import evaluate_q3_solution


def main() -> int:
    ap = argparse.ArgumentParser(description="One bounded cycle-aware Q3 SPILL exchange checkpoint")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--max-targets", type=int, default=4)
    ap.add_argument("--max-blockers-per-target", type=int, default=8)
    ap.add_argument("--expected-official", type=int)
    args = ap.parse_args()
    if args.max_targets <= 0 or args.max_blockers_per_target <= 0:
        raise ValueError("max-targets and max-blockers-per-target must be positive")

    graph: ComputeGraph = load_case(args.data_dir, args.case)
    solution = _read_solution(args.input_dir, args.case)
    q2 = validate_q2_solution(graph, solution)
    q2.require_ok()
    baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()
    if args.expected_official is not None and baseline_official.total_cycles != args.expected_official:
        raise AssertionError(
            f"input official timing drifted: {baseline_official.total_cycles} != {args.expected_official}"
        )

    t0 = time.perf_counter()
    result = search_q3_cycle_aware_spill_exchanges(
        graph,
        solution,
        max_targets=args.max_targets,
        max_blockers_per_target=args.max_blockers_per_target,
        baseline_official=baseline_official,
        baseline_safe=baseline_safe,
    )

    final_q2 = validate_q2_solution(graph, result.best_solution)
    final_q2.require_ok()
    if result.best_solution.spills != solution.spills:
        raise AssertionError("cycle-aware exchange changed exact SPILL records")
    if final_q2.spill_count != q2.spill_count or final_q2.extra_traffic != q2.extra_traffic:
        raise AssertionError("cycle-aware exchange changed Q2 metrics")
    result.best_official.require_ok()
    result.best_safe.require_ok()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_solution(args.out_dir / "next", args.case, result.best_solution)

    best_exchange = None
    if result.best_exchange is not None:
        spill_index, target_edge, blocker_edge = result.best_exchange
        best_exchange = {
            "spill_index": spill_index,
            "target_edge": list(target_edge),
            "blocker_edge": list(blocker_edge),
        }

    payload = {
        "case": args.case,
        "operator": "bounded_cycle_aware_spill_two_edge_exchange",
        "max_targets": args.max_targets,
        "max_blockers_per_target": args.max_blockers_per_target,
        "baseline": {
            "official_cycles": baseline_official.total_cycles,
            "safe_cycles": baseline_safe.total_cycles,
            "spill_count": q2.spill_count,
            "extra_traffic": q2.extra_traffic,
        },
        "result": {
            "improved": result.improved,
            "best_exchange": best_exchange,
            "official_cycles": result.best_official.total_cycles,
            "safe_cycles": result.best_safe.total_cycles,
            "improvement_cycles": baseline_official.total_cycles - result.best_official.total_cycles,
            "spill_count": final_q2.spill_count,
            "extra_traffic": final_q2.extra_traffic,
            "safe_overlap_errors": len(result.best_safe.physical_overlap_errors),
            "valid": result.best_official.ok and result.best_safe.ok,
        },
        "trial_count": len(result.trials),
        "trials": [asdict(trial) for trial in result.trials],
        "seconds": round(time.perf_counter() - t0, 6),
        "checkpoint": "next",
    }
    (args.out_dir / "cycle-aware-exchange.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
