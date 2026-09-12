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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--case", default="Conv_Case1")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    graph = load_case(args.data_dir, args.case)

    t0 = time.perf_counter()
    baseline = solve_q2_promoted(graph)
    t1 = time.perf_counter()
    baseline.validation.require_ok()

    transfer_costs: dict[int, int] = {}
    for node in graph.nodes.values():
        if not node.is_alloc or node.buf_id is None:
            continue
        out, incoming = spill_cycles(graph, node.buf_id)
        transfer_costs[node.buf_id] = out + incoming

    original_chooser = q2_allocator.choose_min_cost_window
    try:
        q2_allocator.choose_min_cost_window = make_transfer_aware_chooser(transfer_costs)
        experimental = solve_q2_promoted(graph)
    finally:
        q2_allocator.choose_min_cost_window = original_chooser
    t2 = time.perf_counter()
    experimental.validation.require_ok()

    baseline_transfer = _transfer_summary(graph, baseline.solution)
    experimental_transfer = _transfer_summary(graph, experimental.solution)
    baseline_q3 = _q3_summary(graph, baseline.solution)
    experimental_q3 = _q3_summary(graph, experimental.solution)
    t3 = time.perf_counter()

    same_q2_primary = (
        experimental.validation.extra_traffic == baseline.validation.extra_traffic
        and experimental.validation.spill_count == baseline.validation.spill_count
    )
    payload = {
        "case": args.case,
        "same_q2_primary": same_q2_primary,
        "baseline": {
            "extra_traffic": baseline.validation.extra_traffic,
            "spill_count": baseline.validation.spill_count,
            "polish_window": baseline.polish_window,
            "changed_positions": baseline.changed_positions,
            "transfer": baseline_transfer,
            "q3": baseline_q3,
        },
        "transfer_aware": {
            "extra_traffic": experimental.validation.extra_traffic,
            "spill_count": experimental.validation.spill_count,
            "polish_window": experimental.polish_window,
            "changed_positions": experimental.changed_positions,
            "transfer": experimental_transfer,
            "q3": experimental_q3,
        },
        "delta": {
            "extra_traffic": experimental.validation.extra_traffic - baseline.validation.extra_traffic,
            "spill_count": experimental.validation.spill_count - baseline.validation.spill_count,
            "spill_out_cycles": experimental_transfer["spill_out_cycles"] - baseline_transfer["spill_out_cycles"],
            "spill_in_cycles": experimental_transfer["spill_in_cycles"] - baseline_transfer["spill_in_cycles"],
            "spill_transfer_cycles": experimental_transfer["spill_transfer_cycles"] - baseline_transfer["spill_transfer_cycles"],
            "zero_out_spills": experimental_transfer["zero_out_spills"] - baseline_transfer["zero_out_spills"],
            "promoted_official_cycles": experimental_q3["official_cycles"] - baseline_q3["official_cycles"],
            "promoted_safe_cycles": experimental_q3["safe_cycles"] - baseline_q3["safe_cycles"],
        },
        "seconds": {
            "baseline_q2": round(t1 - t0, 6),
            "transfer_aware_q2": round(t2 - t1, 6),
            "q3_replays": round(t3 - t2, 6),
            "total": round(t3 - t0, 6),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
