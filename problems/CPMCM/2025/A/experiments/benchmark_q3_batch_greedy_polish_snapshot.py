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
            raise AssertionError("accepted greedy polish move has no strict trial record")
    return {
        "round": index,
        "improved": result.improved,
        "best_move": None if result.best_move is None else [result.best_move[0], result.best_move[1]],
        "best_reversed_edges": None if best_trial is None else [list(edge) for edge in best_trial.reversed_edges],
        "changed_positions": None if best_trial is None else best_trial.changed_positions,
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
    ap.add_argument("--solution", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-rounds", type=int, default=2)
    ap.add_argument("--max-switches", type=int, default=8)
    args = ap.parse_args()

    payload, solution = _load_solution(args.solution)
    graph = load_case(args.data_dir, payload["case"])

    t0 = time.perf_counter()
    q2 = validate_q2_solution(graph, solution)
    q2.require_ok()
    official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    official.require_ok()
    safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    safe.require_ok()
    if official.total_cycles != payload["official_cycles"]:
        raise AssertionError("batch solution official cycles drifted")
    if safe.total_cycles != payload["safe_cycles"]:
        raise AssertionError("batch solution safe cycles drifted")
    if q2.spill_count != payload["spill_count"] or q2.extra_traffic != payload["extra_traffic"]:
        raise AssertionError("batch solution Q2 invariants drifted")
    t1 = time.perf_counter()

    greedy = optimize_q3_critical_spill_switch_greedy(
        graph,
        solution,
        max_rounds=args.max_rounds,
        max_switches=args.max_switches,
        baseline_official=official,
        baseline_safe=safe,
    )
    t2 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, greedy.final_solution)
    final_q2.require_ok()
    original_spills = tuple((s.buf_id, s.new_offset) for s in solution.spills)
    final_spills = tuple((s.buf_id, s.new_offset) for s in greedy.final_solution.spills)
    if final_spills != original_spills:
        raise AssertionError("batch+greedy polish changed spill records")
    if final_q2.spill_count != q2.spill_count or final_q2.extra_traffic != q2.extra_traffic:
        raise AssertionError("batch+greedy polish changed Q2 traffic/spill count")

    rounds = [_round_payload(i, result) for i, result in enumerate(greedy.rounds, start=1)]
    out = {
        "case": payload["case"],
        "batch_official_cycles": official.total_cycles,
        "batch_safe_cycles": safe.total_cycles,
        "greedy_max_rounds": args.max_rounds,
        "greedy_max_switches": args.max_switches,
        "greedy_accepted_rounds": greedy.accepted_rounds,
        "greedy_round_count": len(greedy.rounds),
        "greedy_saturated": bool(greedy.rounds and not greedy.rounds[-1].improved),
        "final_official_cycles": greedy.final_official.total_cycles,
        "final_safe_cycles": greedy.final_safe.total_cycles,
        "polish_improvement_cycles": official.total_cycles - greedy.final_official.total_cycles,
        "improvement_vs_saturated_cycles": 3781664 - greedy.final_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(greedy.final_safe.physical_overlap_errors),
        "valid": greedy.final_official.ok and greedy.final_safe.ok,
        "snapshot_validation_seconds": round(t1 - t0, 6),
        "greedy_polish_seconds": round(t2 - t1, 6),
        "total_seconds": round(t2 - t0, 6),
        "rounds": rounds,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
