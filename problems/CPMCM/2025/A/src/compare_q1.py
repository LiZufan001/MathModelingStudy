from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from parser import load_case
from q1_advanced import schedule_q1_pressure
from q1_scheduler import schedule_q1_baseline

EXPECTED = {
    "Matmul_Case0": (4160, 7104),
    "Matmul_Case1": (30976, 55040),
    "FlashAttention_Case0": (1716, 2712),
    "FlashAttention_Case1": (6952, 11184),
    "Conv_Case0": (2580, 3869),
    "Conv_Case1": (36086, 85653),
}


def _write_schedule(path: Path, order: tuple[int, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Position", "NodeId"])
        writer.writerows(enumerate(order))


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare deterministic Q1 baseline and pressure heuristic")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for case, expected in EXPECTED.items():
        graph = load_case(args.data_dir, case)
        if (graph.node_count, graph.edge_count) != expected:
            raise SystemExit(
                f"{case}: expected nodes/edges {expected}, got {(graph.node_count, graph.edge_count)}"
            )

        baseline = schedule_q1_baseline(graph)
        pressure = schedule_q1_pressure(graph)
        baseline_peak = baseline.evaluation.peak_residency
        pressure_peak = pressure.evaluation.peak_residency
        if baseline_peak is None or pressure_peak is None:
            raise SystemExit(f"{case}: missing Q1 peak from a supposedly valid schedule")

        if pressure_peak < baseline_peak:
            best_method = "q1_pressure"
            best_order = pressure.order
            best_peak = pressure_peak
        else:
            best_method = "q1_baseline"
            best_order = baseline.order
            best_peak = baseline_peak

        _write_schedule(args.out_dir / f"{case}_q1_pressure_schedule.csv", pressure.order)
        _write_schedule(args.out_dir / f"{case}_q1_best_greedy_schedule.csv", best_order)

        rows.append(
            {
                "case": case,
                "nodes": graph.node_count,
                "edges": graph.edge_count,
                "baseline_peak": baseline_peak,
                "pressure_peak": pressure_peak,
                "best_greedy_peak": best_peak,
                "best_method": best_method,
                "absolute_reduction_vs_baseline": baseline_peak - best_peak,
                "relative_reduction_vs_baseline": (baseline_peak - best_peak) / baseline_peak if baseline_peak else 0.0,
            }
        )

    csv_path = args.out_dir / "q1_greedy_comparison.csv"
    fields = [
        "case",
        "nodes",
        "edges",
        "baseline_peak",
        "pressure_peak",
        "best_greedy_peak",
        "best_method",
        "absolute_reduction_vs_baseline",
        "relative_reduction_vs_baseline",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    (args.out_dir / "q1_greedy_comparison.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(csv_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
