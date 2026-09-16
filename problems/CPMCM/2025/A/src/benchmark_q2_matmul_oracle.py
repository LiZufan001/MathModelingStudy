from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from parser import load_case
from q1_scheduler import schedule_q1_baseline
from q2_unit_cache_oracle import solve_uniform_unit_cache_oracle

CASES = ("Matmul_Case0", "Matmul_Case1")


def main() -> int:
    ap = argparse.ArgumentParser(description="Exact uniform-page Q2 oracle for Matmul L1")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--baseline-summary", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    with args.baseline_summary.open("r", encoding="utf-8") as fh:
        baseline = {row["case"]: row for row in csv.DictReader(fh)}

    rows: list[dict[str, object]] = []
    for case in CASES:
        graph = load_case(args.data_dir, case)
        q1 = schedule_q1_baseline(graph)
        oracle = solve_uniform_unit_cache_oracle(
            graph,
            q1.order,
            memory_type="L1",
            capacity=4096,
        )
        strict_spills = int(baseline[case]["spill_count"])
        strict_traffic = int(baseline[case]["extra_traffic"])
        rows.append(
            {
                "case": case,
                "page_size": oracle.page_size,
                "slots": oracle.slots,
                "traffic_per_spill": oracle.traffic_per_spill,
                "belady_spill_count": oracle.spill_count,
                "belady_extra_traffic": oracle.extra_traffic,
                "strict_spill_count": strict_spills,
                "strict_extra_traffic": strict_traffic,
                "spill_gap": strict_spills - oracle.spill_count,
                "traffic_gap": strict_traffic - oracle.extra_traffic,
                "strict_matches_oracle": (
                    strict_spills == oracle.spill_count
                    and strict_traffic == oracle.extra_traffic
                ),
            }
        )

    fields = list(rows[0])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    args.out.with_suffix(".json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.out.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
