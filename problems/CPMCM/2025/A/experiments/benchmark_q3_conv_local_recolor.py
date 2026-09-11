from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from parser import load_case
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_conv_local_recolor import search_q3_critical_recolor
from q3_evaluator import evaluate_q3_solution
from q3_official_optimizer import optimize_q3_official_zero_traffic
from q3_pipeline_scheduler import reschedule_q3_critical

CASES = ("Conv_Case0", "Conv_Case1")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Conv critical-reuse local initial-address recoloring at frozen Q2 traffic, "
            "followed by one critical pipeline reschedule"
        )
    )
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--max-targets", type=int, default=6)
    ap.add_argument("--max-starts", type=int, default=12)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, object]] = []
    trial_rows: list[dict[str, object]] = []
    summary_json: dict[str, object] = {}

    for case in CASES:
        started = time.perf_counter()
        graph = load_case(args.data_dir, case)
        promoted = solve_q2_promoted(graph)
        promoted.validation.require_ok()
        baseline = optimize_q3_official_zero_traffic(
            graph,
            promoted.allocation.solution,
            max_rounds=2,
        )
        baseline.safe_timing.require_ok()
        baseline.official_timing.require_ok()
        base_q2 = validate_q2_solution(graph, baseline.solution)
        base_q2.require_ok()
        base_spills = tuple(spill.buf_id for spill in baseline.solution.spills)

        local_started = time.perf_counter()
        local = search_q3_critical_recolor(
            graph,
            baseline.solution,
            max_targets=args.max_targets,
            max_starts=args.max_starts,
        )
        local_seconds = time.perf_counter() - local_started

        chosen_solution = baseline.solution
        chosen_safe = baseline.safe_timing
        chosen_official = baseline.official_timing
        chosen_stage = "official_zero_traffic_baseline"
        local_raw_improvement = 0
        post_critical_improvement = 0

        if local.improved:
            chosen_solution = local.best_solution
            chosen_safe = local.best_safe
            chosen_official = local.best_official
            chosen_stage = "local_recolor"
            local_raw_improvement = baseline.official_timing.total_cycles - local.best_official.total_cycles

            try:
                critical = reschedule_q3_critical(graph, local.best_solution)
                critical.timing.require_ok()
                critical_official = evaluate_q3_solution(
                    graph,
                    critical.solution,
                    reuse_mode="official_literal",
                )
                critical_official.require_ok()
                if critical_official.total_cycles < chosen_official.total_cycles:
                    chosen_solution = critical.solution
                    chosen_safe = critical.timing
                    chosen_official = critical_official
                    chosen_stage = "local_recolor_plus_critical"
                    post_critical_improvement = (
                        local.best_official.total_cycles - critical_official.total_cycles
                    )
            except Exception:
                pass

        final_q2 = validate_q2_solution(graph, chosen_solution)
        final_q2.require_ok()
        if final_q2.extra_traffic != base_q2.extra_traffic:
            raise AssertionError(f"{case}: local recolor changed extra traffic")
        if final_q2.spill_count != base_q2.spill_count:
            raise AssertionError(f"{case}: local recolor changed spill count")
        if tuple(spill.buf_id for spill in chosen_solution.spills) != base_spills:
            raise AssertionError(f"{case}: local recolor changed spill victim identity/order")
        final_safe = evaluate_q3_solution(graph, chosen_solution, reuse_mode="residency_safe")
        final_safe.require_ok()
        final_official = evaluate_q3_solution(graph, chosen_solution, reuse_mode="official_literal")
        final_official.require_ok()
        if final_official.total_cycles != chosen_official.total_cycles:
            raise AssertionError(f"{case}: final official replay mismatch")
        if final_official.total_cycles > baseline.official_timing.total_cycles:
            raise AssertionError(f"{case}: local recolor regressed official cycles")

        for trial in local.trials:
            trial_rows.append(
                {
                    "case": case,
                    "buf_id": trial.buf_id,
                    "old_offset": trial.old_offset,
                    "new_offset": trial.new_offset,
                    "q2_valid": trial.q2_valid,
                    "safe_valid": trial.safe_valid,
                    "official_cycles": trial.official_cycles,
                    "safe_cycles": trial.safe_cycles,
                    "official_reuse_edges": trial.official_reuse_edges,
                    "error": trial.error,
                }
            )

        improved_cycles = baseline.official_timing.total_cycles - final_official.total_cycles
        row = {
            "case": case,
            "polish_window": promoted.polish_window,
            "extra_traffic": final_q2.extra_traffic,
            "spill_count": final_q2.spill_count,
            "baseline_official_cycles": baseline.official_timing.total_cycles,
            "baseline_safe_cycles": baseline.safe_timing.total_cycles,
            "baseline_official_reuse_edges": baseline.official_timing.reuse_edge_count,
            "baseline_safe_reuse_edges": baseline.safe_timing.reuse_edge_count,
            "target_count": len(local.target_buffers),
            "target_buffers": ";".join(str(x) for x in local.target_buffers),
            "trial_count": len(local.trials),
            "q2_valid_trial_count": sum(1 for t in local.trials if t.q2_valid),
            "safe_valid_trial_count": sum(1 for t in local.trials if t.safe_valid),
            "local_raw_official_cycles": local.best_official.total_cycles,
            "local_raw_improvement": local_raw_improvement,
            "post_critical_improvement": post_critical_improvement,
            "chosen_stage": chosen_stage,
            "final_official_cycles": final_official.total_cycles,
            "final_safe_cycles": final_safe.total_cycles,
            "final_official_reuse_edges": final_official.reuse_edge_count,
            "final_safe_reuse_edges": final_safe.reuse_edge_count,
            "official_improvement_cycles": improved_cycles,
            "official_improvement_pct": round(
                100.0 * improved_cycles / baseline.official_timing.total_cycles,
                6,
            ),
            "local_search_seconds": round(local_seconds, 6),
            "total_seconds": round(time.perf_counter() - started, 6),
        }
        summary_rows.append(row)
        summary_json[case] = dict(row)

    _write_csv(args.out_dir / "conv_local_recolor_summary.csv", summary_rows)
    _write_csv(args.out_dir / "conv_local_recolor_trials.csv", trial_rows)
    (args.out_dir / "conv_local_recolor_summary.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print((args.out_dir / "conv_local_recolor_summary.csv").read_text(encoding="utf-8"))
    print(json.dumps(summary_json, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
