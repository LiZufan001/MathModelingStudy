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
from q2_model import Q2Solution, SpillRecord
from q2_validator import validate_q2_solution
from q3_critical_spill_switch import search_q3_critical_spill_switch_bubbles
from q3_critical_spill_switch_recipe import replay_q3_critical_spill_switch_move
from q3_evaluator import evaluate_q3_solution


def _load_solution(path: Path) -> tuple[dict, Q2Solution]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != "q2-solution-v1":
        raise AssertionError("unsupported Q2 solution snapshot format")
    solution = Q2Solution(
        tuple(int(node_id) for node_id in payload["schedule"]),
        {int(buf_id): int(offset) for buf_id, offset in payload["initial_offsets"].items()},
        tuple(
            SpillRecord(int(item["buf_id"]), int(item["new_offset"]))
            for item in payload["spills"]
        ),
    )
    return payload, solution


def _serialize_solution(case: str, solution: Q2Solution, official, safe, q2, provenance: dict) -> dict:
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
        "provenance": provenance,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--solution", type=Path, required=True)
    ap.add_argument("--recipe", type=Path, required=True)
    ap.add_argument("--solution-out", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-switches", type=int, default=8)
    args = ap.parse_args()

    source_payload, source_solution = _load_solution(args.solution)
    recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
    if source_payload["case"] != recipe["case"]:
        raise AssertionError("solution snapshot and third-switch recipe case mismatch")

    graph = load_case(args.data_dir, source_payload["case"])
    t0 = time.perf_counter()

    source_q2 = validate_q2_solution(graph, source_solution)
    source_q2.require_ok()
    source_official = evaluate_q3_solution(graph, source_solution, reuse_mode="official_literal")
    source_official.require_ok()
    source_safe = evaluate_q3_solution(graph, source_solution, reuse_mode="residency_safe")
    source_safe.require_ok()
    baseline = recipe["baseline"]
    if source_official.total_cycles != baseline["official_cycles"]:
        raise AssertionError("downloaded two-switch solution official cycles drifted")
    if source_safe.total_cycles != baseline["safe_cycles"]:
        raise AssertionError("downloaded two-switch solution safe cycles drifted")
    if source_q2.spill_count != baseline["spill_count"]:
        raise AssertionError("downloaded two-switch solution spill count drifted")
    if source_q2.extra_traffic != baseline["extra_traffic"]:
        raise AssertionError("downloaded two-switch solution extra traffic drifted")
    t1 = time.perf_counter()

    move = recipe["move"]
    third = replay_q3_critical_spill_switch_move(
        graph,
        source_solution,
        spill_index=move["spill_index"],
        mode=move["mode"],
        expected_reversed_edges=tuple(tuple(edge) for edge in move["reversed_edges"]),
    )
    expected_after = move["expected_after"]
    if third.official.total_cycles != expected_after["official_cycles"]:
        raise AssertionError("third switch official result drifted")
    if third.safe.total_cycles != expected_after["safe_cycles"]:
        raise AssertionError("third switch safe result drifted")
    if third.changed_positions != expected_after["changed_positions"]:
        raise AssertionError("third switch changed-position count drifted")
    t2 = time.perf_counter()

    third_q2 = validate_q2_solution(graph, third.solution)
    third_q2.require_ok()
    source_spills = tuple((s.buf_id, s.new_offset) for s in source_solution.spills)
    third_spills = tuple((s.buf_id, s.new_offset) for s in third.solution.spills)
    if third_spills != source_spills:
        raise AssertionError("third switch changed spill records")
    if third_q2.spill_count != source_q2.spill_count or third_q2.extra_traffic != source_q2.extra_traffic:
        raise AssertionError("third switch changed Q2 traffic/spill count")

    solution_payload = _serialize_solution(
        source_payload["case"],
        third.solution,
        third.official,
        third.safe,
        third_q2,
        {
            "source_solution": recipe["source_solution"],
            "third_switch_recipe": recipe,
        },
    )
    args.solution_out.parent.mkdir(parents=True, exist_ok=True)
    args.solution_out.write_text(
        json.dumps(solution_payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    fourth = search_q3_critical_spill_switch_bubbles(
        graph,
        third.solution,
        max_switches=args.max_switches,
        baseline_official=third.official,
        baseline_safe=third.safe,
    )
    t3 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, fourth.best_solution)
    final_q2.require_ok()
    final_spills = tuple((s.buf_id, s.new_offset) for s in fourth.best_solution.spills)
    if final_spills != third_spills:
        raise AssertionError("fourth critical switch changed spill records")
    if final_q2.spill_count != source_q2.spill_count:
        raise AssertionError("fourth critical switch changed spill count")
    if final_q2.extra_traffic != source_q2.extra_traffic:
        raise AssertionError("fourth critical switch changed extra traffic")
    if not fourth.best_official.ok or not fourth.best_safe.ok:
        raise AssertionError("fourth critical switch final timing invalid")
    if fourth.best_official.total_cycles > third.official.total_cycles:
        raise AssertionError("fourth critical switch regressed three-switch result")

    payload = {
        "case": source_payload["case"],
        "source_two_switch_official_cycles": source_official.total_cycles,
        "source_two_switch_safe_cycles": source_safe.total_cycles,
        "third_switch": {
            "spill_index": move["spill_index"],
            "mode": move["mode"],
            "reversed_edges": [list(edge) for edge in third.reversed_edges],
            "changed_positions": third.changed_positions,
            "official_cycles": third.official.total_cycles,
            "safe_cycles": third.safe.total_cycles,
        },
        "three_switch_solution_snapshot_written": str(args.solution_out),
        "fourth_switch_improved": fourth.improved,
        "fourth_switch_best_move": (
            None if fourth.best_move is None else [fourth.best_move[0], fourth.best_move[1]]
        ),
        "final_official_cycles": fourth.best_official.total_cycles,
        "final_safe_cycles": fourth.best_safe.total_cycles,
        "fourth_switch_improvement_cycles": third.official.total_cycles - fourth.best_official.total_cycles,
        "improvement_vs_saturated_cycles": 3781664 - fourth.best_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(fourth.best_safe.physical_overlap_errors),
        "valid": fourth.best_official.ok and fourth.best_safe.ok,
        "source_snapshot_validation_seconds": round(t1 - t0, 6),
        "third_exact_switch_replay_seconds": round(t2 - t1, 6),
        "fourth_switch_search_seconds": round(t3 - t2, 6),
        "total_seconds": round(t3 - t0, 6),
        "candidates": [asdict(candidate) for candidate in fourth.candidates],
        "trials": [asdict(trial) for trial in fourth.trials],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
