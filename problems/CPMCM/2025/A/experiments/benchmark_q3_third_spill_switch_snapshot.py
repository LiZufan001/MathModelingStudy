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


def _serialize_solution(case: str, solution, official, safe, q2, recipe: dict) -> dict:
    return {
        "format": "q2-solution-v1",
        "case": case,
        "schedule": list(solution.schedule),
        "initial_offsets": {str(k): v for k, v in sorted(solution.initial_offsets.items())},
        "spills": [
            {"buf_id": spill.buf_id, "new_offset": spill.new_offset}
            for spill in solution.spills
        ],
        "official_cycles": official.total_cycles,
        "safe_cycles": safe.total_cycles,
        "spill_count": q2.spill_count,
        "extra_traffic": q2.extra_traffic,
        "safe_overlap_errors": len(safe.physical_overlap_errors),
        "recipe": recipe,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--recipe", type=Path, required=True)
    ap.add_argument("--solution-out", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-switches", type=int, default=8)
    args = ap.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
    if snapshot["case"] != recipe["case"]:
        raise AssertionError("snapshot and two-switch recipe case mismatch")

    graph = load_case(args.data_dir, snapshot["case"])
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()

    t0 = time.perf_counter()
    saturated_solution, baseline_official, baseline_safe = _replay_snapshot(
        graph,
        promoted.solution,
        snapshot,
    )
    current = saturated_solution
    t1 = time.perf_counter()

    baseline_q2 = validate_q2_solution(graph, saturated_solution)
    baseline_q2.require_ok()
    expected = recipe["baseline"]
    if baseline_official.total_cycles != expected["official_cycles"]:
        raise AssertionError("two-switch baseline official cycles drifted")
    if baseline_safe.total_cycles != expected["safe_cycles"]:
        raise AssertionError("two-switch baseline safe cycles drifted")
    if baseline_q2.spill_count != expected["spill_count"]:
        raise AssertionError("two-switch baseline spill count drifted")
    if baseline_q2.extra_traffic != expected["extra_traffic"]:
        raise AssertionError("two-switch baseline extra traffic drifted")

    current_official = baseline_official
    current_safe = baseline_safe
    replayed_moves = []
    for index, move in enumerate(recipe["moves"], start=1):
        replay = replay_q3_critical_spill_switch_move(
            graph,
            current,
            spill_index=move["spill_index"],
            mode=move["mode"],
            expected_reversed_edges=tuple(tuple(edge) for edge in move["reversed_edges"]),
        )
        expected_after = move["expected_after"]
        if replay.official.total_cycles != expected_after["official_cycles"]:
            raise AssertionError(f"switch {index} official result drifted")
        if replay.safe.total_cycles != expected_after["safe_cycles"]:
            raise AssertionError(f"switch {index} safe result drifted")
        if replay.changed_positions != expected_after["changed_positions"]:
            raise AssertionError(f"switch {index} changed-position count drifted")
        replayed_moves.append(
            {
                "index": index,
                "spill_index": move["spill_index"],
                "mode": move["mode"],
                "reversed_edges": [list(edge) for edge in replay.reversed_edges],
                "changed_positions": replay.changed_positions,
                "official_cycles": replay.official.total_cycles,
                "safe_cycles": replay.safe.total_cycles,
            }
        )
        current = replay.solution
        current_official = replay.official
        current_safe = replay.safe
    t2 = time.perf_counter()

    two_q2 = validate_q2_solution(graph, current)
    two_q2.require_ok()
    saturated_spills = tuple((s.buf_id, s.new_offset) for s in saturated_solution.spills)
    current_spills = tuple((s.buf_id, s.new_offset) for s in current.spills)
    if two_q2.spill_count != baseline_q2.spill_count:
        raise AssertionError("two-switch snapshot changed spill count")
    if two_q2.extra_traffic != baseline_q2.extra_traffic:
        raise AssertionError("two-switch snapshot changed extra traffic")
    if current_spills != saturated_spills:
        raise AssertionError("two-switch snapshot changed spill records")

    solution_payload = _serialize_solution(
        snapshot["case"],
        current,
        current_official,
        current_safe,
        two_q2,
        recipe,
    )
    args.solution_out.parent.mkdir(parents=True, exist_ok=True)
    args.solution_out.write_text(
        json.dumps(solution_payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    third = search_q3_critical_spill_switch_bubbles(
        graph,
        current,
        max_switches=args.max_switches,
        baseline_official=current_official,
        baseline_safe=current_safe,
    )
    t3 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, third.best_solution)
    final_q2.require_ok()
    final_spills = tuple((s.buf_id, s.new_offset) for s in third.best_solution.spills)
    if final_q2.spill_count != baseline_q2.spill_count:
        raise AssertionError("third critical switch changed spill count")
    if final_q2.extra_traffic != baseline_q2.extra_traffic:
        raise AssertionError("third critical switch changed extra traffic")
    if final_spills != current_spills:
        raise AssertionError("third critical switch changed spill records")
    if not third.best_official.ok or not third.best_safe.ok:
        raise AssertionError("third critical switch final timing invalid")
    if third.best_official.total_cycles > current_official.total_cycles:
        raise AssertionError("third critical switch regressed two-switch result")

    payload = {
        "case": snapshot["case"],
        "baseline_official_cycles": baseline_official.total_cycles,
        "baseline_safe_cycles": baseline_safe.total_cycles,
        "replayed_moves": replayed_moves,
        "two_switch_official_cycles": current_official.total_cycles,
        "two_switch_safe_cycles": current_safe.total_cycles,
        "two_switch_improvement_cycles": baseline_official.total_cycles - current_official.total_cycles,
        "solution_snapshot_written": str(args.solution_out),
        "solution_schedule_length": len(current.schedule),
        "solution_initial_offset_count": len(current.initial_offsets),
        "solution_spill_count": len(current.spills),
        "third_switch_improved": third.improved,
        "third_switch_best_move": (
            None if third.best_move is None else [third.best_move[0], third.best_move[1]]
        ),
        "final_official_cycles": third.best_official.total_cycles,
        "final_safe_cycles": third.best_safe.total_cycles,
        "third_switch_improvement_cycles": (
            current_official.total_cycles - third.best_official.total_cycles
        ),
        "total_improvement_cycles": (
            baseline_official.total_cycles - third.best_official.total_cycles
        ),
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(third.best_safe.physical_overlap_errors),
        "valid": third.best_official.ok and third.best_safe.ok,
        "snapshot_replay_seconds": round(t1 - t0, 6),
        "two_exact_switch_replay_seconds": round(t2 - t1, 6),
        "third_switch_search_seconds": round(t3 - t2, 6),
        "total_seconds": round(t3 - t0, 6),
        "candidates": [asdict(candidate) for candidate in third.candidates],
        "trials": [asdict(trial) for trial in third.trials],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
