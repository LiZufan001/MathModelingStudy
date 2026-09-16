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
from benchmark_q2_transfer_aware import _q3_summary, _transfer_summary
from parser import load_case
from q2_model import spill_cycles
from q2_promoted import solve_q2_promoted
from q2_transfer_aware_window import make_transfer_aware_chooser


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--case", default="Conv_Case1")
    ap.add_argument("--policy", choices=("min_total_transfer", "min_mte2_spill_in", "min_mte3_spill_out"), required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    graph = load_case(args.data_dir, args.case)
    per_buf = {
        node.buf_id: spill_cycles(graph, node.buf_id)
        for node in graph.nodes.values()
        if node.is_alloc and node.buf_id is not None
    }
    costs = {
        "min_total_transfer": {buf: out + incoming for buf, (out, incoming) in per_buf.items()},
        "min_mte2_spill_in": {buf: incoming for buf, (_, incoming) in per_buf.items()},
        "min_mte3_spill_out": {buf: out for buf, (out, _) in per_buf.items()},
    }[args.policy]

    t0 = time.perf_counter()
    baseline = solve_q2_promoted(graph)
    baseline.validation.require_ok()
    t1 = time.perf_counter()

    original = q2_allocator.choose_min_cost_window
    try:
        q2_allocator.choose_min_cost_window = make_transfer_aware_chooser(costs)
        experimental = solve_q2_promoted(graph)
    finally:
        q2_allocator.choose_min_cost_window = original
    experimental.validation.require_ok()
    t2 = time.perf_counter()

    base_transfer = _transfer_summary(graph, baseline.solution)
    exp_transfer = _transfer_summary(graph, experimental.solution)
    base_q3 = _q3_summary(graph, baseline.solution)
    exp_q3 = _q3_summary(graph, experimental.solution)
    t3 = time.perf_counter()

    same_q2_primary = (
        experimental.validation.extra_traffic == baseline.validation.extra_traffic
        and experimental.validation.spill_count == baseline.validation.spill_count
    )
    payload = {
        "case": args.case,
        "policy": args.policy,
        "same_q2_primary": same_q2_primary,
        "baseline": {
            "extra_traffic": baseline.validation.extra_traffic,
            "spill_count": baseline.validation.spill_count,
            "transfer": base_transfer,
            "q3": base_q3,
        },
        "experimental": {
            "extra_traffic": experimental.validation.extra_traffic,
            "spill_count": experimental.validation.spill_count,
            "transfer": exp_transfer,
            "q3": exp_q3,
        },
        "delta": {
            "extra_traffic": experimental.validation.extra_traffic - baseline.validation.extra_traffic,
            "spill_count": experimental.validation.spill_count - baseline.validation.spill_count,
            "spill_out_cycles": exp_transfer["spill_out_cycles"] - base_transfer["spill_out_cycles"],
            "spill_in_cycles": exp_transfer["spill_in_cycles"] - base_transfer["spill_in_cycles"],
            "spill_transfer_cycles": exp_transfer["spill_transfer_cycles"] - base_transfer["spill_transfer_cycles"],
            "zero_out_spills": exp_transfer["zero_out_spills"] - base_transfer["zero_out_spills"],
            "promoted_official_cycles": exp_q3["official_cycles"] - base_q3["official_cycles"],
            "promoted_safe_cycles": exp_q3["safe_cycles"] - base_q3["safe_cycles"],
        },
        "seconds": {
            "baseline_q2": round(t1 - t0, 6),
            "policy_q2": round(t2 - t1, 6),
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
