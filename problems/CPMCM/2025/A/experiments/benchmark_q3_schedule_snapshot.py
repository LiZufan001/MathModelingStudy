from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from benchmark_q3_priority_snapshot import _replay_snapshot
from parser import load_case
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_conv_greedy_recolor import optimize_q3_critical_recolor_greedy
from q3_critical_pipe_swap import search_q3_critical_pipe_swaps
from q3_priority_rescheduler import search_q3_priority_reschedule_portfolio
from q3_spill_gap_shift import search_q3_critical_spill_gap_shifts


def _candidate_payload(name, result, baseline_official: int):
    best_edge = getattr(result, "best_edge", None)
    best_policy = getattr(result, "best_policy", None)
    return {
        "name": name,
        "official_cycles": result.best_official.total_cycles,
        "improvement_cycles": baseline_official - result.best_official.total_cycles,
        "safe_cycles": result.best_safe.total_cycles,
        "improved": result.best_official.total_cycles < baseline_official,
        "best_policy": best_policy,
        "best_edge": None if best_edge is None else list(best_edge),
        "safe_overlap_errors": len(result.best_safe.physical_overlap_errors),
        "trials": [asdict(trial) for trial in result.trials],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pipe-candidates", type=int, default=24)
    ap.add_argument("--spill-candidates", type=int, default=8)
    ap.add_argument("--joint-recolor-rounds", type=int, default=3)
    args = ap.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    case = snapshot["case"]
    graph = load_case(args.data_dir, case)
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()

    t0 = time.perf_counter()
    saturated_solution, saturated_official, saturated_safe = _replay_snapshot(
        graph, promoted.allocation.solution, snapshot
    )
    t1 = time.perf_counter()

    priority = search_q3_priority_reschedule_portfolio(
        graph,
        saturated_solution,
        baseline_official=saturated_official,
        baseline_safe=saturated_safe,
    )
    t2 = time.perf_counter()
    pipe = search_q3_critical_pipe_swaps(
        graph,
        saturated_solution,
        max_candidates=args.pipe_candidates,
        baseline_official=saturated_official,
        baseline_safe=saturated_safe,
    )
    t3 = time.perf_counter()

    first_candidates = [
        ("baseline", saturated_solution, saturated_official, saturated_safe),
        ("priority", priority.best_solution, priority.best_official, priority.best_safe),
        ("critical_pipe", pipe.best_solution, pipe.best_official, pipe.best_safe),
    ]
    first_name, first_solution, first_official, first_safe = min(
        first_candidates,
        key=lambda item: (item[2].total_cycles, item[3].total_cycles, item[0]),
    )

    gap = search_q3_critical_spill_gap_shifts(
        graph,
        first_solution,
        max_spills=args.spill_candidates,
        gap_radius=1,
        baseline_official=first_official,
        baseline_safe=first_safe,
    )
    t4 = time.perf_counter()
    second_candidates = [
        (first_name, first_solution, first_official, first_safe),
        ("spill_gap_after_first", gap.best_solution, gap.best_official, gap.best_safe),
    ]
    second_name, second_solution, second_official, second_safe = min(
        second_candidates,
        key=lambda item: (item[2].total_cycles, item[3].total_cycles, item[0]),
    )

    composed_priority = None
    composed_pipe = None
    composed_candidates = [(second_name, second_solution, second_official, second_safe)]
    if second_official.total_cycles < saturated_official.total_cycles:
        composed_priority = search_q3_priority_reschedule_portfolio(
            graph,
            second_solution,
            baseline_official=second_official,
            baseline_safe=second_safe,
        )
        composed_pipe = search_q3_critical_pipe_swaps(
            graph,
            second_solution,
            max_candidates=args.pipe_candidates,
            baseline_official=second_official,
            baseline_safe=second_safe,
        )
        composed_candidates.extend(
            [
                (
                    "priority_after_second",
                    composed_priority.best_solution,
                    composed_priority.best_official,
                    composed_priority.best_safe,
                ),
                (
                    "pipe_after_second",
                    composed_pipe.best_solution,
                    composed_pipe.best_official,
                    composed_pipe.best_safe,
                ),
            ]
        )
    t5 = time.perf_counter()

    third_name, third_solution, third_official, third_safe = min(
        composed_candidates,
        key=lambda item: (item[2].total_cycles, item[3].total_cycles, item[0]),
    )
    joint_recolor = None
    final_candidates = [(third_name, third_solution, third_official, third_safe)]
    if (
        args.joint_recolor_rounds > 0
        and third_official.total_cycles < saturated_official.total_cycles
    ):
        joint_recolor = optimize_q3_critical_recolor_greedy(
            graph,
            third_solution,
            max_rounds=args.joint_recolor_rounds,
            max_targets=6,
            max_starts=12,
        )
        final_candidates.append(
            (
                "shallow_recolor_after_schedule",
                joint_recolor.final_solution,
                joint_recolor.final_official,
                joint_recolor.final_safe,
            )
        )
    t6 = time.perf_counter()

    final_name, final_solution, final_official, final_safe = min(
        final_candidates,
        key=lambda item: (item[2].total_cycles, item[3].total_cycles, item[0]),
    )
    final_q2 = validate_q2_solution(graph, final_solution)
    final_q2.require_ok()
    if final_q2.spill_count != snapshot["spill_count"]:
        raise AssertionError("schedule probe changed spill count")
    if final_q2.extra_traffic != snapshot["extra_traffic"]:
        raise AssertionError("schedule probe changed extra traffic")
    if not final_safe.ok or not final_official.ok:
        raise AssertionError("schedule probe final timing invalid")

    payload = {
        "case": case,
        "saturated_official_cycles": saturated_official.total_cycles,
        "saturated_safe_cycles": saturated_safe.total_cycles,
        "priority": _candidate_payload("priority", priority, saturated_official.total_cycles),
        "critical_pipe": _candidate_payload("critical_pipe", pipe, saturated_official.total_cycles),
        "spill_gap": {
            "input_source": first_name,
            "input_official_cycles": first_official.total_cycles,
            "critical_spill_count": len(gap.critical_spill_indices),
            "best_shift": None if gap.best_shift is None else list(gap.best_shift),
            "official_cycles": gap.best_official.total_cycles,
            "safe_cycles": gap.best_safe.total_cycles,
            "improvement_cycles": first_official.total_cycles - gap.best_official.total_cycles,
            "trials": [asdict(trial) for trial in gap.trials],
        },
        "composition": {
            "priority": None
            if composed_priority is None
            else _candidate_payload("priority_after_second", composed_priority, second_official.total_cycles),
            "critical_pipe": None
            if composed_pipe is None
            else _candidate_payload("pipe_after_second", composed_pipe, second_official.total_cycles),
        },
        "joint_recolor": None
        if joint_recolor is None
        else {
            "input_source": third_name,
            "input_official_cycles": third_official.total_cycles,
            "accepted_rounds": joint_recolor.accepted_rounds,
            "attempted_rounds": len(joint_recolor.rounds),
            "official_cycles": joint_recolor.final_official.total_cycles,
            "safe_cycles": joint_recolor.final_safe.total_cycles,
            "improvement_cycles": third_official.total_cycles - joint_recolor.final_official.total_cycles,
        },
        "final_source": final_name,
        "final_official_cycles": final_official.total_cycles,
        "final_safe_cycles": final_safe.total_cycles,
        "improvement_cycles": saturated_official.total_cycles - final_official.total_cycles,
        "improved": final_official.total_cycles < saturated_official.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(final_safe.physical_overlap_errors),
        "valid": final_official.ok and final_safe.ok,
        "snapshot_replay_seconds": round(t1 - t0, 6),
        "priority_seconds": round(t2 - t1, 6),
        "critical_pipe_seconds": round(t3 - t2, 6),
        "spill_gap_seconds": round(t4 - t3, 6),
        "composition_seconds": round(t5 - t4, 6),
        "joint_recolor_seconds": round(t6 - t5, 6),
        "total_seconds": round(t6 - t0, 6),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
