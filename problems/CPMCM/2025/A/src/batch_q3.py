from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from parser import load_case
from q2_allocator import allocate_q2_baseline
from q2_optimized import schedule_q2_optimized
from q3_evaluator import evaluate_q3_both

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)


def _write_official_outputs(case: str, out_dir: Path, solution) -> None:
    case_dir = out_dir / case
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / f"{case}_schedule.txt").write_text(
        "".join(f"{node_id}\n" for node_id in solution.schedule), encoding="utf-8"
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
    ap = argparse.ArgumentParser(description="Evaluate promoted Q2 solutions as Q3 timing baseline")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--case", choices=CASES, action="append", dest="cases")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    selected = tuple(args.cases) if args.cases else CASES
    rows: list[dict[str, object]] = []
    for case in selected:
        graph = load_case(args.data_dir, case)
        t0 = time.perf_counter()
        scheduled = schedule_q2_optimized(graph)
        q2 = allocate_q2_baseline(graph, scheduled.order)
        q2.validation.require_ok()
        q2_seconds = time.perf_counter() - t0

        t1 = time.perf_counter()
        timing = evaluate_q3_both(graph, q2.solution)
        timing.official_literal.require_ok()
        timing.residency_safe.require_ok()
        q3_seconds = time.perf_counter() - t1

        literal = timing.official_literal
        safe = timing.residency_safe
        _write_official_outputs(case, args.out_dir, q2.solution)

        row: dict[str, object] = {
            "case": case,
            "q1_peak": scheduled.evaluation.peak_residency,
            "spill_count": q2.validation.spill_count,
            "extra_traffic": q2.validation.extra_traffic,
            "official_literal_cycles": literal.total_cycles,
            "residency_safe_cycles": safe.total_cycles,
            "safe_minus_literal": safe.total_cycles - literal.total_cycles,
            "literal_overlap_errors": len(literal.physical_overlap_errors),
            "safe_overlap_errors": len(safe.physical_overlap_errors),
            "official_reuse_edges": literal.reuse_edge_count,
            "safe_reuse_edges": safe.reuse_edge_count,
            "pipe_edges": safe.pipe_edge_count,
            "spill_edges": safe.spill_edge_count,
            "critical_path_nodes": len(safe.critical_path),
            "q2_build_seconds": round(q2_seconds, 6),
            "q3_eval_seconds": round(q3_seconds, 6),
        }
        for pipe in ("CUBE", "VECTOR", "MTE1", "MTE2", "MTE3", "FIXP"):
            row[f"{pipe.lower()}_busy"] = safe.pipe_busy_cycles.get(pipe, 0)
            row[f"{pipe.lower()}_util"] = round(safe.pipe_utilization.get(pipe, 0.0), 6)
        rows.append(row)

    fields = list(rows[0])
    csv_path = args.out_dir / "q3_baseline_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (args.out_dir / "q3_baseline_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(csv_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
