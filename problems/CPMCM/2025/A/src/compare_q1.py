from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from parser import load_case
from q1_advanced import schedule_q1_pressure
from q1_frontier import schedule_q1_frontier
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
    ap = argparse.ArgumentParser(description="Compare deterministic Q1 greedy policies")
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

        results = {
            "q1_baseline": schedule_q1_baseline(graph),
            "q1_pressure": schedule_q1_pressure(graph),
            "q1_frontier": schedule_q1_frontier(graph),
        }
        peaks: dict[str, int] = {}
        for method, result in results.items():
            peak = result.evaluation.peak_residency
            if not result.evaluation.valid or peak is None:
                raise SystemExit(f"{case}: {method} did not produce a valid Q1 evaluation")
            peaks[method] = peak
            _write_schedule(args.out_dir / f"{case}_{method}_schedule.csv", result.order)

        best_method = min(peaks, key=lambda method: (peaks[method], method))
        best_peak = peaks[best_method]
        baseline_peak = peaks["q1_baseline"]
        _write_schedule(
            args.out_dir / f"{case}_q1_best_greedy_schedule.csv",
            results[best_method].order,
        )

        rows.append(
            {
                "case": case,
                "nodes": graph.node_count,
                "edges": graph.edge_count,
                "baseline_peak": baseline_peak,
                "pressure_peak": peaks["q1_pressure"],
                "frontier_peak": peaks["q1_frontier"],
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
        "frontier_peak",
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
