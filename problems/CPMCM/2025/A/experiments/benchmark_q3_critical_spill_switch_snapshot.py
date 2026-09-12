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
from q3_critical_spill_switch import search_q3_critical_spill_switch_bubbles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-switches", type=int, default=8)
    args = ap.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    graph = load_case(args.data_dir, snapshot["case"])
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()

    t0 = time.perf_counter()
    solution, baseline_official, baseline_safe = _replay_snapshot(
        graph,
        promoted.solution,
        snapshot,
    )
    t1 = time.perf_counter()
    result = search_q3_critical_spill_switch_bubbles(
        graph,
        solution,
        max_switches=args.max_switches,
        baseline_official=baseline_official,
        baseline_safe=baseline_safe,
    )
    t2 = time.perf_counter()

    q2 = validate_q2_solution(graph, result.best_solution)
    q2.require_ok()
    if q2.spill_count != snapshot["spill_count"]:
        raise AssertionError("critical spill switch changed spill count")
    if q2.extra_traffic != snapshot["extra_traffic"]:
        raise AssertionError("critical spill switch changed extra traffic")
    if not result.best_official.ok or not result.best_safe.ok:
        raise AssertionError("critical spill switch final timing invalid")

    payload = {
        "case": snapshot["case"],
        "baseline_official_cycles": baseline_official.total_cycles,
        "best_official_cycles": result.best_official.total_cycles,
        "improvement_cycles": baseline_official.total_cycles - result.best_official.total_cycles,
        "baseline_safe_cycles": baseline_safe.total_cycles,
        "best_safe_cycles": result.best_safe.total_cycles,
        "improved": result.improved,
        "best_move": None if result.best_move is None else list(result.best_move),
        "spill_count": q2.spill_count,
        "extra_traffic": q2.extra_traffic,
        "safe_overlap_errors": len(result.best_safe.physical_overlap_errors),
        "valid": result.best_official.ok and result.best_safe.ok,
        "snapshot_replay_seconds": round(t1 - t0, 6),
        "operator_seconds": round(t2 - t1, 6),
        "total_seconds": round(t2 - t0, 6),
        "candidates": [asdict(candidate) for candidate in result.candidates],
        "trials": [asdict(trial) for trial in result.trials],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
