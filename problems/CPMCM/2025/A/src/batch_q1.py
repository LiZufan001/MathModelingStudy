from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from experiment import run_case

EXPECTED = {
    "Matmul_Case0": (4160, 7104),
    "Matmul_Case1": (30976, 55040),
    "FlashAttention_Case0": (1716, 2712),
    "FlashAttention_Case1": (6952, 11184),
    "Conv_Case0": (2580, 3869),
    "Conv_Case1": (36086, 85653),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Q1 baseline on all six official appendix-E cases")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, object]] = []
    for case, expected in EXPECTED.items():
        summary = run_case(args.data_dir, case, args.out_dir)
        got = (summary["nodes"], summary["edges"])
        if got != expected:
            raise SystemExit(f"{case}: expected nodes/edges {expected}, got {got}")
        if not summary["valid"]:
            raise SystemExit(f"{case}: scheduler/evaluator did not produce a valid schedule")
        summaries.append(summary)

    csv_path = args.out_dir / "q1_baseline_summary.csv"
    fields = [
        "case", "nodes", "edges", "valid", "peak_residency", "peak_position",
        "original_order_valid", "original_peak_residency", "absolute_peak_reduction",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summaries)

    (args.out_dir / "q1_baseline_summary.json").write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(csv_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
