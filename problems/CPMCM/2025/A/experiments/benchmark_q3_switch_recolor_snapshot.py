from __future__ import annotations

import argparse
import json
import sys
import time
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
from q3_critical_spill_switch_recipe import replay_q3_critical_spill_switch_move


def _accepted_offset_moves(round_result) -> list[dict[str, int]]:
    if not round_result.improved:
        return []
    before = round_result.baseline_solution.initial_offsets
    after = round_result.best_solution.initial_offsets
    moves: list[dict[str, int]] = []
    for buf_id in sorted(set(before) | set(after)):
        old = before.get(buf_id)
        new = after.get(buf_id)
        if old != new:
            moves.append({"buf_id": buf_id, "old_offset": old, "new_offset": new})
    return moves


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--recipe", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--recolor-rounds", type=int, default=3)
    ap.add_argument("--recolor-targets", type=int, default=6)
    ap.add_argument("--recolor-starts", type=int, default=12)
    args = ap.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
    if snapshot["case"] != recipe["case"]:
        raise AssertionError("snapshot and switch recipe case mismatch")

    graph = load_case(args.data_dir, snapshot["case"])
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()

    t0 = time.perf_counter()
    solution, baseline_official, baseline_safe = _replay_snapshot(
        graph,
        promoted.solution,
        snapshot,
    )
    t1 = time.perf_counter()

    baseline_q2 = validate_q2_solution(graph, solution)
    baseline_q2.require_ok()
    expected = recipe["baseline"]
    if baseline_official.total_cycles != expected["official_cycles"]:
        raise AssertionError("switch recipe baseline official cycles drifted")
    if baseline_safe.total_cycles != expected["safe_cycles"]:
        raise AssertionError("switch recipe baseline safe cycles drifted")
    if baseline_q2.spill_count != expected["spill_count"]:
        raise AssertionError("switch recipe baseline spill count drifted")
    if baseline_q2.extra_traffic != expected["extra_traffic"]:
        raise AssertionError("switch recipe baseline extra traffic drifted")

    move = recipe["move"]
    expected_edges = tuple(tuple(edge) for edge in move["reversed_edges"])
    switched = replay_q3_critical_spill_switch_move(
        graph,
        solution,
        spill_index=move["spill_index"],
        mode=move["mode"],
        expected_reversed_edges=expected_edges,
    )
    t2 = time.perf_counter()

    expected_after = recipe["expected_after_switch"]
    if switched.official.total_cycles != expected_after["official_cycles"]:
        raise AssertionError("switch recipe official result drifted")
    if switched.safe.total_cycles != expected_after["safe_cycles"]:
        raise AssertionError("switch recipe safe result drifted")
    if switched.changed_positions != expected_after["changed_positions"]:
        raise AssertionError("switch recipe changed-position count drifted")

    recolor = optimize_q3_critical_recolor_greedy(
        graph,
        switched.solution,
        max_rounds=args.recolor_rounds,
        max_targets=args.recolor_targets,
        max_starts=args.recolor_starts,
    )
    t3 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, recolor.final_solution)
    final_q2.require_ok()
    baseline_spills = tuple((s.buf_id, s.new_offset) for s in solution.spills)
    final_spills = tuple((s.buf_id, s.new_offset) for s in recolor.final_solution.spills)
    if final_q2.spill_count != baseline_q2.spill_count:
        raise AssertionError("switch+recolor changed spill count")
    if final_q2.extra_traffic != baseline_q2.extra_traffic:
        raise AssertionError("switch+recolor changed extra traffic")
    if final_spills != baseline_spills:
        raise AssertionError("switch+recolor changed spill record identity/order/offset")
    if not recolor.final_official.ok or not recolor.final_safe.ok:
        raise AssertionError("switch+recolor final timing invalid")
    if recolor.final_official.total_cycles > switched.official.total_cycles:
        raise AssertionError("shallow recolor regressed the strict switch result")

    round_payload = []
    for index, round_result in enumerate(recolor.rounds, start=1):
        round_payload.append(
            {
                "round": index,
                "baseline_official_cycles": round_result.baseline_official.total_cycles,
                "best_official_cycles": round_result.best_official.total_cycles,
                "baseline_safe_cycles": round_result.baseline_safe.total_cycles,
                "best_safe_cycles": round_result.best_safe.total_cycles,
                "improved": round_result.improved,
                "target_buffers": list(round_result.target_buffers),
                "accepted_offset_moves": _accepted_offset_moves(round_result),
                "trial_count": len(round_result.trials),
            }
        )

    payload = {
        "case": snapshot["case"],
        "baseline_official_cycles": baseline_official.total_cycles,
        "baseline_safe_cycles": baseline_safe.total_cycles,
        "switch_official_cycles": switched.official.total_cycles,
        "switch_safe_cycles": switched.safe.total_cycles,
        "switch_improvement_cycles": baseline_official.total_cycles - switched.official.total_cycles,
        "switch_move": {
            "spill_index": move["spill_index"],
            "mode": move["mode"],
            "reversed_edges": [list(edge) for edge in switched.reversed_edges],
            "changed_positions": switched.changed_positions,
        },
        "final_official_cycles": recolor.final_official.total_cycles,
        "final_safe_cycles": recolor.final_safe.total_cycles,
        "recolor_improvement_after_switch": (
            switched.official.total_cycles - recolor.final_official.total_cycles
        ),
        "total_improvement_cycles": (
            baseline_official.total_cycles - recolor.final_official.total_cycles
        ),
        "recolor_accepted_rounds": recolor.accepted_rounds,
        "recolor_rounds_attempted": len(recolor.rounds),
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(recolor.final_safe.physical_overlap_errors),
        "valid": recolor.final_official.ok and recolor.final_safe.ok,
        "snapshot_replay_seconds": round(t1 - t0, 6),
        "switch_replay_seconds": round(t2 - t1, 6),
        "recolor_seconds": round(t3 - t2, 6),
        "total_seconds": round(t3 - t0, 6),
        "rounds": round_payload,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
