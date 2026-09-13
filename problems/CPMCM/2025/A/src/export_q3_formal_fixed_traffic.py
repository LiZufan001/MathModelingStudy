from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from parser import load_case
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution
from q3_official_spill_optimizer import optimize_q3_official_with_spill_batches


CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)
PREFIX_SIZES = (1, 2, 4, 8, 16, 24, 32, 48, 64)


def write_problem3_outputs(case: str, out_dir: Path, solution) -> dict[str, str]:
    problem3 = out_dir / "Problem3"
    problem3.mkdir(parents=True, exist_ok=True)
    schedule = problem3 / f"{case}_schedule.txt"
    memory = problem3 / f"{case}_memory.txt"
    spill = problem3 / f"{case}_spill.txt"
    schedule.write_text(
        "".join(f"{node_id}\n" for node_id in solution.schedule), encoding="utf-8"
    )
    memory.write_text(
        "".join(
            f"{buf_id}:{solution.initial_offsets[buf_id]}\n"
            for buf_id in sorted(solution.initial_offsets)
        ),
        encoding="utf-8",
    )
    spill.write_text(
        "".join(f"{record.buf_id}:{record.new_offset}\n" for record in solution.spills),
        encoding="utf-8",
    )
    return {
        "schedule": str(schedule.relative_to(out_dir)),
        "memory": str(memory.relative_to(out_dir)),
        "spill": str(spill.relative_to(out_dir)),
    }


def _round_payload(index: int, result) -> dict[str, object]:
    return {
        "round": index,
        "improved": result.improved,
        "baseline_official_cycles": result.baseline_official.total_cycles,
        "baseline_safe_cycles": result.baseline_safe.total_cycles,
        "best_prefix_size": result.best_prefix_size,
        "best_official_cycles": result.best_official.total_cycles,
        "best_safe_cycles": result.best_safe.total_cycles,
        "improvement_cycles": result.baseline_official.total_cycles
        - result.best_official.total_cycles,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Export formally accepted fixed-traffic Q3 Problem3 files")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--case", choices=CASES, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--official-ceiling", type=int)
    ap.add_argument("--spill-max-rounds", type=int, default=12)
    ap.add_argument("--require-spill-saturated", action="store_true")
    args = ap.parse_args()

    graph = load_case(args.data_dir, args.case)
    t0 = time.perf_counter()
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()
    promoted_solution = promoted.solution
    promoted_q2 = validate_q2_solution(graph, promoted_solution)
    promoted_q2.require_ok()
    promoted_spill_ids = tuple(record.buf_id for record in promoted_solution.spills)

    result = optimize_q3_official_with_spill_batches(
        graph,
        promoted_solution,
        max_rounds=2,
        recolor_max_rounds=24,
        recolor_max_targets=12,
        recolor_max_starts=24,
        spill_batch_max_rounds=args.spill_max_rounds,
        spill_batch_max_switches=64,
        spill_batch_prefix_sizes=PREFIX_SIZES,
    )
    elapsed = time.perf_counter() - t0

    final_q2 = validate_q2_solution(graph, result.solution)
    final_q2.require_ok()
    if tuple(record.buf_id for record in result.solution.spills) != promoted_spill_ids:
        raise AssertionError("formal Q3 export changed promoted-Q2 SPILL identity/order")
    if final_q2.spill_count != promoted_q2.spill_count:
        raise AssertionError("formal Q3 export changed promoted-Q2 spill count")
    if final_q2.extra_traffic != promoted_q2.extra_traffic:
        raise AssertionError("formal Q3 export changed promoted-Q2 extra traffic")

    official = evaluate_q3_solution(graph, result.solution, reuse_mode="official_literal")
    official.require_ok()
    safe = evaluate_q3_solution(graph, result.solution, reuse_mode="residency_safe")
    safe.require_ok()
    if official.total_cycles != result.official_timing.total_cycles:
        raise AssertionError("formal Q3 export official replay mismatch")
    if safe.total_cycles != result.safe_timing.total_cycles:
        raise AssertionError("formal Q3 export residency-safe replay mismatch")
    if args.official_ceiling is not None and official.total_cycles > args.official_ceiling:
        raise AssertionError(
            f"formal Q3 export regressed: {official.total_cycles} > {args.official_ceiling}"
        )
    if args.require_spill_saturated and not result.spill_batch_saturated:
        raise AssertionError("formal Q3 spill-batch stage did not reach a no-improvement round")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    outputs = write_problem3_outputs(args.case, args.out_dir, result.solution)
    evidence_dir = args.out_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    spill = result.spill_batches
    payload = {
        "case": args.case,
        "route": "promoted_q2->formal_zero_traffic->formal_iterative_spill_batch",
        "promoted_q2": {
            "spill_count": promoted_q2.spill_count,
            "extra_traffic": promoted_q2.extra_traffic,
        },
        "core": {
            "official_cycles": result.core.official_timing.total_cycles,
            "safe_cycles": result.core.safe_timing.total_cycles,
        },
        "spill_batch": {
            "enabled": spill is not None,
            "improved": result.spill_batch_improved,
            "saturated": result.spill_batch_saturated,
            "accepted_rounds": 0 if spill is None else spill.accepted_rounds,
            "round_count": 0 if spill is None else len(spill.rounds),
            "max_rounds": args.spill_max_rounds,
            "max_switches": 64,
            "prefix_sizes": list(PREFIX_SIZES),
            "rounds": []
            if spill is None
            else [
                _round_payload(index, round_result)
                for index, round_result in enumerate(spill.rounds, 1)
            ],
        },
        "final": {
            "official_cycles": official.total_cycles,
            "safe_cycles": safe.total_cycles,
            "official_ceiling": args.official_ceiling,
            "improvement_vs_core_cycles": result.core.official_timing.total_cycles
            - official.total_cycles,
            "spill_count": final_q2.spill_count,
            "extra_traffic": final_q2.extra_traffic,
            "safe_overlap_errors": len(safe.physical_overlap_errors),
            "valid": official.ok and safe.ok,
        },
        "outputs": outputs,
        "seconds": round(elapsed, 6),
    }
    evidence = evidence_dir / f"q3-formal-fixed-traffic-{args.case}.json"
    evidence.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
