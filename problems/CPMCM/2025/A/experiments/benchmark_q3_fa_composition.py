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
PAIR_WINDOWS = (1, 2, 3, 4, 5)
SINGLE_WINDOWS = (0, 1, 3)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _frontier(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    valid = [row for row in rows if row["valid"]]
    out: list[dict[str, object]] = []
    for row in sorted(
        valid,
        key=lambda r: (
            int(r["extra_traffic"]),
            int(r["optimized_official_cycles"]),
            str(r["sequence"]),
        ),
    ):
        dominated = any(
            int(other["extra_traffic"]) <= int(row["extra_traffic"])
            and int(other["optimized_official_cycles"]) <= int(row["optimized_official_cycles"])
            and (
                int(other["extra_traffic"]) < int(row["extra_traffic"])
                or int(other["optimized_official_cycles"]) < int(row["optimized_official_cycles"])
            )
            for other in valid
            if other is not row
        )
        if not dominated:
            out.append(row)
    return out


def _sequence_specs() -> tuple[tuple[int, ...], ...]:
    singles = tuple((w,) for w in SINGLE_WINDOWS)
    pairs = tuple((a, b) for a in PAIR_WINDOWS for b in PAIR_WINDOWS)
    return singles + pairs


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "FlashAttention two-stage critical-window composition search: "
            "strict Q2 replay, residency-safe gate, official-cycle post-optimization"
        )
    )
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--rounds", type=int, default=2)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    frontier_rows: list[dict[str, object]] = []
    summary: dict[str, object] = {}

    for case in CASES:
        graph = load_case(args.data_dir, case)
        promoted = solve_q2_promoted(graph)
        promoted.validation.require_ok()
        base_traffic = promoted.validation.extra_traffic
        base_safe = evaluate_q3_solution(graph, promoted.solution, reuse_mode="residency_safe")
        base_safe.require_ok()
        base_official = evaluate_q3_solution(graph, promoted.solution, reuse_mode="official_literal")
        base_official.require_ok()

        case_rows: list[dict[str, object]] = []
        for sequence in _sequence_specs():
            started = time.perf_counter()
            label = ">".join(str(w) for w in sequence)
            row: dict[str, object] = {
                "case": case,
                "promoted_q2_polish_window": promoted.polish_window,
                "sequence": label,
                "stages": len(sequence),
                "stage1_window": sequence[0],
                "stage2_window": sequence[1] if len(sequence) > 1 else None,
                "q1_peak": None,
                "changed_vs_promoted": None,
                "spill_count": None,
                "extra_traffic": None,
                "traffic_delta": None,
                "traffic_delta_pct": None,
                "raw_safe_cycles": None,
                "raw_official_cycles": None,
                "optimized_safe_cycles": None,
                "optimized_official_cycles": None,
                "official_improvement_pct": None,
                "accepted_zero_traffic_steps": None,
                "dominates_promoted_q2_traffic": False,
                "seconds": None,
                "valid": False,
                "error": "",
            }
            try:
                if sequence == (0,):
                    order = promoted.order
                    evaluation = promoted.evaluation
                    q2 = promoted.allocation
                else:
                    order = promoted.order
                    evaluation = promoted.evaluation
                    for window in sequence:
                        scheduled = schedule_q3_critical_window(graph, order, window=window)
                        order = scheduled.order
                        evaluation = scheduled.evaluation
                    q2 = allocate_q2_baseline(graph, order)
                    q2.validation.require_ok()

                changed = sum(
                    1 for i, node_id in enumerate(order)
                    if node_id != promoted.order[i]
                )
                traffic = q2.validation.extra_traffic
                row["q1_peak"] = evaluation.peak_residency
                row["changed_vs_promoted"] = changed
                row["spill_count"] = q2.validation.spill_count
                row["extra_traffic"] = traffic
                row["traffic_delta"] = traffic - base_traffic
                row["traffic_delta_pct"] = round(
                    100.0 * (traffic - base_traffic) / base_traffic,
                    6,
                )
                row["dominates_promoted_q2_traffic"] = traffic < base_traffic

                raw_safe = evaluate_q3_solution(graph, q2.solution, reuse_mode="residency_safe")
                raw_safe.require_ok()
                raw_official = evaluate_q3_solution(graph, q2.solution, reuse_mode="official_literal")
                raw_official.require_ok()
                row["raw_safe_cycles"] = raw_safe.total_cycles
                row["raw_official_cycles"] = raw_official.total_cycles

                optimized = optimize_q3_official_zero_traffic(
                    graph,
                    q2.solution,
                    max_rounds=args.rounds,
                )
                optimized.safe_timing.require_ok()
                optimized.official_timing.require_ok()
                row["optimized_safe_cycles"] = optimized.safe_timing.total_cycles
                row["optimized_official_cycles"] = optimized.official_timing.total_cycles
                row["official_improvement_pct"] = round(
                    100.0
                    * (base_official.total_cycles - optimized.official_timing.total_cycles)
                    / base_official.total_cycles,
                    6,
                )
                row["accepted_zero_traffic_steps"] = sum(
                    1 for step in optimized.steps if step.accepted
                )
                row["valid"] = True
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            row["seconds"] = round(time.perf_counter() - started, 6)
            case_rows.append(row)
            rows.append(row)

        frontier = _frontier(case_rows)
        frontier_rows.extend(dict(row) for row in frontier)
        best_traffic = min(
            (r for r in case_rows if r["valid"]),
            key=lambda r: (int(r["extra_traffic"]), int(r["optimized_official_cycles"]), str(r["sequence"])),
        )
        best_cycles = min(
            (r for r in case_rows if r["valid"]),
            key=lambda r: (int(r["optimized_official_cycles"]), int(r["extra_traffic"]), str(r["sequence"])),
        )
        below_base = [r for r in case_rows if r["valid"] and int(r["extra_traffic"]) < base_traffic]
        summary[case] = {
            "promoted_q2_polish_window": promoted.polish_window,
            "base_traffic": base_traffic,
            "base_safe_cycles": base_safe.total_cycles,
            "base_official_cycles": base_official.total_cycles,
            "candidate_count": len(case_rows),
            "valid_count": sum(1 for r in case_rows if r["valid"]),
            "frontier_sequences": [r["sequence"] for r in frontier],
            "best_traffic": {
                "sequence": best_traffic["sequence"],
                "extra_traffic": best_traffic["extra_traffic"],
                "official_cycles": best_traffic["optimized_official_cycles"],
            },
            "best_cycles": {
                "sequence": best_cycles["sequence"],
                "extra_traffic": best_cycles["extra_traffic"],
                "traffic_delta_pct": best_cycles["traffic_delta_pct"],
                "official_cycles": best_cycles["optimized_official_cycles"],
                "official_improvement_pct": best_cycles["official_improvement_pct"],
            },
            "q2_traffic_improvements": [
                {
                    "sequence": r["sequence"],
                    "extra_traffic": r["extra_traffic"],
                    "traffic_delta_pct": r["traffic_delta_pct"],
                    "official_cycles": r["optimized_official_cycles"],
                }
                for r in sorted(
                    below_base,
                    key=lambda r: (int(r["extra_traffic"]), int(r["optimized_official_cycles"])),
                )
            ],
        }

    _write_csv(args.out_dir / "fa_composition_candidates.csv", rows)
    _write_csv(args.out_dir / "fa_composition_frontier.csv", frontier_rows)
    (args.out_dir / "fa_composition_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print((args.out_dir / "fa_composition_frontier.csv").read_text(encoding="utf-8"))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
