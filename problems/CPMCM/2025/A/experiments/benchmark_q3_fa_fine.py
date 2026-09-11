from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from parser import load_case
from q2_allocator import allocate_q2_baseline
from q2_promoted import solve_q2_promoted
from q3_evaluator import evaluate_q3_solution
from q3_official_optimizer import optimize_q3_official_zero_traffic
from q3_tradeoff_scheduler import schedule_q3_critical_window

CASES = ("FlashAttention_Case0", "FlashAttention_Case1")
WINDOWS = tuple(range(17))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _nondominated(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    valid = [row for row in rows if row["valid"]]
    frontier: list[dict[str, object]] = []
    for row in sorted(
        valid,
        key=lambda item: (
            int(item["extra_traffic"]),
            int(item["optimized_official_cycles"]),
            int(item["window"]),
        ),
    ):
        dominated = any(
            int(other["extra_traffic"]) <= int(row["extra_traffic"])
            and int(other["optimized_official_cycles"])
            <= int(row["optimized_official_cycles"])
            and (
                int(other["extra_traffic"]) < int(row["extra_traffic"])
                or int(other["optimized_official_cycles"]) < int(row["optimized_official_cycles"])
            )
            for other in valid
            if other is not row
        )
        if not dominated:
            frontier.append(row)
    return frontier


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Fine-grained FlashAttention Q3 trade-off search from the promoted Q2 baseline: "
            "window=0..16, strict Q2 replay, residency-safe feasibility, official-cycle optimization"
        )
    )
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--rounds", type=int, default=2)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, object]] = []
    frontier_rows: list[dict[str, object]] = []
    summary: dict[str, object] = {}

    for case in CASES:
        graph = load_case(args.data_dir, case)
        promoted = solve_q2_promoted(graph)
        base_q2 = promoted.allocation
        base_q2.validation.require_ok()
        base_traffic = base_q2.validation.extra_traffic
        base_official_raw = evaluate_q3_solution(
            graph, base_q2.solution, reuse_mode="official_literal"
        )
        base_official_raw.require_ok()

        case_rows: list[dict[str, object]] = []
        for window in WINDOWS:
            started = time.perf_counter()
            row: dict[str, object] = {
                "case": case,
                "promoted_q2_polish_window": promoted.polish_window,
                "window": window,
                "changed_positions": None,
                "q1_peak": None,
                "spill_count": None,
                "extra_traffic": None,
                "traffic_delta": None,
                "traffic_delta_pct": None,
                "raw_safe_cycles": None,
                "raw_official_cycles": None,
                "optimized_safe_cycles": None,
                "optimized_official_cycles": None,
                "official_improvement_vs_window0_pct": None,
                "improvement_per_traffic_pct": None,
                "accepted_zero_traffic_steps": None,
                "seconds": None,
                "valid": False,
                "error": "",
            }
            try:
                if window == 0:
                    evaluation = promoted.evaluation
                    changed = 0
                    q2 = base_q2
                else:
                    scheduled = schedule_q3_critical_window(
                        graph,
                        promoted.order,
                        window=window,
                    )
                    evaluation = scheduled.evaluation
                    changed = scheduled.changed_positions
                    q2 = allocate_q2_baseline(graph, scheduled.order)
                    q2.validation.require_ok()

                row["changed_positions"] = changed
                row["q1_peak"] = evaluation.peak_residency
                row["spill_count"] = q2.validation.spill_count
                row["extra_traffic"] = q2.validation.extra_traffic
                traffic_delta = q2.validation.extra_traffic - base_traffic
                traffic_delta_pct = 100.0 * traffic_delta / base_traffic
                row["traffic_delta"] = traffic_delta
                row["traffic_delta_pct"] = round(traffic_delta_pct, 6)

                raw_safe = evaluate_q3_solution(
                    graph, q2.solution, reuse_mode="residency_safe"
                )
                raw_safe.require_ok()
                raw_official = evaluate_q3_solution(
                    graph, q2.solution, reuse_mode="official_literal"
                )
                raw_official.require_ok()
                row["raw_safe_cycles"] = raw_safe.total_cycles
                row["raw_official_cycles"] = raw_official.total_cycles

                optimized = optimize_q3_official_zero_traffic(
                    graph, q2.solution, max_rounds=args.rounds
                )
                optimized.safe_timing.require_ok()
                optimized.official_timing.require_ok()
                row["optimized_safe_cycles"] = optimized.safe_timing.total_cycles
                row["optimized_official_cycles"] = optimized.official_timing.total_cycles
                row["accepted_zero_traffic_steps"] = sum(
                    1 for step in optimized.steps if step.accepted
                )
                row["valid"] = True
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            row["seconds"] = round(time.perf_counter() - started, 6)
            case_rows.append(row)
            all_rows.append(row)

        zero = next(
            (row for row in case_rows if row["window"] == 0 and row["valid"]),
            None,
        )
        if zero is None:
            raise RuntimeError(f"{case}: window=0 promoted baseline did not survive")
        zero_cycles = int(zero["optimized_official_cycles"])

        for row in case_rows:
            if not row["valid"]:
                continue
            cycles = int(row["optimized_official_cycles"])
            improvement = 100.0 * (zero_cycles - cycles) / zero_cycles
            row["official_improvement_vs_window0_pct"] = round(improvement, 6)
            traffic_pct = float(row["traffic_delta_pct"])
            if traffic_pct > 0 and improvement > 0:
                row["improvement_per_traffic_pct"] = round(improvement / traffic_pct, 6)

        frontier = _nondominated(case_rows)
        frontier_rows.extend(dict(row) for row in frontier)

        improved = [
            row
            for row in frontier
            if int(row["optimized_official_cycles"]) < zero_cycles
            and int(row["extra_traffic"]) >= base_traffic
        ]
        first_improvement = min(
            improved,
            key=lambda row: (
                int(row["extra_traffic"]),
                int(row["optimized_official_cycles"]),
                int(row["window"]),
            ),
            default=None,
        )
        best_efficiency = max(
            (row for row in improved if row["improvement_per_traffic_pct"] is not None),
            key=lambda row: (
                float(row["improvement_per_traffic_pct"]),
                -int(row["extra_traffic"]),
            ),
            default=None,
        )
        best_cycles = min(
            (row for row in case_rows if row["valid"]),
            key=lambda row: (
                int(row["optimized_official_cycles"]),
                int(row["extra_traffic"]),
                int(row["window"]),
            ),
        )
        summary[case] = {
            "promoted_q2_polish_window": promoted.polish_window,
            "base_q2_traffic": base_traffic,
            "base_q2_official_cycles": base_official_raw.total_cycles,
            "window0_official_optimized_cycles": zero_cycles,
            "first_improvement": None
            if first_improvement is None
            else {
                "window": first_improvement["window"],
                "extra_traffic": first_improvement["extra_traffic"],
                "traffic_delta_pct": first_improvement["traffic_delta_pct"],
                "official_cycles": first_improvement["optimized_official_cycles"],
                "official_improvement_pct": first_improvement[
                    "official_improvement_vs_window0_pct"
                ],
            },
            "best_efficiency": None
            if best_efficiency is None
            else {
                "window": best_efficiency["window"],
                "traffic_delta_pct": best_efficiency["traffic_delta_pct"],
                "official_improvement_pct": best_efficiency[
                    "official_improvement_vs_window0_pct"
                ],
                "improvement_per_traffic_pct": best_efficiency[
                    "improvement_per_traffic_pct"
                ],
            },
            "best_cycles": {
                "window": best_cycles["window"],
                "extra_traffic": best_cycles["extra_traffic"],
                "traffic_delta_pct": best_cycles["traffic_delta_pct"],
                "official_cycles": best_cycles["optimized_official_cycles"],
                "official_improvement_pct": best_cycles[
                    "official_improvement_vs_window0_pct"
                ],
            },
            "frontier_windows": [row["window"] for row in frontier],
        }

    _write_csv(args.out_dir / "fa_fine_candidates.csv", all_rows)
    _write_csv(args.out_dir / "fa_fine_frontier.csv", frontier_rows)
    (args.out_dir / "fa_fine_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print((args.out_dir / "fa_fine_frontier.csv").read_text(encoding="utf-8"))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
