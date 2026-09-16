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

from benchmark_q3_spill_switch_batch_snapshot import _load_solution
from parser import load_case
from q2_validator import validate_q2_solution
from q3_critical_spill_switch_batch import search_q3_critical_spill_out_batches
from q3_critical_spill_switch_recipe import replay_q3_critical_spill_switch_move
from q3_evaluator import evaluate_q3_solution


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--solution", type=Path, required=True)
    ap.add_argument("--polish-evidence", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    source_payload, current = _load_solution(args.solution)
    evidence = json.loads(args.polish_evidence.read_text(encoding="utf-8"))
    if source_payload["case"] != evidence["case"]:
        raise AssertionError("batch solution and polish evidence case mismatch")
    graph = load_case(args.data_dir, source_payload["case"])

    t0 = time.perf_counter()
    source_q2 = validate_q2_solution(graph, current)
    source_q2.require_ok()
    current_official = evaluate_q3_solution(graph, current, reuse_mode="official_literal")
    current_official.require_ok()
    current_safe = evaluate_q3_solution(graph, current, reuse_mode="residency_safe")
    current_safe.require_ok()
    if current_official.total_cycles != evidence["batch_official_cycles"]:
        raise AssertionError("batch-source official timing drifted")
    if current_safe.total_cycles != evidence["batch_safe_cycles"]:
        raise AssertionError("batch-source safe timing drifted")
    t1 = time.perf_counter()

    replayed = []
    for item in evidence["rounds"]:
        if not item["improved"]:
            break
        move = item["best_move"]
        replay = replay_q3_critical_spill_switch_move(
            graph,
            current,
            spill_index=int(move[0]),
            mode=str(move[1]),
            expected_reversed_edges=tuple(tuple(edge) for edge in item["best_reversed_edges"]),
        )
        if replay.official.total_cycles != item["best_official_cycles"]:
            raise AssertionError("greedy-polish official replay drifted")
        if replay.safe.total_cycles != item["best_safe_cycles"]:
            raise AssertionError("greedy-polish safe replay drifted")
        replayed.append({
            "round": item["round"],
            "move": move,
            "reversed_edges": item["best_reversed_edges"],
            "official_cycles": replay.official.total_cycles,
            "safe_cycles": replay.safe.total_cycles,
        })
        current = replay.solution
        current_official = replay.official
        current_safe = replay.safe
    if current_official.total_cycles != evidence["final_official_cycles"]:
        raise AssertionError("replayed polish final official timing drifted")
    if current_safe.total_cycles != evidence["final_safe_cycles"]:
        raise AssertionError("replayed polish final safe timing drifted")
    t2 = time.perf_counter()

    second_batch = search_q3_critical_spill_out_batches(
        graph,
        current,
        max_switches=8,
        prefix_sizes=(2, 4, 8),
        baseline_official=current_official,
        baseline_safe=current_safe,
    )
    t3 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, second_batch.best_solution)
    final_q2.require_ok()
    source_spills = tuple((s.buf_id, s.new_offset) for s in current.spills)
    final_spills = tuple((s.buf_id, s.new_offset) for s in second_batch.best_solution.spills)
    if final_spills != source_spills:
        raise AssertionError("second batch changed spill records")
    if final_q2.spill_count != source_q2.spill_count or final_q2.extra_traffic != source_q2.extra_traffic:
        raise AssertionError("second batch changed Q2 traffic/spill count")

    payload = {
        "case": evidence["case"],
        "polish_official_cycles": current_official.total_cycles,
        "polish_safe_cycles": current_safe.total_cycles,
        "replayed_polish_rounds": replayed,
        "second_batch_improved": second_batch.improved,
        "second_batch_best_prefix_size": second_batch.best_prefix_size,
        "final_official_cycles": second_batch.best_official.total_cycles,
        "final_safe_cycles": second_batch.best_safe.total_cycles,
        "second_batch_improvement_cycles": current_official.total_cycles - second_batch.best_official.total_cycles,
        "improvement_vs_saturated_cycles": 3781664 - second_batch.best_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(second_batch.best_safe.physical_overlap_errors),
        "valid": second_batch.best_official.ok and second_batch.best_safe.ok,
        "source_validation_seconds": round(t1 - t0, 6),
        "polish_exact_replay_seconds": round(t2 - t1, 6),
        "second_batch_seconds": round(t3 - t2, 6),
        "total_seconds": round(t3 - t0, 6),
        "trials": [
            {
                "prefix_size": trial.prefix_size,
                "spill_indices": list(trial.spill_indices),
                "reversed_edges": [list(edge) for edge in trial.reversed_edges],
                "q2_valid": trial.q2_valid,
                "safe_valid": trial.safe_valid,
                "official_cycles": trial.official_cycles,
                "safe_cycles": trial.safe_cycles,
                "changed_positions": trial.changed_positions,
                "error": trial.error,
            }
            for trial in second_batch.trials
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
