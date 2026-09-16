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

from model import ComputeGraph
from parser import load_case
from q2_model import Q2Solution, SpillRecord
from q2_validator import validate_q2_solution
from q3_critical_spill_switch import search_q3_critical_spill_switch_bubbles
from q3_evaluator import evaluate_q3_solution


CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)


def _read_solution(input_dir: Path, case: str) -> Q2Solution:
    schedule_path = input_dir / f"{case}_schedule.txt"
    memory_path = input_dir / f"{case}_memory.txt"
    spill_path = input_dir / f"{case}_spill.txt"

    schedule = tuple(
        int(line.strip())
        for line in schedule_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    initial_offsets: dict[int, int] = {}
    for line in memory_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        key, value = line.split(":", 1)
        initial_offsets[int(key)] = int(value)
    spills: list[SpillRecord] = []
    for line in spill_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        key, value = line.split(":", 1)
        spills.append(SpillRecord(int(key), int(value)))
    return Q2Solution(schedule, initial_offsets, tuple(spills))


def _write_solution(out_dir: Path, case: str, solution: Q2Solution) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{case}_schedule.txt").write_text(
        "".join(f"{node_id}\n" for node_id in solution.schedule), encoding="utf-8"
    )
    (out_dir / f"{case}_memory.txt").write_text(
        "".join(
            f"{buf_id}:{solution.initial_offsets[buf_id]}\n"
            for buf_id in sorted(solution.initial_offsets)
        ),
        encoding="utf-8",
    )
    (out_dir / f"{case}_spill.txt").write_text(
        "".join(f"{spill.buf_id}:{spill.new_offset}\n" for spill in solution.spills),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="One checkpointed single-switch Q3 probe")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--case", choices=CASES, required=True)
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--max-switches", type=int, default=4)
    ap.add_argument("--expected-official", type=int)
    args = ap.parse_args()

    if args.max_switches <= 0:
        raise ValueError("max-switches must be positive")

    graph: ComputeGraph = load_case(args.data_dir, args.case)
    solution = _read_solution(args.input_dir, args.case)
    q2 = validate_q2_solution(graph, solution)
    q2.require_ok()
    baseline_official = evaluate_q3_solution(
        graph, solution, reuse_mode="official_literal"
    )
    baseline_official.require_ok()
    baseline_safe = evaluate_q3_solution(
        graph, solution, reuse_mode="residency_safe"
    )
    baseline_safe.require_ok()
    if args.expected_official is not None and baseline_official.total_cycles != args.expected_official:
        raise AssertionError(
            f"input official timing drifted: {baseline_official.total_cycles} != {args.expected_official}"
        )

    t0 = time.perf_counter()
    result = search_q3_critical_spill_switch_bubbles(
        graph,
        solution,
        max_switches=args.max_switches,
        baseline_official=baseline_official,
        baseline_safe=baseline_safe,
    )
    elapsed = time.perf_counter() - t0

    final_q2 = validate_q2_solution(graph, result.best_solution)
    final_q2.require_ok()
    if result.best_solution.spills != solution.spills:
        raise AssertionError("single-switch checkpoint changed exact SPILL records")
    if final_q2.spill_count != q2.spill_count:
        raise AssertionError("single-switch checkpoint changed spill count")
    if final_q2.extra_traffic != q2.extra_traffic:
        raise AssertionError("single-switch checkpoint changed extra traffic")
    result.best_official.require_ok()
    result.best_safe.require_ok()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    next_dir = args.out_dir / "next"
    _write_solution(next_dir, args.case, result.best_solution)

    payload = {
        "case": args.case,
        "operator": "critical_spill_single_switch_bubble",
        "max_switches": args.max_switches,
        "baseline": {
            "official_cycles": baseline_official.total_cycles,
            "safe_cycles": baseline_safe.total_cycles,
            "spill_count": q2.spill_count,
            "extra_traffic": q2.extra_traffic,
        },
        "result": {
            "improved": result.improved,
            "best_move": None
            if result.best_move is None
            else {"spill_index": result.best_move[0], "mode": result.best_move[1]},
            "official_cycles": result.best_official.total_cycles,
            "safe_cycles": result.best_safe.total_cycles,
            "improvement_cycles": baseline_official.total_cycles
            - result.best_official.total_cycles,
            "spill_count": final_q2.spill_count,
            "extra_traffic": final_q2.extra_traffic,
            "safe_overlap_errors": len(result.best_safe.physical_overlap_errors),
            "valid": result.best_official.ok and result.best_safe.ok,
        },
        "candidates": [
            {
                "spill_index": candidate.spill_index,
                "out_id": candidate.out_id,
                "in_id": candidate.in_id,
                "left_run_cycles": candidate.left_run_cycles,
                "right_run_cycles": candidate.right_run_cycles,
                "combined_run_cycles": candidate.combined_run_cycles,
            }
            for candidate in result.candidates
        ],
        "trials": [
            {
                "spill_index": trial.spill_index,
                "mode": trial.mode,
                "reversed_edges": [list(edge) for edge in trial.reversed_edges],
                "left_run_cycles": trial.left_run_cycles,
                "right_run_cycles": trial.right_run_cycles,
                "q2_valid": trial.q2_valid,
                "safe_valid": trial.safe_valid,
                "official_cycles": trial.official_cycles,
                "safe_cycles": trial.safe_cycles,
                "changed_positions": trial.changed_positions,
                "error": trial.error,
            }
            for trial in result.trials
        ],
        "seconds": round(elapsed, 6),
        "checkpoint": "next",
    }
    (args.out_dir / "single-switch-checkpoint.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
