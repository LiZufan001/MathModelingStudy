from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from evaluator import evaluate_q1
from parser import load_case
from q1_scheduler import schedule_q1_baseline


def run_case(data_dir: Path, case: str, out_dir: Path) -> dict[str, object]:
    graph = load_case(data_dir, case)
    result = schedule_q1_baseline(graph)
    out_dir.mkdir(parents=True, exist_ok=True)

    schedule_path = out_dir / f"{case}_q1_baseline_schedule.csv"
    with schedule_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Position", "NodeId"])
        writer.writerows(enumerate(result.order))

    original_order = sorted(graph.nodes)
    original_eval = evaluate_q1(graph, original_order)
    original_peak = original_eval.peak_residency if original_eval.valid else None
    improvement = None
    if original_peak is not None and result.evaluation.peak_residency is not None:
        improvement = original_peak - result.evaluation.peak_residency

    summary: dict[str, object] = {
        "case": case,
        "method": "q1_baseline",
        "nodes": graph.node_count,
        "edges": graph.edge_count,
        "valid": result.evaluation.valid,
        "peak_residency": result.evaluation.peak_residency,
        "peak_position": result.evaluation.peak_position,
        "original_order_valid": original_eval.valid,
        "original_peak_residency": original_peak,
        "absolute_peak_reduction": improvement,
        "schedule_file": str(schedule_path),
    }
    summary_path = out_dir / f"{case}_q1_baseline_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="2025 CPMCM A scheduling experiments")
    ap.add_argument("--data-dir", type=Path, required=True, help="directory containing *_Nodes.csv and *_Edges.csv")
    ap.add_argument("--case", required=True, help="case name, e.g. Matmul_Case0")
    ap.add_argument("--method", choices=["q1_baseline"], default="q1_baseline")
    ap.add_argument("--out-dir", type=Path, default=Path("results"))
    args = ap.parse_args()
    summary = run_case(args.data_dir, args.case, args.out_dir)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
