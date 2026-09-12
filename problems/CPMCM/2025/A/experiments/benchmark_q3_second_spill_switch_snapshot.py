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
from q3_critical_spill_switch_recipe import replay_q3_critical_spill_switch_move


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--recipe", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-switches", type=int, default=8)
    args = ap.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
    if snapshot["case"] != recipe["case"]:
        raise AssertionError("snapshot and switch recipe case mismatch")

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

    baseline_q2 = validate_q2_solution(graph, solution)
    baseline_q2.require_ok()
    expected = recipe["baseline"]
    if baseline_official.total_cycles != expected["official_cycles"]:
        raise AssertionError("second-switch baseline official cycles drifted")
    if baseline_safe.total_cycles != expected["safe_cycles"]:
        raise AssertionError("second-switch baseline safe cycles drifted")
    if baseline_q2.spill_count != expected["spill_count"]:
        raise AssertionError("second-switch baseline spill count drifted")
    if baseline_q2.extra_traffic != expected["extra_traffic"]:
        raise AssertionError("second-switch baseline extra traffic drifted")

    move = recipe["move"]
    switched = replay_q3_critical_spill_switch_move(
        graph,
        solution,
        spill_index=move["spill_index"],
        mode=move["mode"],
        expected_reversed_edges=tuple(tuple(edge) for edge in move["reversed_edges"]),
    )
    t2 = time.perf_counter()

    expected_after = recipe["expected_after_switch"]
    if switched.official.total_cycles != expected_after["official_cycles"]:
        raise AssertionError("first switch official result drifted")
    if switched.safe.total_cycles != expected_after["safe_cycles"]:
        raise AssertionError("first switch safe result drifted")

    second = search_q3_critical_spill_switch_bubbles(
        graph,
        switched.solution,
        max_switches=args.max_switches,
        baseline_official=switched.official,
        baseline_safe=switched.safe,
    )
    t3 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, second.best_solution)
    final_q2.require_ok()
    baseline_spills = tuple((s.buf_id, s.new_offset) for s in solution.spills)
    final_spills = tuple((s.buf_id, s.new_offset) for s in second.best_solution.spills)
    if final_q2.spill_count != baseline_q2.spill_count:
        raise AssertionError("second critical switch changed spill count")
    if final_q2.extra_traffic != baseline_q2.extra_traffic:
        raise AssertionError("second critical switch changed extra traffic")
    if final_spills != baseline_spills:
        raise AssertionError("second critical switch changed spill records")
    if not second.best_official.ok or not second.best_safe.ok:
        raise AssertionError("second critical switch final timing invalid")
    if second.best_official.total_cycles > switched.official.total_cycles:
        raise AssertionError("second critical switch regressed the first strict switch")

    payload = {
        "case": snapshot["case"],
        "baseline_official_cycles": baseline_official.total_cycles,
        "baseline_safe_cycles": baseline_safe.total_cycles,
        "first_switch": {
            "spill_index": move["spill_index"],
            "mode": move["mode"],
            "official_cycles": switched.official.total_cycles,
            "safe_cycles": switched.safe.total_cycles,
            "improvement_cycles": baseline_official.total_cycles - switched.official.total_cycles,
            "reversed_edges": [list(edge) for edge in switched.reversed_edges],
        },
        "second_switch_improved": second.improved,
        "second_switch_best_move": (
            None if second.best_move is None else [second.best_move[0], second.best_move[1]]
        ),
        "final_official_cycles": second.best_official.total_cycles,
        "final_safe_cycles": second.best_safe.total_cycles,
        "second_switch_improvement_cycles": (
            switched.official.total_cycles - second.best_official.total_cycles
        ),
        "total_improvement_cycles": (
            baseline_official.total_cycles - second.best_official.total_cycles
        ),
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(second.best_safe.physical_overlap_errors),
        "valid": second.best_official.ok and second.best_safe.ok,
        "snapshot_replay_seconds": round(t1 - t0, 6),
        "first_switch_replay_seconds": round(t2 - t1, 6),
        "second_switch_search_seconds": round(t3 - t2, 6),
        "total_seconds": round(t3 - t0, 6),
        "candidates": [asdict(candidate) for candidate in second.candidates],
        "trials": [asdict(trial) for trial in second.trials],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
