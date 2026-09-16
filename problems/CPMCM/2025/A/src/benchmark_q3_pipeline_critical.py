from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from parser import load_case
from q2_promoted import solve_q2_promoted
from q3_address_portfolio import select_q3_address_portfolio
from q3_pipeline_scheduler import reschedule_q3_critical

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark zero-traffic Q3 pipeline rescheduling")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for case in CASES:
        graph = load_case(args.data_dir, case)
        promoted = solve_q2_promoted(graph)
        q2 = promoted.allocation
        q2.validation.require_ok()

        t0 = time.perf_counter()
        address = select_q3_address_portfolio(graph, q2.solution)
        address_seconds = time.perf_counter() - t0

        t1 = time.perf_counter()
        try:
            rescheduled = reschedule_q3_critical(graph, address.solution)
            schedule_seconds = time.perf_counter() - t1
            rows.append(
                {
                    "case": case,
                    "polish_window": promoted.polish_window,
                    "address_policy": address.policy,
                    "address_cycles": address.timing.total_cycles,
                    "critical_cycles": rescheduled.timing.total_cycles,
                    "cycle_delta": rescheduled.timing.total_cycles - address.timing.total_cycles,
                    "cycle_ratio": round(
                        rescheduled.timing.total_cycles / address.timing.total_cycles, 6
                    ),
                    "spill_count": q2.validation.spill_count,
                    "extra_traffic": q2.validation.extra_traffic,
                    "changed_positions": rescheduled.changed_positions,
                    "reuse_edges": rescheduled.timing.reuse_edge_count,
                    "critical_path_nodes": len(rescheduled.timing.critical_path),
                    "address_seconds": round(address_seconds, 6),
                    "schedule_seconds": round(schedule_seconds, 6),
                    "valid": True,
                    "error": "",
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "case": case,
                    "polish_window": promoted.polish_window,
                    "address_policy": address.policy,
                    "address_cycles": address.timing.total_cycles,
                    "critical_cycles": None,
                    "cycle_delta": None,
                    "cycle_ratio": None,
                    "spill_count": q2.validation.spill_count,
                    "extra_traffic": q2.validation.extra_traffic,
                    "changed_positions": None,
                    "reuse_edges": None,
                    "critical_path_nodes": None,
                    "address_seconds": round(address_seconds, 6),
                    "schedule_seconds": round(time.perf_counter() - t1, 6),
                    "valid": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    csv_path = args.out_dir / "q3_pipeline_critical.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.out_dir / "q3_pipeline_critical.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(csv_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
