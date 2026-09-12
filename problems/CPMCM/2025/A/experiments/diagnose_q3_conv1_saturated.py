from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from parser import load_case
from q2_model import Q2Solution
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_dependencies import (
    augmented_nodes,
    official_literal_reuse_edges,
    original_edges,
    pipe_edges,
    spill_edges,
)
from q3_evaluator import evaluate_q3_solution
from q3_model import node_cycles
from q3_official_optimizer import optimize_q3_official_zero_traffic


def _sha256_ints(values: tuple[int, ...]) -> str:
    h = hashlib.sha256()
    for value in values:
        h.update(str(value).encode("ascii"))
        h.update(b",")
    return h.hexdigest()


def _classify_critical_path(graph, solution: Q2Solution, timing):
    nodes = augmented_nodes(graph, solution)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    base = original_edges(graph)
    spill = spill_edges(graph, solution, nodes, pos)
    reuse = official_literal_reuse_edges(graph, solution, pos)
    pipe = pipe_edges(solution, nodes)

    combo_counts: Counter[str] = Counter()
    membership_counts: Counter[str] = Counter()
    op_counts: Counter[str] = Counter()
    pipe_counts: Counter[str] = Counter()
    pipe_only = []
    edge_rows = []

    for node_id in timing.critical_path:
        node = nodes[node_id]
        op_counts[node.op] += 1
        if node.pipe is not None:
            pipe_counts[node.pipe] += 1

    for u, v in zip(timing.critical_path, timing.critical_path[1:]):
        labels = []
        edge = (u, v)
        if edge in base:
            labels.append("original")
        if edge in spill:
            labels.append("spill")
        if edge in reuse:
            labels.append("reuse")
        if edge in pipe:
            labels.append("pipe")
        if not labels:
            labels.append("unknown")
        for label in labels:
            membership_counts[label] += 1
        combo = "+".join(labels)
        combo_counts[combo] += 1
        un = nodes[u]
        vn = nodes[v]
        row = {
            "u": u,
            "v": v,
            "labels": labels,
            "u_op": un.op,
            "v_op": vn.op,
            "u_pipe": un.pipe,
            "v_pipe": vn.pipe,
            "u_cycles": node_cycles(un),
            "v_cycles": node_cycles(vn),
            "u_finish": timing.finish_times[u],
            "v_start": timing.start_times[v],
        }
        edge_rows.append(row)
        if labels == ["pipe"]:
            pipe_only.append(row)

    return {
        "critical_path_nodes": len(timing.critical_path),
        "critical_path_edges": max(0, len(timing.critical_path) - 1),
        "edge_membership_counts": dict(sorted(membership_counts.items())),
        "edge_combo_counts": dict(sorted(combo_counts.items())),
        "critical_node_op_counts": dict(sorted(op_counts.items())),
        "critical_node_pipe_counts": dict(sorted(pipe_counts.items())),
        "pipe_only_edge_count": len(pipe_only),
        "pipe_only_edges": pipe_only,
        "edges": edge_rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--case", default="Conv_Case1")
    ap.add_argument("--recolor-rounds", type=int, default=24)
    args = ap.parse_args()

    graph = load_case(args.data_dir, args.case)
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()
    promoted_solution = promoted.allocation.solution

    t0 = time.perf_counter()
    saturated = optimize_q3_official_zero_traffic(
        graph,
        promoted_solution,
        max_rounds=2,
        recolor_max_rounds=args.recolor_rounds,
        recolor_max_targets=6,
        recolor_max_starts=12,
    )
    t1 = time.perf_counter()
    saturated_q2 = validate_q2_solution(graph, saturated.solution)
    saturated_q2.require_ok()

    # Rebuild the deterministic production core without deep recolor, then prove
    # that a small offset override map reproduces the saturated solution exactly.
    core = optimize_q3_official_zero_traffic(
        graph,
        promoted_solution,
        max_rounds=2,
        recolor_max_rounds=0,
    )
    t2 = time.perf_counter()
    if core.solution.schedule != saturated.solution.schedule:
        raise AssertionError("deep recolor unexpectedly changed the accepted schedule")
    if tuple(s.buf_id for s in core.solution.spills) != tuple(s.buf_id for s in saturated.solution.spills):
        raise AssertionError("deep recolor unexpectedly changed spill identity/order")
    if tuple(s.new_offset for s in core.solution.spills) != tuple(s.new_offset for s in saturated.solution.spills):
        raise AssertionError("deep recolor unexpectedly changed spill offsets")

    overrides = {
        buf_id: saturated.solution.initial_offsets[buf_id]
        for buf_id, old in core.solution.initial_offsets.items()
        if saturated.solution.initial_offsets[buf_id] != old
    }
    replay_offsets = dict(core.solution.initial_offsets)
    replay_offsets.update(overrides)
    replayed = Q2Solution(core.solution.schedule, replay_offsets, core.solution.spills)
    replay_q2 = validate_q2_solution(graph, replayed)
    replay_q2.require_ok()
    replay_official = evaluate_q3_solution(graph, replayed, reuse_mode="official_literal")
    replay_official.require_ok()
    replay_safe = evaluate_q3_solution(graph, replayed, reuse_mode="residency_safe")
    replay_safe.require_ok()
    if replay_official.total_cycles != saturated.official_timing.total_cycles:
        raise AssertionError("offset override replay does not reproduce saturated official cycles")
    if replay_safe.total_cycles != saturated.safe_timing.total_cycles:
        raise AssertionError("offset override replay does not reproduce saturated safe cycles")

    diagnostic = _classify_critical_path(graph, saturated.solution, saturated.official_timing)
    payload = {
        "case": args.case,
        "promoted_official_cycles": evaluate_q3_solution(
            graph, promoted_solution, reuse_mode="official_literal"
        ).total_cycles,
        "core_official_cycles": core.official_timing.total_cycles,
        "core_safe_cycles": core.safe_timing.total_cycles,
        "saturated_official_cycles": saturated.official_timing.total_cycles,
        "saturated_safe_cycles": saturated.safe_timing.total_cycles,
        "spill_count": saturated_q2.spill_count,
        "extra_traffic": saturated_q2.extra_traffic,
        "safe_overlap_errors": len(saturated.safe_timing.physical_overlap_errors),
        "valid": saturated.official_timing.ok and saturated.safe_timing.ok,
        "offset_override_count": len(overrides),
        "offset_overrides": {str(k): v for k, v in sorted(overrides.items())},
        "schedule_sha256": _sha256_ints(saturated.solution.schedule),
        "replay_official_cycles": replay_official.total_cycles,
        "replay_safe_cycles": replay_safe.total_cycles,
        "saturation_seconds": round(t1 - t0, 6),
        "core_rebuild_seconds": round(t2 - t1, 6),
        "total_seconds": round(t2 - t0, 6),
        "diagnostic": diagnostic,
    }
    if args.case == "Conv_Case1":
        if payload["saturated_official_cycles"] != 3781664:
            raise AssertionError("Conv1 saturated official regression")
        if payload["saturated_safe_cycles"] != 4113775:
            raise AssertionError("Conv1 saturated safe regression")
        if payload["safe_overlap_errors"] != 0:
            raise AssertionError("Conv1 saturated solution lost residency safety")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compact = {k: v for k, v in payload.items() if k != "diagnostic"}
    compact["critical_edge_membership_counts"] = diagnostic["edge_membership_counts"]
    compact["critical_edge_combo_counts"] = diagnostic["edge_combo_counts"]
    compact["pipe_only_edge_count"] = diagnostic["pipe_only_edge_count"]
    print(json.dumps(compact, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
