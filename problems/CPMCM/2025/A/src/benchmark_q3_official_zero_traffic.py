from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from parser import load_case
from q2_promoted import solve_q2_promoted
from q3_official_optimizer import optimize_q3_official_zero_traffic

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
        description="Benchmark official-literal objective Q3 optimizer at fixed promoted-Q2 traffic"
    )
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
        result = optimize_q3_official_zero_traffic(
            graph,
            q2.solution,
            max_rounds=args.rounds,
        )
        seconds = time.perf_counter() - t0

        official_delta = result.official_timing.total_cycles - result.original_official_cycles
        safe_delta = result.safe_timing.total_cycles - result.original_safe_cycles
        rows.append(
            {
                "case": case,
                "polish_window": promoted.polish_window,
                "baseline_official_cycles": result.original_official_cycles,
                "optimized_official_cycles": result.official_timing.total_cycles,
                "official_cycle_delta": official_delta,
                "official_cycle_ratio": round(
                    result.official_timing.total_cycles / result.original_official_cycles,
                    6,
                ),
                "official_improvement_pct": round(
                    100.0 * (-official_delta) / result.original_official_cycles,
                    6,
                ),
                "baseline_safe_cycles": result.original_safe_cycles,
                "optimized_safe_cycles": result.safe_timing.total_cycles,
                "safe_cycle_delta": safe_delta,
                "safe_cycle_ratio": round(
                    result.safe_timing.total_cycles / result.original_safe_cycles,
                    6,
                ),
                "spill_count": result.spill_count,
                "extra_traffic": result.extra_traffic,
                "accepted_steps": sum(1 for step in result.steps if step.accepted),
                "steps": len(result.steps),
                "safe_overlap_errors": len(result.safe_timing.physical_overlap_errors),
                "literal_overlap_errors": len(result.official_timing.physical_overlap_errors),
                "seconds": round(seconds, 6),
                "valid": result.safe_timing.ok and result.official_timing.ok,
            }
        )
        trace[case] = [
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
            for step in result.steps
        ]

    csv_path = args.out_dir / "q3_official_zero_traffic_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.out_dir / "q3_official_zero_traffic_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "q3_official_zero_traffic_trace.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(csv_path.read_text(encoding="utf-8"))
    print(json.dumps(trace, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
