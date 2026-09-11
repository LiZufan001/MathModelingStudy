from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from parser import load_case
from q2_promoted import solve_q2_promoted
from q3_evaluator import evaluate_q3_solution
from q3_reallocator import repack_q3_addresses

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)
POLICIES = ("best_fit", "first_fit_low", "first_fit_high", "next_fit")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark Q3 address-reuse policies at fixed traffic")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    winners: dict[str, dict[str, object]] = {}

    for case in CASES:
        graph = load_case(args.data_dir, case)
        promoted = solve_q2_promoted(graph)
        q2 = promoted.allocation
        q2.validation.require_ok()
        baseline = evaluate_q3_solution(graph, q2.solution, reuse_mode="residency_safe")
        baseline.require_ok()

        candidates: list[tuple[int, str, object]] = [
            (baseline.total_cycles, "original_q2_addresses", q2.solution)
        ]
        rows.append(
            {
                "case": case,
                "polish_window": promoted.polish_window,
                "policy": "original_q2_addresses",
                "cycles": baseline.total_cycles,
                "cycle_delta": 0,
                "cycle_ratio": 1.0,
                "spill_count": q2.validation.spill_count,
                "extra_traffic": q2.validation.extra_traffic,
                "reuse_edges": baseline.reuse_edge_count,
                "overlap_errors": len(baseline.physical_overlap_errors),
                "seconds": 0.0,
                "valid": True,
                "error": "",
            }
        )

        for policy in POLICIES:
            t0 = time.perf_counter()
            try:
                repacked = repack_q3_addresses(graph, q2.solution, policy).solution
                timing = evaluate_q3_solution(graph, repacked, reuse_mode="residency_safe")
                timing.require_ok()
                seconds = time.perf_counter() - t0
                candidates.append((timing.total_cycles, policy, repacked))
                rows.append(
                    {
                        "case": case,
                        "polish_window": promoted.polish_window,
                        "policy": policy,
                        "cycles": timing.total_cycles,
                        "cycle_delta": timing.total_cycles - baseline.total_cycles,
                        "cycle_ratio": round(timing.total_cycles / baseline.total_cycles, 6),
                        "spill_count": q2.validation.spill_count,
                        "extra_traffic": q2.validation.extra_traffic,
                        "reuse_edges": timing.reuse_edge_count,
                        "overlap_errors": len(timing.physical_overlap_errors),
                        "seconds": round(seconds, 6),
                        "valid": True,
                        "error": "",
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "case": case,
                        "polish_window": promoted.polish_window,
                        "policy": policy,
                        "cycles": None,
                        "cycle_delta": None,
                        "cycle_ratio": None,
                        "spill_count": q2.validation.spill_count,
                        "extra_traffic": q2.validation.extra_traffic,
                        "reuse_edges": None,
                        "overlap_errors": None,
                        "seconds": round(time.perf_counter() - t0, 6),
                        "valid": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        best_cycles, best_policy, _ = min(candidates, key=lambda item: (item[0], item[1]))
        winners[case] = {
            "polish_window": promoted.polish_window,
            "baseline_cycles": baseline.total_cycles,
            "winner_policy": best_policy,
            "winner_cycles": best_cycles,
            "cycle_delta": best_cycles - baseline.total_cycles,
            "cycle_ratio": round(best_cycles / baseline.total_cycles, 6),
            "spill_count": q2.validation.spill_count,
            "extra_traffic": q2.validation.extra_traffic,
        }

    _write_csv(args.out_dir / "q3_address_policy_grid.csv", rows)
    (args.out_dir / "q3_address_policy_winners.json").write_text(
        json.dumps(winners, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(winners, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
