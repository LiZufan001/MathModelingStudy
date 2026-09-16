from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from parser import load_case
from q2_allocator import allocate_q2_baseline
from q2_promoted import solve_q2_promoted
from q3_evaluator import evaluate_q3_solution
from q3_official_optimizer import optimize_q3_official_zero_traffic
from q3_tradeoff_scheduler import schedule_q3_critical_window
from q3_zero_traffic_optimizer import optimize_q3_zero_traffic

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)
WINDOWS = (0, 8, 32, 128, 512)
EPSILON_BPS = (0, 100, 300, 500)  # 0%, 1%, 3%, 5%; experimental, not official thresholds.
BPS_DENOMINATOR = 10_000


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _within_budget(traffic: int, baseline: int, epsilon_bps: int) -> bool:
    return traffic * BPS_DENOMINATOR <= baseline * (BPS_DENOMINATOR + epsilon_bps)


def _winner(
    eligible: list[dict[str, object]],
    *,
    metric: str,
) -> dict[str, object]:
    if metric not in {"safe_variant_safe_cycles", "official_variant_official_cycles"}:
        raise ValueError(f"unsupported Pareto metric: {metric}")
    return min(
        eligible,
        key=lambda row: (
            int(row[metric]),
            int(row["extra_traffic"]),
            int(row["window"]),
        ),
    )


def _frontier_row(
    *,
    case: str,
    epsilon_bps: int,
    winner: dict[str, object],
    baseline_traffic: int,
    baseline_safe_cycles: int,
    baseline_official_cycles: int,
    objective: str,
) -> dict[str, object]:
    if objective == "residency_safe":
        safe_cycles = int(winner["safe_variant_safe_cycles"])
        official_cycles = int(winner["safe_variant_official_cycles"])
        accepted_steps = int(winner["safe_accepted_steps"])
    elif objective == "official_literal":
        safe_cycles = int(winner["official_variant_safe_cycles"])
        official_cycles = int(winner["official_variant_official_cycles"])
        accepted_steps = int(winner["official_accepted_steps"])
    else:
        raise ValueError(f"unsupported frontier objective {objective!r}")

    return {
        "case": case,
        "objective": objective,
        "epsilon_pct": epsilon_bps / 100.0,
        "window": winner["window"],
        "baseline_traffic": baseline_traffic,
        "extra_traffic": winner["extra_traffic"],
        "traffic_delta": winner["traffic_delta"],
        "traffic_ratio": winner["traffic_ratio"],
        "baseline_safe_cycles": baseline_safe_cycles,
        "safe_cycles": safe_cycles,
        "safe_improvement_pct": round(
            100.0 * (baseline_safe_cycles - safe_cycles) / baseline_safe_cycles,
            6,
        ),
        "baseline_official_literal_cycles": baseline_official_cycles,
        "official_literal_cycles": official_cycles,
        "official_improvement_pct": round(
            100.0 * (baseline_official_cycles - official_cycles) / baseline_official_cycles,
            6,
        ),
        "spill_count": winner["spill_count"],
        "changed_positions": winner["changed_positions"],
        "accepted_zero_traffic_steps": accepted_steps,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Build strict Q3 traffic/cycles Pareto candidates from the promoted Q2 baseline; "
            "safe and official frontiers use their own monotone post-optimizers"
        )
    )
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--rounds", type=int, default=2)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    candidate_rows: list[dict[str, object]] = []
    safe_frontier_rows: list[dict[str, object]] = []
    official_frontier_rows: list[dict[str, object]] = []
    traces: dict[str, dict[str, object]] = {}

    for case in CASES:
        graph = load_case(args.data_dir, case)
        promoted = solve_q2_promoted(graph)
        base_q2 = promoted.allocation
        base_q2.validation.require_ok()
        baseline_traffic = base_q2.validation.extra_traffic
        baseline_spills = base_q2.validation.spill_count
        baseline_safe = evaluate_q3_solution(graph, base_q2.solution, reuse_mode="residency_safe")
        baseline_safe.require_ok()
        baseline_literal = evaluate_q3_solution(graph, base_q2.solution, reuse_mode="official_literal")
        baseline_literal.require_ok()

        case_candidates: list[dict[str, object]] = []
        case_trace: dict[str, object] = {
            "promoted_q2_polish_window": promoted.polish_window,
            "baseline_traffic": baseline_traffic,
            "baseline_spills": baseline_spills,
            "baseline_safe_cycles": baseline_safe.total_cycles,
            "baseline_official_literal_cycles": baseline_literal.total_cycles,
            "windows": {},
        }

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
                "traffic_ratio": None,
                "within_5pct": False,
                "raw_safe_cycles": None,
                "raw_official_cycles": None,
                "safe_variant_safe_cycles": None,
                "safe_variant_official_cycles": None,
                "official_variant_safe_cycles": None,
                "official_variant_official_cycles": None,
                "safe_accepted_steps": None,
                "official_accepted_steps": None,
                "seconds": None,
                "valid": False,
                "error": "",
            }
            trace_entry: dict[str, object] = {}
            try:
                if window == 0:
                    order = promoted.order
                    evaluation = promoted.evaluation
                    changed = 0
                    q2 = base_q2
                else:
                    scheduled = schedule_q3_critical_window(
                        graph,
                        promoted.order,
                        window=window,
                    )
                    order = scheduled.order
                    evaluation = scheduled.evaluation
                    changed = scheduled.changed_positions
                    q2 = allocate_q2_baseline(graph, order)
                    q2.validation.require_ok()

                row["changed_positions"] = changed
                row["q1_peak"] = evaluation.peak_residency
                traffic = q2.validation.extra_traffic
                spills = q2.validation.spill_count
                row["spill_count"] = spills
                row["extra_traffic"] = traffic
                row["traffic_delta"] = traffic - baseline_traffic
                row["traffic_ratio"] = round(traffic / baseline_traffic, 8) if baseline_traffic else 1.0
                within_5 = _within_budget(traffic, baseline_traffic, max(EPSILON_BPS))
                row["within_5pct"] = within_5

                raw_safe = evaluate_q3_solution(graph, q2.solution, reuse_mode="residency_safe")
                raw_safe.require_ok()
                raw_official = evaluate_q3_solution(graph, q2.solution, reuse_mode="official_literal")
                raw_official.require_ok()
                row["raw_safe_cycles"] = raw_safe.total_cycles
                row["raw_official_cycles"] = raw_official.total_cycles

                if within_5:
                    safe_opt = optimize_q3_zero_traffic(
                        graph,
                        q2.solution,
                        max_rounds=args.rounds,
                    )
                    safe_official = evaluate_q3_solution(
                        graph,
                        safe_opt.solution,
                        reuse_mode="official_literal",
                    )
                    safe_official.require_ok()

                    official_opt = optimize_q3_official_zero_traffic(
                        graph,
                        q2.solution,
                        max_rounds=args.rounds,
                    )
                    official_opt.safe_timing.require_ok()
                    official_opt.official_timing.require_ok()

                    row["safe_variant_safe_cycles"] = safe_opt.timing.total_cycles
                    row["safe_variant_official_cycles"] = safe_official.total_cycles
                    row["official_variant_safe_cycles"] = official_opt.safe_timing.total_cycles
                    row["official_variant_official_cycles"] = official_opt.official_timing.total_cycles
                    row["safe_accepted_steps"] = sum(
                        1 for step in safe_opt.steps if step.accepted
                    )
                    row["official_accepted_steps"] = sum(
                        1 for step in official_opt.steps if step.accepted
                    )
                    row["valid"] = safe_opt.timing.ok and official_opt.safe_timing.ok

                    trace_entry["safe_zero_traffic_steps"] = [
                        {
                            "round": step.round_index,
                            "transformation": step.transformation,
                            "detail": step.detail,
                            "cycles_before": step.cycles_before,
                            "cycles_after": step.cycles_after,
                            "accepted": step.accepted,
                            "error": step.error,
                        }
                        for step in safe_opt.steps
                    ]
                    trace_entry["official_zero_traffic_steps"] = [
                        {
                            "round": step.round_index,
                            "transformation": step.transformation,
                            "detail": step.detail,
                            "official_before": step.official_before,
                            "official_after": step.official_after,
                            "safe_before": step.safe_before,
                            "safe_after": step.safe_after,
                            "accepted": step.accepted,
                            "error": step.error,
                        }
                        for step in official_opt.steps
                    ]
                else:
                    row["error"] = "strict-valid candidate exceeds the 5% experiment ceiling"
                    trace_entry["safe_zero_traffic_steps"] = []
                    trace_entry["official_zero_traffic_steps"] = []
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            row["seconds"] = round(time.perf_counter() - started, 6)
            case_candidates.append(row)
            candidate_rows.append(row)
            case_trace["windows"][str(window)] = trace_entry

        usable = [
            row
            for row in case_candidates
            if row["valid"]
            and row["safe_variant_safe_cycles"] is not None
            and row["official_variant_official_cycles"] is not None
        ]
        if not usable:
            raise RuntimeError(f"{case}: no strict Q3 Pareto candidate survived")

        for epsilon_bps in EPSILON_BPS:
            eligible = [
                row
                for row in usable
                if _within_budget(
                    int(row["extra_traffic"]),
                    baseline_traffic,
                    epsilon_bps,
                )
            ]
            if not eligible:
                raise RuntimeError(f"{case}: no candidate satisfies epsilon={epsilon_bps} bps")

            safe_winner = _winner(eligible, metric="safe_variant_safe_cycles")
            official_winner = _winner(eligible, metric="official_variant_official_cycles")
            safe_frontier_rows.append(
                _frontier_row(
                    case=case,
                    epsilon_bps=epsilon_bps,
                    winner=safe_winner,
                    baseline_traffic=baseline_traffic,
                    baseline_safe_cycles=baseline_safe.total_cycles,
                    baseline_official_cycles=baseline_literal.total_cycles,
                    objective="residency_safe",
                )
            )
            official_frontier_rows.append(
                _frontier_row(
                    case=case,
                    epsilon_bps=epsilon_bps,
                    winner=official_winner,
                    baseline_traffic=baseline_traffic,
                    baseline_safe_cycles=baseline_safe.total_cycles,
                    baseline_official_cycles=baseline_literal.total_cycles,
                    objective="official_literal",
                )
            )
        traces[case] = case_trace

    candidate_path = args.out_dir / "q3_pareto_candidates.csv"
    safe_frontier_path = args.out_dir / "q3_safe_frontier.csv"
    official_frontier_path = args.out_dir / "q3_official_frontier.csv"
    compatibility_path = args.out_dir / "q3_epsilon_frontier.csv"
    _write_csv(candidate_path, candidate_rows)
    _write_csv(safe_frontier_path, safe_frontier_rows)
    _write_csv(official_frontier_path, official_frontier_rows)
    _write_csv(compatibility_path, safe_frontier_rows)
    (args.out_dir / "q3_pareto_candidates.json").write_text(
        json.dumps(candidate_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "q3_safe_frontier.json").write_text(
        json.dumps(safe_frontier_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "q3_official_frontier.json").write_text(
        json.dumps(official_frontier_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "q3_pareto_trace.json").write_text(
        json.dumps(traces, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(candidate_path.read_text(encoding="utf-8"))
    print(safe_frontier_path.read_text(encoding="utf-8"))
    print(official_frontier_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
