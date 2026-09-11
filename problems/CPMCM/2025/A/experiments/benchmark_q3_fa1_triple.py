from __future__ import annotations

import argparse
import csv
import itertools
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

CASE = "FlashAttention_Case1"
LOCAL_WINDOWS = (1, 2, 3)
ANCHORS = ((0,), (1, 1), (2, 1), (1, 2))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
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


def _sequence_specs() -> tuple[tuple[int, ...], ...]:
    triples = tuple(itertools.product(LOCAL_WINDOWS, repeat=3))
    seen: set[tuple[int, ...]] = set()
    out: list[tuple[int, ...]] = []
    for sequence in ANCHORS + triples:
        if sequence not in seen:
            seen.add(sequence)
            out.append(sequence)
    return tuple(out)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "FlashAttention_Case1 three-stage local critical-window search over "
            "{1,2,3}^3 plus current two-stage anchors; every candidate gets strict "
            "Q2 replay, residency-safe gating, and official-cycle post-optimization."
        )
    )
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--rounds", type=int, default=2)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    graph = load_case(args.data_dir, CASE)
    promoted = solve_q2_promoted(graph)
    promoted.validation.require_ok()
    base_traffic = promoted.validation.extra_traffic
    base_safe = evaluate_q3_solution(
        graph, promoted.solution, reuse_mode="residency_safe"
    )
    base_safe.require_ok()
    base_official = evaluate_q3_solution(
        graph, promoted.solution, reuse_mode="official_literal"
    )
    base_official.require_ok()

    rows: list[dict[str, object]] = []
    for sequence in _sequence_specs():
        started = time.perf_counter()
        label = ">".join(str(w) for w in sequence)
        row: dict[str, object] = {
            "case": CASE,
            "promoted_q2_polish_window": promoted.polish_window,
            "sequence": label,
            "stages": len(sequence),
            "stage1_window": sequence[0],
            "stage2_window": sequence[1] if len(sequence) > 1 else None,
            "stage3_window": sequence[2] if len(sequence) > 2 else None,
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
                    scheduled = schedule_q3_critical_window(
                        graph, order, window=window
                    )
                    order = scheduled.order
                    evaluation = scheduled.evaluation
                q2 = allocate_q2_baseline(graph, order)
                q2.validation.require_ok()

            changed = sum(
                1
                for i, node_id in enumerate(order)
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
        rows.append(row)

    frontier = _frontier(rows)
    by_sequence = {str(row["sequence"]): row for row in rows if row["valid"]}
    anchor_labels = ("1>1", "2>1", "1>2")
    missing = [label for label in anchor_labels if label not in by_sequence]
    if missing:
        raise RuntimeError(f"missing valid anchors: {missing}")

    triples = [row for row in rows if row["valid"] and int(row["stages"]) == 3]
    if not triples:
        raise RuntimeError("no valid three-stage candidates")

    best_triple_cycles = min(
        triples,
        key=lambda r: (
            int(r["optimized_official_cycles"]),
            int(r["extra_traffic"]),
            str(r["sequence"]),
        ),
    )
    best_triple_traffic = min(
        triples,
        key=lambda r: (
            int(r["extra_traffic"]),
            int(r["optimized_official_cycles"]),
            str(r["sequence"]),
        ),
    )

    anchor_dominators: dict[str, list[dict[str, object]]] = {}
    for label in anchor_labels:
        anchor = by_sequence[label]
        anchor_dominators[label] = [
            {
                "sequence": row["sequence"],
                "extra_traffic": row["extra_traffic"],
                "official_cycles": row["optimized_official_cycles"],
            }
            for row in sorted(
                (candidate for candidate in triples if _dominates(candidate, anchor)),
                key=lambda r: (
                    int(r["extra_traffic"]),
                    int(r["optimized_official_cycles"]),
                    str(r["sequence"]),
                ),
            )
        ]

    q2_better = [
        row
        for row in triples
        if int(row["extra_traffic"]) < base_traffic
    ]

    summary = {
        "case": CASE,
        "search_windows": list(LOCAL_WINDOWS),
        "triple_candidate_count": len(tuple(itertools.product(LOCAL_WINDOWS, repeat=3))),
        "total_candidate_count": len(rows),
        "valid_count": sum(1 for row in rows if row["valid"]),
        "promoted_q2_polish_window": promoted.polish_window,
        "base_traffic": base_traffic,
        "base_safe_cycles": base_safe.total_cycles,
        "base_official_cycles": base_official.total_cycles,
        "frontier_sequences": [row["sequence"] for row in frontier],
        "best_triple_cycles": {
            "sequence": best_triple_cycles["sequence"],
            "extra_traffic": best_triple_cycles["extra_traffic"],
            "traffic_delta_pct": best_triple_cycles["traffic_delta_pct"],
            "official_cycles": best_triple_cycles["optimized_official_cycles"],
            "official_improvement_pct": best_triple_cycles[
                "official_improvement_pct"
            ],
        },
        "best_triple_traffic": {
            "sequence": best_triple_traffic["sequence"],
            "extra_traffic": best_triple_traffic["extra_traffic"],
            "official_cycles": best_triple_traffic[
                "optimized_official_cycles"
            ],
        },
        "triple_dominators_of_anchors": anchor_dominators,
        "q2_traffic_improvements": [
            {
                "sequence": row["sequence"],
                "extra_traffic": row["extra_traffic"],
                "traffic_delta_pct": row["traffic_delta_pct"],
                "official_cycles": row["optimized_official_cycles"],
            }
            for row in sorted(
                q2_better,
                key=lambda r: (
                    int(r["extra_traffic"]),
                    int(r["optimized_official_cycles"]),
                ),
            )
        ],
    }

    _write_csv(args.out_dir / "fa1_triple_candidates.csv", rows)
    _write_csv(args.out_dir / "fa1_triple_frontier.csv", frontier)
    (args.out_dir / "fa1_triple_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print((args.out_dir / "fa1_triple_frontier.csv").read_text(encoding="utf-8"))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
