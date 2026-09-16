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
from q3_evaluator import evaluate_q3_solution


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
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--solution-out", type=Path, required=True)
    ap.add_argument("--max-rounds", type=int, default=12)
    args = ap.parse_args()

    source_payload, source_solution = _load_solution(args.solution)
    graph = load_case(args.data_dir, source_payload["case"])

    t0 = time.perf_counter()
    source_q2 = validate_q2_solution(graph, source_solution)
    source_q2.require_ok()
    source_official = evaluate_q3_solution(graph, source_solution, reuse_mode="official_literal")
    source_official.require_ok()
    source_safe = evaluate_q3_solution(graph, source_solution, reuse_mode="residency_safe")
    source_safe.require_ok()

    if source_official.total_cycles != int(source_payload["official_cycles"]):
        raise AssertionError("continuation source official timing drifted")
    if source_safe.total_cycles != int(source_payload["safe_cycles"]):
        raise AssertionError("continuation source safe timing drifted")
    if source_q2.spill_count != int(source_payload["spill_count"]):
        raise AssertionError("continuation source spill count drifted")
    if source_q2.extra_traffic != int(source_payload["extra_traffic"]):
        raise AssertionError("continuation source extra traffic drifted")
    if len(source_safe.physical_overlap_errors) != int(source_payload.get("safe_overlap_errors", 0)):
        raise AssertionError("continuation source safe-overlap count drifted")
    t1 = time.perf_counter()

    iterative = optimize_q3_critical_spill_batch_iterative(
        graph,
        source_solution,
        max_rounds=args.max_rounds,
        max_switches=64,
        prefix_sizes=(1, 2, 4, 8, 16, 24, 32, 48, 64),
        baseline_official=source_official,
        baseline_safe=source_safe,
    )
    t2 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, iterative.final_solution)
    final_q2.require_ok()
    source_spills = tuple((spill.buf_id, spill.new_offset) for spill in source_solution.spills)
    final_spills = tuple((spill.buf_id, spill.new_offset) for spill in iterative.final_solution.spills)
    if final_spills != source_spills:
        raise AssertionError("continuation changed spill records")
    if final_q2.spill_count != source_q2.spill_count:
        raise AssertionError("continuation changed spill count")
    if final_q2.extra_traffic != source_q2.extra_traffic:
        raise AssertionError("continuation changed extra traffic")

    snapshot = _serialize_solution(
        source_payload["case"],
        iterative.final_solution,
        iterative.final_official,
        iterative.final_safe,
        final_q2,
        {
            "continued_from": str(args.solution),
            "source_official_cycles": source_official.total_cycles,
            "source_safe_cycles": source_safe.total_cycles,
            "continuation_max_rounds": args.max_rounds,
            "continuation_accepted_rounds": iterative.accepted_rounds,
            "continuation_saturated": iterative.saturated,
            "round_best_prefixes": [result.best_prefix_size for result in iterative.rounds],
            "parent_provenance": source_payload.get("provenance"),
        },
    )
    args.solution_out.parent.mkdir(parents=True, exist_ok=True)
    args.solution_out.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    payload = {
        "case": source_payload["case"],
        "source_official_cycles": source_official.total_cycles,
        "source_safe_cycles": source_safe.total_cycles,
        "continuation_max_rounds": args.max_rounds,
        "continuation_accepted_rounds": iterative.accepted_rounds,
        "continuation_round_count": len(iterative.rounds),
        "continuation_saturated": iterative.saturated,
        "final_official_cycles": iterative.final_official.total_cycles,
        "final_safe_cycles": iterative.final_safe.total_cycles,
        "continuation_improvement_cycles": source_official.total_cycles - iterative.final_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(iterative.final_safe.physical_overlap_errors),
        "valid": iterative.final_official.ok and iterative.final_safe.ok,
        "source_validation_seconds": round(t1 - t0, 6),
        "continuation_seconds": round(t2 - t1, 6),
        "total_seconds": round(t2 - t0, 6),
        "rounds": [_round_payload(i, result) for i, result in enumerate(iterative.rounds, 1)],
        "solution_snapshot_written": str(args.solution_out),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
