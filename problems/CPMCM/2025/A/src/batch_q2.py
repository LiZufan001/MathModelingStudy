from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from parser import load_case
from q1_scheduler import schedule_q1_baseline
from q2_allocator import allocate_q2_baseline
from q2_validator import validate_q2_solution

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)

EXPECTED = {
    "Matmul_Case0": (4160, 7104),
    "Matmul_Case1": (30976, 55040),
    "FlashAttention_Case0": (1716, 2712),
    "FlashAttention_Case1": (6952, 11184),
    "Conv_Case0": (2580, 3869),
    "Conv_Case1": (36086, 85653),
}


def _write_official_outputs(case: str, out_dir: Path, solution) -> None:
    case_dir = out_dir / case
    case_dir.mkdir(parents=True, exist_ok=True)

    (case_dir / f"{case}_schedule.txt").write_text(
        "".join(f"{node_id}\n" for node_id in solution.schedule),
        encoding="utf-8",
    )
    (case_dir / f"{case}_memory.txt").write_text(
        "".join(
            f"{buf_id}:{solution.initial_offsets[buf_id]}\n"
            for buf_id in sorted(solution.initial_offsets)
        ),
        encoding="utf-8",
    )
    (case_dir / f"{case}_spill.txt").write_text(
        "".join(f"{spill.buf_id}:{spill.new_offset}\n" for spill in solution.spills),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Run strict Q2 baseline on all official cases")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--case", choices=CASES, action="append", dest="cases")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    selected = tuple(args.cases) if args.cases else CASES
    rows: list[dict[str, object]] = []

    for case in selected:
        graph = load_case(args.data_dir, case)
        expected_nodes, expected_edges = EXPECTED[case]
        if (graph.node_count, graph.edge_count) != (expected_nodes, expected_edges):
            raise ValueError(
                f"{case}: expected {(expected_nodes, expected_edges)}, got "
                f"{(graph.node_count, graph.edge_count)}"
            )

        q1_start = time.perf_counter()
        q1 = schedule_q1_baseline(graph)
        q1_seconds = time.perf_counter() - q1_start

        q2_start = time.perf_counter()
        q2 = allocate_q2_baseline(graph, q1.order)
        q2_seconds = time.perf_counter() - q2_start

        # A second explicit replay here is intentional: batch acceptance must not
        # rely only on the allocator's internal postcondition call.
        replay = validate_q2_solution(graph, q2.solution)
        replay.require_ok()
        if replay.extra_traffic != q2.validation.extra_traffic:
            raise AssertionError(f"{case}: Q2 traffic mismatch between validation passes")

        _write_official_outputs(case, args.out_dir, q2.solution)
        rows.append(
            {
                "case": case,
                "nodes": graph.node_count,
                "edges": graph.edge_count,
                "q1_peak": q1.evaluation.peak_residency,
                "spill_count": replay.spill_count,
                "extra_traffic": replay.extra_traffic,
                "final_schedule_nodes": len(q2.solution.schedule),
                "q1_seconds": round(q1_seconds, 6),
                "q2_seconds": round(q2_seconds, 6),
                "valid": replay.ok,
            }
        )

    fields = [
        "case",
        "nodes",
        "edges",
        "q1_peak",
        "spill_count",
        "extra_traffic",
        "final_schedule_nodes",
        "q1_seconds",
        "q2_seconds",
        "valid",
    ]
    csv_path = args.out_dir / "q2_baseline_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (args.out_dir / "q2_baseline_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(csv_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
