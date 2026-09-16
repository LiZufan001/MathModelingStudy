from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from evaluator import evaluate_q1
from parser import load_case

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)


def read_schedule(path: Path) -> list[int]:
    order: list[int] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        text = raw.strip()
        if not text:
            continue
        try:
            order.append(int(text))
        except ValueError as exc:
            raise ValueError(f"{path}:{line_no}: expected integer NodeId, got {text!r}") from exc
    return order


def main() -> int:
    ap = argparse.ArgumentParser(description="Strictly re-evaluate external Q1 schedule files")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--schedule-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    rows: list[dict[str, object]] = []
    for case in CASES:
        graph = load_case(args.data_dir, case)
        path = args.schedule_dir / f"{case}_schedule.txt"
        if not path.exists():
            rows.append(
                {
                    "case": case,
                    "present": False,
                    "valid": False,
                    "peak_residency": None,
                    "schedule_length": None,
                    "errors": "missing schedule file",
                }
            )
            continue

        try:
            order = read_schedule(path)
            evaluation = evaluate_q1(graph, order)
            rows.append(
                {
                    "case": case,
                    "present": True,
                    "valid": evaluation.valid,
                    "peak_residency": evaluation.peak_residency,
                    "schedule_length": len(order),
                    "errors": " | ".join(evaluation.errors[:8]),
                }
            )
        except Exception as exc:  # report malformed third-party inputs without hiding the case
            rows.append(
                {
                    "case": case,
                    "present": True,
                    "valid": False,
                    "peak_residency": None,
                    "schedule_length": None,
                    "errors": f"{type(exc).__name__}: {exc}",
                }
            )

    fields = ["case", "present", "valid", "peak_residency", "schedule_length", "errors"]
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        args.out.with_suffix(".json").write_text(
            json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    writer = csv.DictWriter(__import__("sys").stdout, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
