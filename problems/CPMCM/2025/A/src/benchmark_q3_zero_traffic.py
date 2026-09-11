from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from parser import load_case
from q2_promoted import solve_q2_promoted
from q3_zero_traffic_optimizer import optimize_q3_zero_traffic

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark monotone zero-traffic Q3 optimizer")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--rounds", type=int, default=2)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    trace: dict[str, list[dict[str, object]]] = {}
    for case in CASES:
        graph = load_case(args.data_dir, case)
        promoted = solve_q2_promoted(graph)
        q2 = promoted.allocation
        q2.validation.require_ok()

        t0 = time.perf_counter()
        result = optimize_q3_zero_traffic(graph, q2.solution, max_rounds=args.rounds)
        seconds = time.perf_counter() - t0
        rows.append(
            {
                "case": case,
                "polish_window": promoted.polish_window,
                "baseline_cycles": result.original_cycles,
                "optimized_cycles": result.timing.total_cycles,
                "cycle_delta": result.timing.total_cycles - result.original_cycles,
                "cycle_ratio": round(result.timing.total_cycles / result.original_cycles, 6),
                "improvement_pct": round(
                    100.0 * (result.original_cycles - result.timing.total_cycles) / result.original_cycles,
                    6,
                ),
                "spill_count": result.spill_count,
                "extra_traffic": result.extra_traffic,
                "accepted_steps": sum(1 for step in result.steps if step.accepted),
                "steps": len(result.steps),
                "safe_overlap_errors": len(result.timing.physical_overlap_errors),
                "seconds": round(seconds, 6),
                "valid": result.timing.ok,
            }
        )
        trace[case] = [
            {
                "round": step.round_index,
                "transformation": step.transformation,
                "detail": step.detail,
                "cycles_before": step.cycles_before,
                "cycles_after": step.cycles_after,
                "accepted": step.accepted,
                "error": step.error,
            }
            for step in result.steps
        ]

    csv_path = args.out_dir / "q3_zero_traffic_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.out_dir / "q3_zero_traffic_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.out_dir / "q3_zero_traffic_trace.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(csv_path.read_text(encoding="utf-8"))
    print(json.dumps(trace, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
