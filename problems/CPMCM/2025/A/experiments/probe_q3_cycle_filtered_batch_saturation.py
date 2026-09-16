from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from parser import load_case
from probe_q3_single_switch_checkpoint import _read_solution, _write_solution
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution


def main() -> int:
    ap = argparse.ArgumentParser(description="Fresh-rerank cycle-filtered SPILL batch saturation")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--expected-official", type=int)
    ap.add_argument("--max-switches", type=int, default=16)
    ap.add_argument("--max-rounds", type=int, default=8)
    args = ap.parse_args()
    if args.max_switches <= 0 or args.max_rounds <= 0:
        raise ValueError("max-switches and max-rounds must be positive")

    graph = load_case(args.data_dir, args.case)
    initial = _read_solution(args.input_dir, args.case)
    initial_q2 = validate_q2_solution(graph, initial)
    initial_q2.require_ok()
    initial_official = evaluate_q3_solution(graph, initial, reuse_mode="official_literal")
    initial_official.require_ok()
    initial_safe = evaluate_q3_solution(graph, initial, reuse_mode="residency_safe")
    initial_safe.require_ok()
    if args.expected_official is not None and initial_official.total_cycles != args.expected_official:
        raise AssertionError(
            f"input official timing drifted: {initial_official.total_cycles} != {args.expected_official}"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    history: list[dict[str, object]] = []
    current_dir = args.input_dir
    current_cycles = initial_official.total_cycles
    current_safe_cycles = initial_safe.total_cycles
    saturated = False
    stop_reason = "max_rounds_reached"
    t0 = time.perf_counter()

    probe_script = EXP / "probe_q3_cycle_filtered_batch.py"
    for round_no in range(1, args.max_rounds + 1):
        round_dir = args.out_dir / f"round-{round_no:02d}"
        command = [
            sys.executable,
            str(probe_script),
            "--data-dir",
            str(args.data_dir),
            "--case",
            args.case,
            "--input-dir",
            str(current_dir),
            "--out-dir",
            str(round_dir),
            "--expected-official",
            str(current_cycles),
            "--max-switches",
            str(args.max_switches),
        ]
        rt0 = time.perf_counter()
        completed = subprocess.run(command, check=False, text=True, capture_output=True)
        (round_dir / "stdout.txt").parent.mkdir(parents=True, exist_ok=True)
        (round_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (round_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            stop_reason = "round_error"
            raise RuntimeError(
                f"cycle-filtered round {round_no} failed with {completed.returncode}: {completed.stderr[-2000:]}"
            )

        payload = json.loads((round_dir / "cycle-filtered-batch.json").read_text(encoding="utf-8"))
        result = payload["result"]
        record = {
            "round": round_no,
            "baseline_official_cycles": payload["baseline"]["official_cycles"],
            "baseline_safe_cycles": payload["baseline"]["safe_cycles"],
            "filtered_spill_indices": [item["spill_index"] for item in payload["filtered_out"]],
            "eligible_spill_indices": payload["eligible_spill_indices"],
            "improved": result["improved"],
            "best_prefix_size": result["best_prefix_size"],
            "official_cycles": result["official_cycles"],
            "safe_cycles": result["safe_cycles"],
            "improvement_cycles": result["improvement_cycles"],
            "seconds": round(time.perf_counter() - rt0, 6),
        }
        history.append(record)

        if not result["improved"]:
            saturated = True
            stop_reason = "no_improvement"
            break

        current_dir = round_dir / "next"
        current_cycles = int(result["official_cycles"])
        current_safe_cycles = int(result["safe_cycles"])

    final_solution = _read_solution(current_dir, args.case)
    final_q2 = validate_q2_solution(graph, final_solution)
    final_q2.require_ok()
    if tuple((s.buf_id, s.new_offset) for s in final_solution.spills) != tuple(
        (s.buf_id, s.new_offset) for s in initial.spills
    ):
        raise AssertionError("cycle-filtered saturation changed exact SPILL records")
    if final_q2.spill_count != initial_q2.spill_count or final_q2.extra_traffic != initial_q2.extra_traffic:
        raise AssertionError("cycle-filtered saturation changed Q2 metrics")
    final_official = evaluate_q3_solution(graph, final_solution, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, final_solution, reuse_mode="residency_safe")
    final_safe.require_ok()
    if final_official.total_cycles != current_cycles or final_safe.total_cycles != current_safe_cycles:
        raise AssertionError("cycle-filtered saturation final replay mismatch")

    _write_solution(args.out_dir / "Problem3", args.case, final_solution)
    summary = {
        "case": args.case,
        "operator": "fresh_rerank_cycle_filtered_critical_spill_batch",
        "max_switches": args.max_switches,
        "max_rounds": args.max_rounds,
        "initial_official_cycles": initial_official.total_cycles,
        "initial_safe_cycles": initial_safe.total_cycles,
        "final_official_cycles": final_official.total_cycles,
        "final_safe_cycles": final_safe.total_cycles,
        "improvement_cycles": initial_official.total_cycles - final_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(final_safe.physical_overlap_errors),
        "valid": final_official.ok and final_safe.ok,
        "saturated": saturated,
        "stop_reason": stop_reason,
        "round_count": len(history),
        "accepted_rounds": sum(1 for item in history if item["improved"]),
        "rounds": history,
        "seconds": round(time.perf_counter() - t0, 6),
    }
    (args.out_dir / "cycle-filtered-saturation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
