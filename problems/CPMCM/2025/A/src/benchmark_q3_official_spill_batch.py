from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from parser import load_case
from q2_promoted import solve_q2_promoted
from q3_official_spill_optimizer import optimize_q3_official_with_spill_batches

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Benchmark formal official Q3 optimizer plus critical-SPILL batch post-pass"
    )
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--case", choices=CASES)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--recolor-rounds", type=int, default=24)
    ap.add_argument("--recolor-targets", type=int, default=6)
    ap.add_argument("--recolor-starts", type=int, default=12)
    ap.add_argument("--spill-batch-rounds", type=int, default=12)
    ap.add_argument("--spill-batch-switches", type=int, default=64)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    cases = (args.case,) if args.case is not None else CASES
    rows: list[dict[str, object]] = []
    trace: dict[str, dict[str, object]] = {}

    for case in cases:
        graph = load_case(args.data_dir, case)
        promoted = solve_q2_promoted(graph)
        promoted.allocation.validation.require_ok()

        t0 = time.perf_counter()
        result = optimize_q3_official_with_spill_batches(
            graph,
            promoted.solution,
            max_rounds=args.rounds,
            recolor_max_rounds=args.recolor_rounds,
            recolor_max_targets=args.recolor_targets,
            recolor_max_starts=args.recolor_starts,
            spill_batch_max_rounds=args.spill_batch_rounds,
            spill_batch_max_switches=args.spill_batch_switches,
            spill_batch_prefix_sizes=(1, 2, 4, 8, 16, 24, 32, 48, 64),
        )
        seconds = time.perf_counter() - t0

        spill = result.spill_batches
        rows.append(
            {
                "case": case,
                "baseline_official_cycles": result.core.original_official_cycles,
                "core_official_cycles": result.core.official_timing.total_cycles,
                "final_official_cycles": result.official_timing.total_cycles,
                "spill_batch_improvement_cycles": (
                    result.core.official_timing.total_cycles - result.official_timing.total_cycles
                ),
                "official_improvement_pct_vs_baseline": round(
                    100.0
                    * (result.core.original_official_cycles - result.official_timing.total_cycles)
                    / result.core.original_official_cycles,
                    6,
                ),
                "core_safe_cycles": result.core.safe_timing.total_cycles,
                "final_safe_cycles": result.safe_timing.total_cycles,
                "spill_count": result.spill_count,
                "extra_traffic": result.extra_traffic,
                "spill_batch_accepted_rounds": 0 if spill is None else spill.accepted_rounds,
                "spill_batch_round_count": 0 if spill is None else len(spill.rounds),
                "spill_batch_saturated": False if spill is None else spill.saturated,
                "safe_overlap_errors": len(result.safe_timing.physical_overlap_errors),
                "valid": result.safe_timing.ok and result.official_timing.ok,
                "seconds": round(seconds, 6),
            }
        )

        trace[case] = {
            "core_steps": [
                {
                    "round": step.round_index,
                    "transformation": step.transformation,
                    "detail": step.detail,
                    "official_before": step.official_before,
                    "official_after": step.official_after,
                    "safe_before": step.safe_before,
                    "safe_after": step.safe_after,
                    "accepted": step.accepted,
                    "error": step.error,
                }
                for step in result.core.steps
            ],
            "spill_batch_rounds": []
            if spill is None
            else [
                {
                    "round": index,
                    "improved": item.improved,
                    "baseline_official_cycles": item.baseline_official.total_cycles,
                    "best_prefix_size": item.best_prefix_size,
                    "best_official_cycles": item.best_official.total_cycles,
                    "best_safe_cycles": item.best_safe.total_cycles,
                    "improvement_cycles": (
                        item.baseline_official.total_cycles - item.best_official.total_cycles
                    ),
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
                        for trial in item.trials
                    ],
                }
                for index, item in enumerate(spill.rounds, 1)
            ],
        }

    csv_path = args.out_dir / "q3_official_spill_batch_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.out_dir / "q3_official_spill_batch_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "q3_official_spill_batch_trace.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(csv_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
