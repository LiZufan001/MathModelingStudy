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

from benchmark_q3_priority_snapshot import _replay_snapshot
from parser import load_case
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_conv_greedy_spill_switch import optimize_q3_critical_spill_switch_greedy
from q3_critical_spill_switch import search_q3_critical_spill_switch_bubbles
from q3_critical_spill_switch_batch import search_q3_critical_spill_out_batches


def _best_trial(result):
    if result.best_move is None:
        return None
    for trial in result.trials:
        if (
            trial.spill_index == result.best_move[0]
            and trial.mode == result.best_move[1]
            and trial.official_cycles == result.best_official.total_cycles
            and trial.safe_valid is True
        ):
            return trial
    raise AssertionError("accepted seed move has no strict trial")


def _round_payload(index: int, result) -> dict:
    trial = _best_trial(result)
    return {
        "round": index,
        "improved": result.improved,
        "best_move": None if result.best_move is None else list(result.best_move),
        "best_reversed_edges": None if trial is None else [list(edge) for edge in trial.reversed_edges],
        "baseline_official_cycles": result.baseline_official.total_cycles,
        "best_official_cycles": result.best_official.total_cycles,
        "baseline_safe_cycles": result.baseline_safe.total_cycles,
        "best_safe_cycles": result.best_safe.total_cycles,
        "improvement_cycles": result.baseline_official.total_cycles - result.best_official.total_cycles,
        "candidate_count": len(result.candidates),
        "trial_count": len(result.trials),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-switches", type=int, default=8)
    ap.add_argument("--batch-prefixes", default="2,4,8")
    ap.add_argument("--greedy-rounds", type=int, default=2)
    args = ap.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    graph = load_case(args.data_dir, snapshot["case"])
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()

    t0 = time.perf_counter()
    saturated, saturated_official, saturated_safe = _replay_snapshot(
        graph, promoted.solution, snapshot
    )
    saturated_q2 = validate_q2_solution(graph, saturated)
    saturated_q2.require_ok()
    t1 = time.perf_counter()

    seed = search_q3_critical_spill_switch_bubbles(
        graph,
        saturated,
        max_switches=args.max_switches,
        baseline_official=saturated_official,
        baseline_safe=saturated_safe,
    )
    t2 = time.perf_counter()

    prefixes = tuple(int(item) for item in args.batch_prefixes.split(",") if item)
    batch = search_q3_critical_spill_out_batches(
        graph,
        seed.best_solution,
        max_switches=args.max_switches,
        prefix_sizes=prefixes,
        baseline_official=seed.best_official,
        baseline_safe=seed.best_safe,
    )
    t3 = time.perf_counter()

    greedy = optimize_q3_critical_spill_switch_greedy(
        graph,
        batch.best_solution,
        max_rounds=args.greedy_rounds,
        max_switches=args.max_switches,
        baseline_official=batch.best_official,
        baseline_safe=batch.best_safe,
    )
    t4 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, greedy.final_solution)
    final_q2.require_ok()
    original_spills = tuple((s.buf_id, s.new_offset) for s in saturated.spills)
    final_spills = tuple((s.buf_id, s.new_offset) for s in greedy.final_solution.spills)
    if final_spills != original_spills:
        raise AssertionError("seed+batch+greedy changed spill records")
    if final_q2.spill_count != saturated_q2.spill_count:
        raise AssertionError("seed+batch+greedy changed spill count")
    if final_q2.extra_traffic != saturated_q2.extra_traffic:
        raise AssertionError("seed+batch+greedy changed extra traffic")

    seed_trial = _best_trial(seed)
    out = {
        "case": snapshot["case"],
        "saturated_official_cycles": saturated_official.total_cycles,
        "saturated_safe_cycles": saturated_safe.total_cycles,
        "seed_improved": seed.improved,
        "seed_best_move": None if seed.best_move is None else list(seed.best_move),
        "seed_reversed_edges": None if seed_trial is None else [list(edge) for edge in seed_trial.reversed_edges],
        "seed_official_cycles": seed.best_official.total_cycles,
        "seed_safe_cycles": seed.best_safe.total_cycles,
        "seed_improvement_cycles": saturated_official.total_cycles - seed.best_official.total_cycles,
        "batch_improved": batch.improved,
        "batch_best_prefix_size": batch.best_prefix_size,
        "batch_official_cycles": batch.best_official.total_cycles,
        "batch_safe_cycles": batch.best_safe.total_cycles,
        "batch_improvement_cycles": seed.best_official.total_cycles - batch.best_official.total_cycles,
        "batch_trials": [
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
            for trial in batch.trials
        ],
        "greedy_accepted_rounds": greedy.accepted_rounds,
        "greedy_round_count": len(greedy.rounds),
        "greedy_saturated": bool(greedy.rounds and not greedy.rounds[-1].improved),
        "greedy_rounds": [_round_payload(i, result) for i, result in enumerate(greedy.rounds, 1)],
        "final_official_cycles": greedy.final_official.total_cycles,
        "final_safe_cycles": greedy.final_safe.total_cycles,
        "total_improvement_cycles": saturated_official.total_cycles - greedy.final_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(greedy.final_safe.physical_overlap_errors),
        "valid": greedy.final_official.ok and greedy.final_safe.ok,
        "saturated_replay_seconds": round(t1 - t0, 6),
        "seed_seconds": round(t2 - t1, 6),
        "batch_seconds": round(t3 - t2, 6),
        "greedy_seconds": round(t4 - t3, 6),
        "total_seconds": round(t4 - t0, 6),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
