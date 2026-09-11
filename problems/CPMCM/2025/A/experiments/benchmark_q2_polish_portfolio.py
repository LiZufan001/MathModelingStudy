from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from parser import load_case
from q2_allocator import allocate_q2_baseline
from q2_optimized import schedule_q2_optimized
from q3_tradeoff_scheduler import schedule_q3_critical_window

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)
WINDOWS = (0, 1, 2, 3)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Strict six-case Q2 polish portfolio")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    winners: list[dict[str, object]] = []
    detail: dict[str, object] = {}

    for case in CASES:
        graph = load_case(args.data_dir, case)
        promoted = schedule_q2_optimized(graph)
        base_q2 = allocate_q2_baseline(graph, promoted.order)
        base_q2.validation.require_ok()
        baseline_peak = promoted.evaluation.peak_residency
        case_rows: list[dict[str, object]] = []

        for window in WINDOWS:
            row: dict[str, object] = {
                "case": case,
                "window": window,
                "changed_positions": None,
                "q1_peak": None,
                "spill_count": None,
                "extra_traffic": None,
                "traffic_delta": None,
                "peak_gate": False,
                "valid": False,
                "error": "",
            }
            try:
                scheduled = schedule_q3_critical_window(graph, promoted.order, window=window)
                row["changed_positions"] = scheduled.changed_positions
                row["q1_peak"] = scheduled.evaluation.peak_residency
                row["peak_gate"] = scheduled.evaluation.peak_residency <= baseline_peak
                if not row["peak_gate"]:
                    raise ValueError(
                        f"Q1 peak regressed: {scheduled.evaluation.peak_residency} > {baseline_peak}"
                    )
                q2 = allocate_q2_baseline(graph, scheduled.order)
                q2.validation.require_ok()
                row["spill_count"] = q2.validation.spill_count
                row["extra_traffic"] = q2.validation.extra_traffic
                row["traffic_delta"] = q2.validation.extra_traffic - base_q2.validation.extra_traffic
                row["valid"] = True
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            case_rows.append(row)
            rows.append(row)

        valid = [row for row in case_rows if row["valid"]]
        if not valid:
            raise RuntimeError(f"{case}: no Q2 polish candidate survived")
        winner = min(
            valid,
            key=lambda row: (
                int(row["extra_traffic"]),
                int(row["spill_count"]),
                int(row["q1_peak"]),
                int(row["changed_positions"]),
                int(row["window"]),
            ),
        )
        winners.append(dict(winner))
        detail[case] = {
            "baseline_peak": baseline_peak,
            "baseline_spill_count": base_q2.validation.spill_count,
            "baseline_extra_traffic": base_q2.validation.extra_traffic,
            "winner": dict(winner),
        }

    _write_csv(args.out_dir / "q2_polish_candidates.csv", rows)
    _write_csv(args.out_dir / "q2_polish_winners.csv", winners)
    (args.out_dir / "q2_polish_summary.json").write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print((args.out_dir / "q2_polish_winners.csv").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
