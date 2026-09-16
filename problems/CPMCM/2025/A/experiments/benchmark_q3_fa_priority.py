from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EXP = ROOT / "experiments"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(EXP))

from parser import load_case
from priority_window_scheduler import schedule_priority_window
from q2_allocator import allocate_q2_baseline
from q2_promoted import solve_q2_promoted
from q3_evaluator import evaluate_q3_solution
from q3_official_optimizer import optimize_q3_official_zero_traffic
from q3_tradeoff_scheduler import schedule_q3_critical_window

CASES = ("FlashAttention_Case0", "FlashAttention_Case1")
NEW_POLICIES = ("pipe_remaining", "unlock", "pipe_unlock")
WINDOWS = tuple(range(1, 9))
ANCHORS = {
    "FlashAttention_Case0": ((0,), (1,)),
    "FlashAttention_Case1": ((0,), (1, 1), (2, 1)),
}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _frontier(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    valid = [row for row in rows if row["valid"] and row["within_5pct"]]
    out: list[dict[str, object]] = []
    for row in sorted(
        valid,
        key=lambda r: (
            int(r["extra_traffic"]),
            int(r["optimized_official_cycles"]),
            str(r["candidate"]),
        ),
    ):
        dominated = any(
            int(other["extra_traffic"]) <= int(row["extra_traffic"])
            and int(other["optimized_official_cycles"])
            <= int(row["optimized_official_cycles"])
            and (
                int(other["extra_traffic"]) < int(row["extra_traffic"])
                or int(other["optimized_official_cycles"])
                < int(row["optimized_official_cycles"])
            )
            for other in valid
            if other is not row
        )
        if not dominated:
            out.append(row)
    return out


def _dominates(a: dict[str, object], b: dict[str, object]) -> bool:
    return (
        int(a["extra_traffic"]) <= int(b["extra_traffic"])
        and int(a["optimized_official_cycles"]) <= int(b["optimized_official_cycles"])
        and (
            int(a["extra_traffic"]) < int(b["extra_traffic"])
            or int(a["optimized_official_cycles"]) < int(b["optimized_official_cycles"])
        )
    )


def _anchor_order(graph, promoted, sequence: tuple[int, ...]):
    if sequence == (0,):
        return promoted.order, promoted.evaluation
    order = promoted.order
    evaluation = promoted.evaluation
    for window in sequence:
        scheduled = schedule_q3_critical_window(graph, order, window=window)
        order = scheduled.order
        evaluation = scheduled.evaluation
    return order, evaluation


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "FlashAttention pipeline-priority window portfolio: compare the current "
            "critical-window refined anchors with graph-generic dynamic Pipe/unlock "
            "priorities under strict Q2 and residency-safe gates."
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
        promoted.validation.require_ok()
        base_traffic = promoted.validation.extra_traffic
        base_official = evaluate_q3_solution(
            graph, promoted.solution, reuse_mode="official_literal"
        )
        base_official.require_ok()

        specs: list[tuple[str, str, int | None, tuple[int, ...] | None]] = []
        for sequence in ANCHORS[case]:
            label = ">".join(str(w) for w in sequence)
            specs.append((f"anchor:{label}", "anchor", None, sequence))
        for policy in NEW_POLICIES:
            for window in WINDOWS:
                specs.append((f"{policy}:w{window}", policy, window, None))

        case_rows: list[dict[str, object]] = []
        for candidate, policy, window, anchor_sequence in specs:
            started = time.perf_counter()
            row: dict[str, object] = {
                "case": case,
                "candidate": candidate,
                "policy": policy,
                "window": window,
                "anchor_sequence": None
                if anchor_sequence is None
                else ">".join(str(w) for w in anchor_sequence),
                "changed_vs_promoted": None,
                "q1_peak": None,
                "spill_count": None,
                "extra_traffic": None,
                "traffic_delta": None,
                "traffic_delta_pct": None,
                "within_5pct": False,
                "raw_safe_cycles": None,
                "raw_official_cycles": None,
                "optimized_safe_cycles": None,
                "optimized_official_cycles": None,
                "official_improvement_pct": None,
                "accepted_zero_traffic_steps": None,
                "seconds": None,
                "valid": False,
                "error": "",
            }
            try:
                if anchor_sequence is not None:
                    order, evaluation = _anchor_order(
                        graph, promoted, anchor_sequence
                    )
                else:
                    scheduled = schedule_priority_window(
                        graph,
                        promoted.order,
                        window=int(window),
                        policy=policy,
                    )
                    order = scheduled.order
                    evaluation = scheduled.evaluation

                q2 = (
                    promoted.allocation
                    if anchor_sequence == (0,)
                    else allocate_q2_baseline(graph, order)
                )
                q2.validation.require_ok()
                traffic = q2.validation.extra_traffic
                within_5pct = traffic <= base_traffic * 1.05 + 1e-9

                row["changed_vs_promoted"] = sum(
                    1
                    for i, node_id in enumerate(order)
                    if node_id != promoted.order[i]
                )
                row["q1_peak"] = evaluation.peak_residency
                row["spill_count"] = q2.validation.spill_count
                row["extra_traffic"] = traffic
                row["traffic_delta"] = traffic - base_traffic
                row["traffic_delta_pct"] = round(
                    100.0 * (traffic - base_traffic) / base_traffic, 6
                )
                row["within_5pct"] = within_5pct

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

                if not within_5pct:
                    row["error"] = "strict-valid candidate exceeds the 5% experiment ceiling"
                else:
                    optimized = optimize_q3_official_zero_traffic(
                        graph,
                        q2.solution,
                        max_rounds=args.rounds,
                    )
                    optimized.safe_timing.require_ok()
                    optimized.official_timing.require_ok()
                    row["optimized_safe_cycles"] = optimized.safe_timing.total_cycles
                    row["optimized_official_cycles"] = (
                        optimized.official_timing.total_cycles
                    )
                    row["official_improvement_pct"] = round(
                        100.0
                        * (
                            base_official.total_cycles
                            - optimized.official_timing.total_cycles
                        )
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
            all_rows.append(row)

        frontier = _frontier(case_rows)
        frontier_rows.extend(dict(row) for row in frontier)

        anchors = {
            str(row["anchor_sequence"]): row
            for row in case_rows
            if row["valid"] and row["policy"] == "anchor"
        }
        new_rows = [
            row
            for row in case_rows
            if row["valid"] and row["policy"] != "anchor"
        ]

        anchor_dominators: dict[str, list[dict[str, object]]] = {}
        for label, anchor in anchors.items():
            anchor_dominators[label] = [
                {
                    "candidate": row["candidate"],
                    "extra_traffic": row["extra_traffic"],
                    "official_cycles": row["optimized_official_cycles"],
                }
                for row in sorted(
                    (r for r in new_rows if _dominates(r, anchor)),
                    key=lambda r: (
                        int(r["extra_traffic"]),
                        int(r["optimized_official_cycles"]),
                        str(r["candidate"]),
                    ),
                )
            ]

        best_new = min(
            new_rows,
            key=lambda r: (
                int(r["optimized_official_cycles"]),
                int(r["extra_traffic"]),
                str(r["candidate"]),
            ),
            default=None,
        )
        summary[case] = {
            "base_traffic": base_traffic,
            "base_official_cycles": base_official.total_cycles,
            "candidate_count": len(case_rows),
            "valid_within_5pct_count": len(
                [r for r in case_rows if r["valid"] and r["within_5pct"]]
            ),
            "frontier_candidates": [row["candidate"] for row in frontier],
            "new_policy_dominators_of_anchors": anchor_dominators,
            "best_new_policy": None
            if best_new is None
            else {
                "candidate": best_new["candidate"],
                "extra_traffic": best_new["extra_traffic"],
                "traffic_delta_pct": best_new["traffic_delta_pct"],
                "official_cycles": best_new["optimized_official_cycles"],
                "official_improvement_pct": best_new["official_improvement_pct"],
            },
        }

    _write_csv(args.out_dir / "fa_priority_candidates.csv", all_rows)
    _write_csv(args.out_dir / "fa_priority_frontier.csv", frontier_rows)
    (args.out_dir / "fa_priority_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print((args.out_dir / "fa_priority_frontier.csv").read_text(encoding="utf-8"))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
