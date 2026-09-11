from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from parser import load_case
from q1_scheduler import schedule_q1_baseline
from q2_allocator import allocate_q2_baseline
from q2_promoted import EXPECTED_Q2_PROMOTED, solve_q2_promoted
from q2_validator import validate_q2_solution

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)
STRATEGIES = ("baseline", "optimized")

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


def _assert_optimized_regression(case: str, scheduled, replay) -> None:
    expected = EXPECTED_Q2_PROMOTED[case]
    actual = (
        scheduled.evaluation.peak_residency,
        replay.spill_count,
        replay.extra_traffic,
    )
    target = (expected.q1_peak, expected.spill_count, expected.extra_traffic)
    if actual != target:
        raise AssertionError(
            f"{case}: optimized regression expected peak/spills/traffic={target}, got {actual}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate strict Q2 solutions on official cases")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--case", choices=CASES, action="append", dest="cases")
    ap.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default="baseline",
        help=(
            "baseline keeps the Q1 order; optimized uses the promoted footprint "
            "scheduler plus a strict window-0..3 Q2 polish portfolio"
        ),
    )
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

        schedule_start = time.perf_counter()
        if args.strategy == "baseline":
            scheduled = schedule_q1_baseline(graph)
            schedule_seconds = time.perf_counter() - schedule_start

            q2_start = time.perf_counter()
            q2 = allocate_q2_baseline(graph, scheduled.order)
            q2_seconds = time.perf_counter() - q2_start
            polish_window = 0
            changed_positions = 0
        else:
            scheduled = solve_q2_promoted(graph)
            schedule_seconds = time.perf_counter() - schedule_start
            # The promoted solver already allocated and strictly replayed every
            # portfolio candidate; reuse the chosen allocation rather than paying
            # for a fifth allocation of the same winner.
            q2 = scheduled.allocation
            q2_seconds = 0.0
            polish_window = scheduled.polish_window
            changed_positions = scheduled.changed_positions

        # A second explicit replay here is intentional: batch acceptance must not
        # rely only on the allocator's internal postcondition call.
        replay = validate_q2_solution(graph, q2.solution)
        replay.require_ok()
        if replay.extra_traffic != q2.validation.extra_traffic:
            raise AssertionError(f"{case}: Q2 traffic mismatch between validation passes")
        if replay.spill_count != q2.validation.spill_count:
            raise AssertionError(f"{case}: Q2 spill-count mismatch between validation passes")

        if args.strategy == "optimized":
            _assert_optimized_regression(case, scheduled, replay)

        _write_official_outputs(case, args.out_dir, q2.solution)
        rows.append(
            {
                "case": case,
                "strategy": args.strategy,
                "nodes": graph.node_count,
                "edges": graph.edge_count,
                "q1_peak": scheduled.evaluation.peak_residency,
                "spill_count": replay.spill_count,
                "extra_traffic": replay.extra_traffic,
                "final_schedule_nodes": len(q2.solution.schedule),
                "affinity_decisions": getattr(scheduled, "affinity_decisions", 0),
                "footprint_decisions": getattr(scheduled, "footprint_decisions", 0),
                "polish_window": polish_window,
                "changed_positions": changed_positions,
                "q1_seconds": round(schedule_seconds, 6),
                "q2_seconds": round(q2_seconds, 6),
                "valid": replay.ok,
            }
        )

    fields = [
        "case",
        "strategy",
        "nodes",
        "edges",
        "q1_peak",
        "spill_count",
        "extra_traffic",
        "final_schedule_nodes",
        "affinity_decisions",
        "footprint_decisions",
        "polish_window",
        "changed_positions",
        "q1_seconds",
        "q2_seconds",
        "valid",
    ]
    stem = f"q2_{args.strategy}_summary"
    csv_path = args.out_dir / f"{stem}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (args.out_dir / f"{stem}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(csv_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
