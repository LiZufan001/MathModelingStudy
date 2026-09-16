from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from parser import load_case
from q1_advanced import schedule_q1_pressure
from q1_frontier import schedule_q1_frontier
from q1_lookahead import schedule_q1_lookahead
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


def _timed(fn):
    start = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - start


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare deterministic Q1 policies")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--lookahead-depth", type=int, default=2)
    ap.add_argument("--lookahead-candidates", type=int, default=6)
    ap.add_argument("--lookahead-horizon", type=int, default=96)
    ap.add_argument("--lookahead-trigger-ratio", type=float, default=0.5)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for case, expected in EXPECTED.items():
        graph = load_case(args.data_dir, case)
        if (graph.node_count, graph.edge_count) != expected:
            raise SystemExit(
                f"{case}: expected nodes/edges {expected}, got {(graph.node_count, graph.edge_count)}"
            )

        baseline, baseline_seconds = _timed(lambda: schedule_q1_baseline(graph))
        pressure, pressure_seconds = _timed(lambda: schedule_q1_pressure(graph))
        frontier, frontier_seconds = _timed(lambda: schedule_q1_frontier(graph))
        lookahead, lookahead_seconds = _timed(
            lambda: schedule_q1_lookahead(
                graph,
                depth=args.lookahead_depth,
                candidate_limit=args.lookahead_candidates,
                rollout_horizon=args.lookahead_horizon,
                trigger_ratio=args.lookahead_trigger_ratio,
            )
        )

        results = {
            "q1_baseline": baseline,
            "q1_pressure": pressure,
            "q1_frontier": frontier,
            "q1_lookahead": lookahead,
        }
        runtimes = {
            "q1_baseline": baseline_seconds,
            "q1_pressure": pressure_seconds,
            "q1_frontier": frontier_seconds,
            "q1_lookahead": lookahead_seconds,
        }
        peaks: dict[str, int] = {}
        for method, result in results.items():
            peak = result.evaluation.peak_residency
            if not result.evaluation.valid or peak is None:
                raise SystemExit(f"{case}: {method} did not produce a valid Q1 evaluation")
            peaks[method] = peak
            _write_schedule(args.out_dir / f"{case}_{method}_schedule.csv", result.order)

        best_method = min(peaks, key=lambda method: (peaks[method], runtimes[method], method))
        best_peak = peaks[best_method]
        baseline_peak = peaks["q1_baseline"]
        _write_schedule(
            args.out_dir / f"{case}_q1_best_schedule.csv",
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
                "lookahead_peak": peaks["q1_lookahead"],
                "best_peak": best_peak,
                "best_method": best_method,
                "absolute_reduction_vs_baseline": baseline_peak - best_peak,
                "relative_reduction_vs_baseline": (baseline_peak - best_peak) / baseline_peak if baseline_peak else 0.0,
                "baseline_seconds": round(baseline_seconds, 6),
                "pressure_seconds": round(pressure_seconds, 6),
                "frontier_seconds": round(frontier_seconds, 6),
                "lookahead_seconds": round(lookahead_seconds, 6),
                "lookahead_decisions": lookahead.lookahead_decisions,
                "lookahead_baseline_upper": lookahead.baseline_upper_bound,
            }
        )

    csv_path = args.out_dir / "q1_policy_comparison.csv"
    fields = [
        "case",
        "nodes",
        "edges",
        "baseline_peak",
        "pressure_peak",
        "frontier_peak",
        "lookahead_peak",
        "best_peak",
        "best_method",
        "absolute_reduction_vs_baseline",
        "relative_reduction_vs_baseline",
        "baseline_seconds",
        "pressure_seconds",
        "frontier_seconds",
        "lookahead_seconds",
        "lookahead_decisions",
        "lookahead_baseline_upper",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    (args.out_dir / "q1_policy_comparison.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(csv_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
