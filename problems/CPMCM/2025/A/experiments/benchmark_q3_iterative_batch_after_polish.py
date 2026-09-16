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

from benchmark_q3_spill_switch_batch_snapshot import _load_solution, _serialize_solution
from parser import load_case
from q2_validator import validate_q2_solution
from q3_conv_iterative_spill_batch import optimize_q3_critical_spill_batch_iterative
from q3_critical_spill_switch_batch import search_q3_critical_spill_out_batches
from q3_critical_spill_switch_recipe import replay_q3_critical_spill_switch_move
from q3_evaluator import evaluate_q3_solution


EXPECTED_SECOND_BATCH_OFFICIAL = 3_776_239
EXPECTED_SECOND_BATCH_SAFE = 4_112_927
EXPECTED_FIRST_ITERATIVE_ROUND = 3_772_909
SATURATED_REFERENCE = 3_781_664


def _trial_payload(trial) -> dict:
    return {
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


def _round_payload(index: int, result) -> dict:
    return {
        "round": index,
        "improved": result.improved,
        "baseline_official_cycles": result.baseline_official.total_cycles,
        "baseline_safe_cycles": result.baseline_safe.total_cycles,
        "best_prefix_size": result.best_prefix_size,
        "best_official_cycles": result.best_official.total_cycles,
        "best_safe_cycles": result.best_safe.total_cycles,
        "improvement_cycles": result.baseline_official.total_cycles - result.best_official.total_cycles,
        "trials": [_trial_payload(trial) for trial in result.trials],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--solution", type=Path, required=True)
    ap.add_argument("--polish-evidence", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--solution-out", type=Path, required=True)
    ap.add_argument("--max-rounds", type=int, default=4)
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

    replayed_polish = []
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
        replayed_polish.append(
            {
                "round": item["round"],
                "move": move,
                "official_cycles": replay.official.total_cycles,
                "safe_cycles": replay.safe.total_cycles,
            }
        )
        current = replay.solution
        current_official = replay.official
        current_safe = replay.safe
    if current_official.total_cycles != evidence["final_official_cycles"]:
        raise AssertionError("replayed polish final official timing drifted")
    if current_safe.total_cycles != evidence["final_safe_cycles"]:
        raise AssertionError("replayed polish final safe timing drifted")

    second_batch = search_q3_critical_spill_out_batches(
        graph,
        current,
        max_switches=8,
        prefix_sizes=(8,),
        baseline_official=current_official,
        baseline_safe=current_safe,
    )
    if not second_batch.improved or second_batch.best_prefix_size != 8:
        raise AssertionError("second-batch winner no longer replays as prefix 8")
    if second_batch.best_official.total_cycles != EXPECTED_SECOND_BATCH_OFFICIAL:
        raise AssertionError("second-batch official timing drifted")
    if second_batch.best_safe.total_cycles != EXPECTED_SECOND_BATCH_SAFE:
        raise AssertionError("second-batch safe timing drifted")
    t1 = time.perf_counter()

    iterative = optimize_q3_critical_spill_batch_iterative(
        graph,
        second_batch.best_solution,
        max_rounds=args.max_rounds,
        max_switches=64,
        prefix_sizes=(1, 2, 4, 8, 16, 24, 32, 48, 64),
        baseline_official=second_batch.best_official,
        baseline_safe=second_batch.best_safe,
    )
    t2 = time.perf_counter()

    if not iterative.rounds:
        raise AssertionError("iterative search produced no rounds")
    first_round = iterative.rounds[0]
    if not first_round.improved or first_round.best_prefix_size != 16:
        raise AssertionError("first iterative round no longer reproduces third-batch prefix 16")
    if first_round.best_official.total_cycles != EXPECTED_FIRST_ITERATIVE_ROUND:
        raise AssertionError("first iterative round official timing drifted")

    final_q2 = validate_q2_solution(graph, iterative.final_solution)
    final_q2.require_ok()
    if final_q2.spill_count != source_q2.spill_count or final_q2.extra_traffic != source_q2.extra_traffic:
        raise AssertionError("iterative batches changed Q2 traffic/spill count")
    if tuple((s.buf_id, s.new_offset) for s in iterative.final_solution.spills) != tuple(
        (s.buf_id, s.new_offset) for s in current.spills
    ):
        raise AssertionError("iterative batches changed spill records")

    snapshot = _serialize_solution(
        evidence["case"],
        iterative.final_solution,
        iterative.final_official,
        iterative.final_safe,
        final_q2,
        {
            "source_solution": str(args.solution),
            "polish_evidence": str(args.polish_evidence),
            "second_batch_prefix": 8,
            "iterative_max_rounds": args.max_rounds,
            "iterative_accepted_rounds": iterative.accepted_rounds,
            "iterative_saturated": iterative.saturated,
            "round_best_prefixes": [result.best_prefix_size for result in iterative.rounds],
        },
    )
    args.solution_out.parent.mkdir(parents=True, exist_ok=True)
    args.solution_out.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    payload = {
        "case": evidence["case"],
        "polish_official_cycles": current_official.total_cycles,
        "second_batch_official_cycles": second_batch.best_official.total_cycles,
        "iterative_max_rounds": args.max_rounds,
        "iterative_accepted_rounds": iterative.accepted_rounds,
        "iterative_round_count": len(iterative.rounds),
        "iterative_saturated": iterative.saturated,
        "final_official_cycles": iterative.final_official.total_cycles,
        "final_safe_cycles": iterative.final_safe.total_cycles,
        "improvement_vs_second_batch_cycles": (
            second_batch.best_official.total_cycles - iterative.final_official.total_cycles
        ),
        "improvement_vs_saturated_cycles": SATURATED_REFERENCE - iterative.final_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(iterative.final_safe.physical_overlap_errors),
        "valid": iterative.final_official.ok and iterative.final_safe.ok,
        "setup_and_second_batch_seconds": round(t1 - t0, 6),
        "iterative_seconds": round(t2 - t1, 6),
        "total_seconds": round(t2 - t0, 6),
        "rounds": [_round_payload(i, result) for i, result in enumerate(iterative.rounds, 1)],
        "replayed_polish_rounds": replayed_polish,
        "solution_snapshot_written": str(args.solution_out),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
