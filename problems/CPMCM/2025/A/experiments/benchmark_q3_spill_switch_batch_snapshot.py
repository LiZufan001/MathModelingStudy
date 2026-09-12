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
from q3_critical_spill_switch_batch import search_q3_critical_spill_out_batches
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
    args = ap.parse_args()

    source_payload, source_solution = _load_solution(args.solution)
    recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
    if source_payload["case"] != recipe["case"]:
        raise AssertionError("solution snapshot and fourth-switch recipe case mismatch")
    graph = load_case(args.data_dir, source_payload["case"])

    t0 = time.perf_counter()
    source_q2 = validate_q2_solution(graph, source_solution)
    source_q2.require_ok()
    source_official = evaluate_q3_solution(graph, source_solution, reuse_mode="official_literal")
    source_official.require_ok()
    source_safe = evaluate_q3_solution(graph, source_solution, reuse_mode="residency_safe")
    source_safe.require_ok()
    baseline = recipe["baseline"]
    if source_official.total_cycles != baseline["official_cycles"] or source_safe.total_cycles != baseline["safe_cycles"]:
        raise AssertionError("downloaded three-switch solution timing drifted")
    if source_q2.spill_count != baseline["spill_count"] or source_q2.extra_traffic != baseline["extra_traffic"]:
        raise AssertionError("downloaded three-switch solution Q2 invariants drifted")
    t1 = time.perf_counter()

    move = recipe["move"]
    fourth = replay_q3_critical_spill_switch_move(
        graph,
        source_solution,
        spill_index=move["spill_index"],
        mode=move["mode"],
        expected_reversed_edges=tuple(tuple(edge) for edge in move["reversed_edges"]),
    )
    expected_after = move["expected_after"]
    if fourth.official.total_cycles != expected_after["official_cycles"]:
        raise AssertionError("fourth switch official result drifted")
    if fourth.safe.total_cycles != expected_after["safe_cycles"]:
        raise AssertionError("fourth switch safe result drifted")
    if fourth.changed_positions != expected_after["changed_positions"]:
        raise AssertionError("fourth switch changed-position count drifted")
    t2 = time.perf_counter()

    batch = search_q3_critical_spill_out_batches(
        graph,
        fourth.solution,
        max_switches=8,
        prefix_sizes=(2, 4, 8),
        baseline_official=fourth.official,
        baseline_safe=fourth.safe,
    )
    t3 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, batch.best_solution)
    final_q2.require_ok()
    base_spills = tuple((s.buf_id, s.new_offset) for s in fourth.solution.spills)
    final_spills = tuple((s.buf_id, s.new_offset) for s in batch.best_solution.spills)
    if final_spills != base_spills:
        raise AssertionError("batch critical-SPILL probe changed spill records")
    if final_q2.spill_count != source_q2.spill_count or final_q2.extra_traffic != source_q2.extra_traffic:
        raise AssertionError("batch critical-SPILL probe changed Q2 traffic/spill count")

    final_snapshot = _serialize_solution(
        source_payload["case"],
        batch.best_solution,
        batch.best_official,
        batch.best_safe,
        final_q2,
        {
            "source_solution": recipe["source_solution"],
            "fourth_switch_recipe": recipe,
            "batch_prefix_sizes": [2, 4, 8],
            "best_prefix_size": batch.best_prefix_size,
        },
    )
    args.solution_out.parent.mkdir(parents=True, exist_ok=True)
    args.solution_out.write_text(
        json.dumps(final_snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    payload = {
        "case": source_payload["case"],
        "four_switch_official_cycles": fourth.official.total_cycles,
        "four_switch_safe_cycles": fourth.safe.total_cycles,
        "batch_improved": batch.improved,
        "best_prefix_size": batch.best_prefix_size,
        "final_official_cycles": batch.best_official.total_cycles,
        "final_safe_cycles": batch.best_safe.total_cycles,
        "batch_improvement_cycles": fourth.official.total_cycles - batch.best_official.total_cycles,
        "improvement_vs_saturated_cycles": 3781664 - batch.best_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(batch.best_safe.physical_overlap_errors),
        "valid": batch.best_official.ok and batch.best_safe.ok,
        "source_snapshot_validation_seconds": round(t1 - t0, 6),
        "fourth_exact_switch_replay_seconds": round(t2 - t1, 6),
        "batch_search_seconds": round(t3 - t2, 6),
        "total_seconds": round(t3 - t0, 6),
        "trials": [asdict(trial) for trial in batch.trials],
        "solution_snapshot_written": str(args.solution_out),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
