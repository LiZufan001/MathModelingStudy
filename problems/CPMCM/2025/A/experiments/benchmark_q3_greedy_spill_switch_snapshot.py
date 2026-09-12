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
from q2_model import Q2Solution, SpillRecord
from q2_validator import validate_q2_solution
from q3_conv_greedy_spill_switch import optimize_q3_critical_spill_switch_greedy
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


def _round_payload(index: int, result) -> dict:
    best_trial = None
    if result.best_move is not None:
        for trial in result.trials:
            if (
                trial.spill_index == result.best_move[0]
                and trial.mode == result.best_move[1]
                and trial.official_cycles == result.best_official.total_cycles
                and trial.safe_valid is True
            ):
                best_trial = trial
                break
        if best_trial is None:
            raise AssertionError("accepted greedy switch has no strict trial record")
    return {
        "round": index,
        "baseline_official_cycles": result.baseline_official.total_cycles,
        "baseline_safe_cycles": result.baseline_safe.total_cycles,
        "improved": result.improved,
        "best_move": None if result.best_move is None else [result.best_move[0], result.best_move[1]],
        "best_reversed_edges": (
            None if best_trial is None else [list(edge) for edge in best_trial.reversed_edges]
        ),
        "changed_positions": None if best_trial is None else best_trial.changed_positions,
        "best_official_cycles": result.best_official.total_cycles,
        "best_safe_cycles": result.best_safe.total_cycles,
        "improvement_cycles": result.baseline_official.total_cycles - result.best_official.total_cycles,
        "candidate_count": len(result.candidates),
        "trial_count": len(result.trials),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--solution", type=Path, required=True)
    ap.add_argument("--recipe", type=Path, required=True)
    ap.add_argument("--solution-out", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-rounds", type=int, default=4)
    ap.add_argument("--max-switches", type=int, default=8)
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
    if source_official.total_cycles != baseline["official_cycles"]:
        raise AssertionError("downloaded three-switch solution official cycles drifted")
    if source_safe.total_cycles != baseline["safe_cycles"]:
        raise AssertionError("downloaded three-switch solution safe cycles drifted")
    if source_q2.spill_count != baseline["spill_count"]:
        raise AssertionError("downloaded three-switch solution spill count drifted")
    if source_q2.extra_traffic != baseline["extra_traffic"]:
        raise AssertionError("downloaded three-switch solution extra traffic drifted")
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

    fourth_q2 = validate_q2_solution(graph, fourth.solution)
    fourth_q2.require_ok()
    source_spills = tuple((s.buf_id, s.new_offset) for s in source_solution.spills)
    fourth_spills = tuple((s.buf_id, s.new_offset) for s in fourth.solution.spills)
    if fourth_spills != source_spills:
        raise AssertionError("fourth switch changed spill records")
    if fourth_q2.spill_count != source_q2.spill_count or fourth_q2.extra_traffic != source_q2.extra_traffic:
        raise AssertionError("fourth switch changed Q2 traffic/spill count")

    greedy = optimize_q3_critical_spill_switch_greedy(
        graph,
        fourth.solution,
        max_rounds=args.max_rounds,
        max_switches=args.max_switches,
        baseline_official=fourth.official,
        baseline_safe=fourth.safe,
    )
    t3 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, greedy.final_solution)
    final_q2.require_ok()
    final_spills = tuple((s.buf_id, s.new_offset) for s in greedy.final_solution.spills)
    if final_spills != fourth_spills:
        raise AssertionError("greedy critical-SPILL loop changed spill records")
    if final_q2.spill_count != source_q2.spill_count:
        raise AssertionError("greedy critical-SPILL loop changed spill count")
    if final_q2.extra_traffic != source_q2.extra_traffic:
        raise AssertionError("greedy critical-SPILL loop changed extra traffic")

    rounds = [_round_payload(i, result) for i, result in enumerate(greedy.rounds, start=1)]
    provenance = {
        "source_solution": recipe["source_solution"],
        "fourth_switch_recipe": recipe,
        "greedy_rounds": rounds,
    }
    final_snapshot = _serialize_solution(
        source_payload["case"],
        greedy.final_solution,
        greedy.final_official,
        greedy.final_safe,
        final_q2,
        provenance,
    )
    args.solution_out.parent.mkdir(parents=True, exist_ok=True)
    args.solution_out.write_text(
        json.dumps(final_snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    payload = {
        "case": source_payload["case"],
        "source_three_switch_official_cycles": source_official.total_cycles,
        "source_three_switch_safe_cycles": source_safe.total_cycles,
        "fourth_switch": {
            "spill_index": move["spill_index"],
            "mode": move["mode"],
            "reversed_edges": [list(edge) for edge in fourth.reversed_edges],
            "changed_positions": fourth.changed_positions,
            "official_cycles": fourth.official.total_cycles,
            "safe_cycles": fourth.safe.total_cycles,
        },
        "greedy_max_rounds": args.max_rounds,
        "greedy_max_switches": args.max_switches,
        "greedy_accepted_rounds": greedy.accepted_rounds,
        "greedy_round_count": len(greedy.rounds),
        "greedy_saturated": bool(greedy.rounds and not greedy.rounds[-1].improved),
        "final_official_cycles": greedy.final_official.total_cycles,
        "final_safe_cycles": greedy.final_safe.total_cycles,
        "greedy_improvement_cycles": fourth.official.total_cycles - greedy.final_official.total_cycles,
        "improvement_vs_saturated_cycles": 3781664 - greedy.final_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(greedy.final_safe.physical_overlap_errors),
        "valid": greedy.final_official.ok and greedy.final_safe.ok,
        "source_snapshot_validation_seconds": round(t1 - t0, 6),
        "fourth_exact_switch_replay_seconds": round(t2 - t1, 6),
        "greedy_search_seconds": round(t3 - t2, 6),
        "total_seconds": round(t3 - t0, 6),
        "rounds": rounds,
        "final_solution_snapshot_written": str(args.solution_out),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
