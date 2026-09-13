from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph
from parser import load_case
from q2_model import Q2Solution
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution
from q3_official_optimizer import optimize_q3_official_zero_traffic
from q3_spill_batch_optimizer import optimize_q3_critical_spill_batches


CASE = "Conv_Case1"
REFERENCE_FINAL_OFFICIAL = 3_767_326
PREFIX_SIZES = (1, 2, 4, 8, 16, 24, 32, 48, 64)


def _write_problem3_outputs(out_dir: Path, solution: Q2Solution) -> None:
    case_dir = out_dir / CASE
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / f"{CASE}_schedule.txt").write_text(
        "".join(f"{node_id}\n" for node_id in solution.schedule), encoding="utf-8"
    )
    (case_dir / f"{CASE}_memory.txt").write_text(
        "".join(
            f"{buf_id}:{solution.initial_offsets[buf_id]}\n"
            for buf_id in sorted(solution.initial_offsets)
        ),
        encoding="utf-8",
    )
    (case_dir / f"{CASE}_spill.txt").write_text(
        "".join(f"{spill.buf_id}:{spill.new_offset}\n" for spill in solution.spills),
        encoding="utf-8",
    )


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
        "trials": [
            {
                "prefix_size": trial.prefix_size,
                "spill_indices": list(trial.spill_indices),
                "reversed_edges": [list(edge) for edge in trial.reversed_edges],
                "q2_valid": trial.q2_valid,
                "safe_valid": trial.safe_valid,
                "official_cycles": trial.official_cycles,
                "safe_cycles": trial.safe_cycles,
                "changed_positions": trial.changed_positions,
                "error": trial.error,
            }
            for trial in result.trials
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--max-rounds", type=int, default=12)
    args = ap.parse_args()

    snap = json.loads(args.snapshot.read_text(encoding="utf-8"))
    if snap["case"] != CASE:
        raise AssertionError(f"unexpected snapshot case {snap['case']!r}")
    graph: ComputeGraph = load_case(args.data_dir, CASE)

    t0 = time.perf_counter()
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()
    promoted_solution = promoted.solution
    promoted_q2 = validate_q2_solution(graph, promoted_solution)
    promoted_q2.require_ok()
    if promoted_q2.spill_count != int(snap["spill_count"]):
        raise AssertionError("promoted-Q2 spill count drifted")
    if promoted_q2.extra_traffic != int(snap["extra_traffic"]):
        raise AssertionError("promoted-Q2 extra traffic drifted")

    core = optimize_q3_official_zero_traffic(graph, promoted_solution, max_rounds=2)
    if core.official_timing.total_cycles != int(snap["core_official_cycles"]):
        raise AssertionError("formal core official timing drifted")
    if core.safe_timing.total_cycles != int(snap["core_safe_cycles"]):
        raise AssertionError("formal core safe timing drifted")

    offsets = dict(core.solution.initial_offsets)
    for key, value in snap["offset_overrides"].items():
        offsets[int(key)] = int(value)
    saturated = Q2Solution(core.solution.schedule, offsets, core.solution.spills)
    saturated_q2 = validate_q2_solution(graph, saturated)
    saturated_q2.require_ok()
    saturated_official = evaluate_q3_solution(
        graph, saturated, reuse_mode="official_literal"
    )
    saturated_official.require_ok()
    saturated_safe = evaluate_q3_solution(
        graph, saturated, reuse_mode="residency_safe"
    )
    saturated_safe.require_ok()
    if saturated_official.total_cycles != int(snap["saturated_official_cycles"]):
        raise AssertionError("saturated official timing drifted")
    if saturated_safe.total_cycles != int(snap["saturated_safe_cycles"]):
        raise AssertionError("saturated safe timing drifted")
    if saturated.spills != core.solution.spills:
        raise AssertionError("saturated offset snapshot changed SPILL records")
    t1 = time.perf_counter()

    result = optimize_q3_critical_spill_batches(
        graph,
        saturated,
        max_rounds=args.max_rounds,
        max_switches=64,
        prefix_sizes=PREFIX_SIZES,
        baseline_official=saturated_official,
        baseline_safe=saturated_safe,
    )
    t2 = time.perf_counter()

    if not result.saturated:
        raise AssertionError("formal Conv1 spill-batch search did not reach a no-improvement round")
    final_q2 = validate_q2_solution(graph, result.final_solution)
    final_q2.require_ok()
    if result.final_solution.spills != saturated.spills:
        raise AssertionError("formal Conv1 spill-batch changed exact SPILL records")
    if final_q2.spill_count != saturated_q2.spill_count:
        raise AssertionError("formal Conv1 spill-batch changed spill count")
    if final_q2.extra_traffic != saturated_q2.extra_traffic:
        raise AssertionError("formal Conv1 spill-batch changed extra traffic")

    final_official = evaluate_q3_solution(
        graph, result.final_solution, reuse_mode="official_literal"
    )
    final_official.require_ok()
    final_safe = evaluate_q3_solution(
        graph, result.final_solution, reuse_mode="residency_safe"
    )
    final_safe.require_ok()
    if final_official.total_cycles != result.final_official.total_cycles:
        raise AssertionError("formal Conv1 official replay mismatch")
    if final_safe.total_cycles != result.final_safe.total_cycles:
        raise AssertionError("formal Conv1 residency-safe replay mismatch")
    if final_official.total_cycles > REFERENCE_FINAL_OFFICIAL:
        raise AssertionError(
            f"formal Conv1 regressed: {final_official.total_cycles} > {REFERENCE_FINAL_OFFICIAL}"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_problem3_outputs(args.out_dir, result.final_solution)
    schedule_bytes = "".join(f"{node_id}\n" for node_id in result.final_solution.schedule).encode()

    payload = {
        "case": CASE,
        "route": "promoted_q2->formal_core->deterministic_saturated_offsets->formal_iterative_spill_batch",
        "promoted_q2": {
            "spill_count": promoted_q2.spill_count,
            "extra_traffic": promoted_q2.extra_traffic,
        },
        "core": {
            "official_cycles": core.official_timing.total_cycles,
            "safe_cycles": core.safe_timing.total_cycles,
        },
        "saturated": {
            "official_cycles": saturated_official.total_cycles,
            "safe_cycles": saturated_safe.total_cycles,
            "offset_override_count": len(snap["offset_overrides"]),
        },
        "spill_batch": {
            "improved": result.improved,
            "saturated": result.saturated,
            "accepted_rounds": result.accepted_rounds,
            "round_count": len(result.rounds),
            "max_rounds": args.max_rounds,
            "max_switches": 64,
            "prefix_sizes": list(PREFIX_SIZES),
            "rounds": [
                _round_payload(index, round_result)
                for index, round_result in enumerate(result.rounds, 1)
            ],
        },
        "final": {
            "official_cycles": final_official.total_cycles,
            "safe_cycles": final_safe.total_cycles,
            "reference_official_cycles": REFERENCE_FINAL_OFFICIAL,
            "improvement_vs_saturated_cycles": saturated_official.total_cycles
            - final_official.total_cycles,
            "spill_count": final_q2.spill_count,
            "extra_traffic": final_q2.extra_traffic,
            "safe_overlap_errors": len(final_safe.physical_overlap_errors),
            "valid": final_official.ok and final_safe.ok,
            "schedule_sha256": hashlib.sha256(schedule_bytes).hexdigest(),
        },
        "outputs": {
            "schedule": f"{CASE}/{CASE}_schedule.txt",
            "memory": f"{CASE}/{CASE}_memory.txt",
            "spill": f"{CASE}/{CASE}_spill.txt",
        },
        "seconds": {
            "setup": round(t1 - t0, 6),
            "formal_spill_batch": round(t2 - t1, 6),
            "total": round(t2 - t0, 6),
        },
    }
    (args.out_dir / "q3-formal-spill-Conv_Case1.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
