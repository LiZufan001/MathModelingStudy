from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
EXP = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(EXP))

import q2_allocator
from parser import load_case
from q2_model import spill_cycles
from q2_promoted import solve_q2_promoted
from q3_evaluator import evaluate_q3_solution
from q2_transfer_aware_window import make_transfer_aware_chooser


def _transfer_summary(graph, solution) -> dict[str, int]:
    out_cycles = 0
    in_cycles = 0
    zero_out_spills = 0
    for spill in solution.spills:
        out, incoming = spill_cycles(graph, spill.buf_id)
        out_cycles += out
        in_cycles += incoming
        zero_out_spills += int(out == 0)
    return {
        "spill_count": len(solution.spills),
        "spill_out_cycles": out_cycles,
        "spill_in_cycles": in_cycles,
        "spill_transfer_cycles": out_cycles + in_cycles,
        "zero_out_spills": zero_out_spills,
    }


def _q3_summary(graph, solution) -> dict[str, int | bool]:
    official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    official.require_ok()
    safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    safe.require_ok()
    return {
        "official_cycles": official.total_cycles,
        "safe_cycles": safe.total_cycles,
        "safe_overlap_errors": len(safe.physical_overlap_errors),
        "valid": official.ok and safe.ok,
    }


def _run_policy(graph, cost_map: dict[int, int]):
    original_chooser = q2_allocator.choose_min_cost_window
    try:
        q2_allocator.choose_min_cost_window = make_transfer_aware_chooser(cost_map)
        result = solve_q2_promoted(graph)
    finally:
        q2_allocator.choose_min_cost_window = original_chooser
    result.validation.require_ok()
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--case", default="Conv_Case1")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    graph = load_case(args.data_dir, args.case)

    per_buf: dict[int, tuple[int, int]] = {}
    for node in graph.nodes.values():
        if not node.is_alloc or node.buf_id is None:
            continue
        per_buf[node.buf_id] = spill_cycles(graph, node.buf_id)
    policy_costs = {
        "min_total_transfer": {buf: out + incoming for buf, (out, incoming) in per_buf.items()},
        "min_mte2_spill_in": {buf: incoming for buf, (_, incoming) in per_buf.items()},
        "min_mte3_spill_out": {buf: out for buf, (out, _) in per_buf.items()},
    }

    t0 = time.perf_counter()
    baseline = solve_q2_promoted(graph)
    baseline.validation.require_ok()
    t1 = time.perf_counter()

    baseline_transfer = _transfer_summary(graph, baseline.solution)
    baseline_q3 = _q3_summary(graph, baseline.solution)
    policies: dict[str, dict] = {}

    for name, costs in policy_costs.items():
        p0 = time.perf_counter()
        result = _run_policy(graph, costs)
        p1 = time.perf_counter()
        transfer = _transfer_summary(graph, result.solution)
        q3 = _q3_summary(graph, result.solution)
        p2 = time.perf_counter()
        same_q2_primary = (
            result.validation.extra_traffic == baseline.validation.extra_traffic
            and result.validation.spill_count == baseline.validation.spill_count
        )
        policies[name] = {
            "same_q2_primary": same_q2_primary,
            "extra_traffic": result.validation.extra_traffic,
            "spill_count": result.validation.spill_count,
            "polish_window": result.polish_window,
            "changed_positions": result.changed_positions,
            "transfer": transfer,
            "q3": q3,
            "delta_vs_baseline": {
                "extra_traffic": result.validation.extra_traffic - baseline.validation.extra_traffic,
                "spill_count": result.validation.spill_count - baseline.validation.spill_count,
                "spill_out_cycles": transfer["spill_out_cycles"] - baseline_transfer["spill_out_cycles"],
                "spill_in_cycles": transfer["spill_in_cycles"] - baseline_transfer["spill_in_cycles"],
                "spill_transfer_cycles": transfer["spill_transfer_cycles"] - baseline_transfer["spill_transfer_cycles"],
                "zero_out_spills": transfer["zero_out_spills"] - baseline_transfer["zero_out_spills"],
                "promoted_official_cycles": q3["official_cycles"] - baseline_q3["official_cycles"],
                "promoted_safe_cycles": q3["safe_cycles"] - baseline_q3["safe_cycles"],
            },
            "seconds": {
                "q2": round(p1 - p0, 6),
                "q3_replays": round(p2 - p1, 6),
                "total": round(p2 - p0, 6),
            },
        }

    t2 = time.perf_counter()
    comparable = {
        name: data
        for name, data in policies.items()
        if data["same_q2_primary"] and data["q3"]["valid"]
    }
    best_policy = min(
        comparable,
        key=lambda name: (
            comparable[name]["q3"]["official_cycles"],
            comparable[name]["q3"]["safe_cycles"],
            name,
        ),
        default=None,
    )
    payload = {
        "case": args.case,
        "baseline": {
            "extra_traffic": baseline.validation.extra_traffic,
            "spill_count": baseline.validation.spill_count,
            "polish_window": baseline.polish_window,
            "changed_positions": baseline.changed_positions,
            "transfer": baseline_transfer,
            "q3": baseline_q3,
        },
        "policies": policies,
        "best_same_q2_policy": best_policy,
        "best_same_q2_official_cycles": None if best_policy is None else comparable[best_policy]["q3"]["official_cycles"],
        "seconds": {
            "baseline": round(t1 - t0, 6),
            "policy_portfolio": round(t2 - t1, 6),
            "total": round(t2 - t0, 6),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
