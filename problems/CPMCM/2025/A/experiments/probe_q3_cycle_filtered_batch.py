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

from model import ComputeGraph
from parser import load_case
from probe_q3_single_switch_checkpoint import _read_solution, _write_solution
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_dependencies import (
    augmented_nodes,
    original_edges,
    pipe_edges,
    residency_safe_reuse_edges,
    spill_edges,
)
from q3_evaluator import evaluate_q3_solution
from q3_spill_batch_optimizer import _pipe_predecessor, _topological_order, critical_spill_candidates


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe critical-SPILL prefixes after filtering singleton-cycle blockers")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--expected-official", type=int)
    ap.add_argument("--max-switches", type=int, default=16)
    args = ap.parse_args()
    if args.max_switches <= 0:
        raise ValueError("max-switches must be positive")

    graph: ComputeGraph = load_case(args.data_dir, args.case)
    solution = _read_solution(args.input_dir, args.case)
    base_q2 = validate_q2_solution(graph, solution)
    base_q2.require_ok()
    base_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    base_official.require_ok()
    base_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    base_safe.require_ok()
    if args.expected_official is not None and base_official.total_cycles != args.expected_official:
        raise AssertionError(
            f"input official timing drifted: {base_official.total_cycles} != {args.expected_official}"
        )

    nodes = augmented_nodes(graph, solution)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    fixed = (
        original_edges(graph)
        | spill_edges(graph, solution, nodes, pos)
        | residency_safe_reuse_edges(graph, solution)
    )
    pipes = pipe_edges(solution, nodes)
    base_spills = tuple((s.buf_id, s.new_offset) for s in solution.spills)

    ranked = critical_spill_candidates(
        graph,
        solution,
        base_official,
        max_switches=args.max_switches,
    )

    filtered_out: list[dict[str, object]] = []
    eligible: list[tuple[int, tuple[int, int]]] = []
    for candidate in ranked:
        prev = _pipe_predecessor(solution, nodes, candidate.out_id)
        if prev is None:
            filtered_out.append({"spill_index": candidate.spill_index, "reason": "no_pipe_predecessor"})
            continue
        edge = (prev, candidate.out_id)
        if edge not in pipes or edge in fixed:
            filtered_out.append({"spill_index": candidate.spill_index, "edge": list(edge), "reason": "not_mutable"})
            continue
        constrained = set(fixed)
        constrained.update(pipes - {edge})
        constrained.add((edge[1], edge[0]))
        try:
            _topological_order(nodes, constrained, pos)
        except ValueError as exc:
            filtered_out.append(
                {
                    "spill_index": candidate.spill_index,
                    "edge": list(edge),
                    "reason": "singleton_precedence_cycle",
                    "error": str(exc),
                }
            )
            continue
        eligible.append((candidate.spill_index, edge))

    requested = (1, 2, 4, 8, 16)
    sizes = sorted({min(size, len(eligible)) for size in requested if eligible})
    trials: list[dict[str, object]] = []
    best_solution = solution
    best_official = base_official
    best_safe = base_safe
    best_prefix: int | None = None
    t0 = time.perf_counter()

    for size in sizes:
        selected = eligible[:size]
        spill_indices = tuple(item[0] for item in selected)
        reverse_edges = tuple(item[1] for item in selected)
        record: dict[str, object] = {
            "prefix_size": size,
            "spill_indices": list(spill_indices),
            "reversed_edges": [list(edge) for edge in reverse_edges],
        }
        try:
            constrained = set(fixed)
            constrained.update(pipes - set(reverse_edges))
            constrained.update((v, u) for u, v in reverse_edges)
            order = _topological_order(nodes, constrained, pos)
            candidate_solution = Q2Solution(order, solution.initial_offsets, solution.spills)
            q2 = validate_q2_solution(graph, candidate_solution)
            q2.require_ok()
            if q2.spill_count != base_q2.spill_count or q2.extra_traffic != base_q2.extra_traffic:
                raise AssertionError("filtered batch changed Q2 spill/traffic metrics")
            if tuple((s.buf_id, s.new_offset) for s in candidate_solution.spills) != base_spills:
                raise AssertionError("filtered batch changed exact SPILL records")
            official = evaluate_q3_solution(graph, candidate_solution, reuse_mode="official_literal")
            official.require_ok()
            record.update(
                {
                    "q2_valid": True,
                    "official_cycles": official.total_cycles,
                    "improvement_cycles": base_official.total_cycles - official.total_cycles,
                    "changed_positions": sum(a != b for a, b in zip(order, solution.schedule)),
                }
            )
            if official.total_cycles <= base_official.total_cycles:
                safe = evaluate_q3_solution(graph, candidate_solution, reuse_mode="residency_safe")
                safe.require_ok()
                record.update(
                    {
                        "safe_valid": True,
                        "safe_cycles": safe.total_cycles,
                        "safe_overlap_errors": len(safe.physical_overlap_errors),
                    }
                )
                if official.total_cycles < best_official.total_cycles or (
                    official.total_cycles == best_official.total_cycles
                    and safe.total_cycles < best_safe.total_cycles
                ):
                    best_solution = candidate_solution
                    best_official = official
                    best_safe = safe
                    best_prefix = size
            else:
                record.update({"safe_valid": None, "safe_cycles": None})
        except Exception as exc:
            record.update(
                {
                    "q2_valid": False,
                    "safe_valid": False,
                    "official_cycles": None,
                    "safe_cycles": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        trials.append(record)

    final_q2 = validate_q2_solution(graph, best_solution)
    final_q2.require_ok()
    if final_q2.spill_count != base_q2.spill_count or final_q2.extra_traffic != base_q2.extra_traffic:
        raise AssertionError("filtered batch final Q2 metrics changed")
    if tuple((s.buf_id, s.new_offset) for s in best_solution.spills) != base_spills:
        raise AssertionError("filtered batch final SPILL records changed")
    final_official = evaluate_q3_solution(graph, best_solution, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, best_solution, reuse_mode="residency_safe")
    final_safe.require_ok()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_solution(args.out_dir / "next", args.case, best_solution)
    payload = {
        "case": args.case,
        "operator": "cycle_filtered_critical_spill_prefix_batch",
        "baseline": {
            "official_cycles": base_official.total_cycles,
            "safe_cycles": base_safe.total_cycles,
            "spill_count": base_q2.spill_count,
            "extra_traffic": base_q2.extra_traffic,
        },
        "ranked_candidate_count": len(ranked),
        "filtered_out": filtered_out,
        "eligible_spill_indices": [item[0] for item in eligible],
        "trials": trials,
        "result": {
            "improved": final_official.total_cycles < base_official.total_cycles,
            "best_prefix_size": best_prefix,
            "official_cycles": final_official.total_cycles,
            "safe_cycles": final_safe.total_cycles,
            "improvement_cycles": base_official.total_cycles - final_official.total_cycles,
            "spill_count": final_q2.spill_count,
            "extra_traffic": final_q2.extra_traffic,
            "safe_overlap_errors": len(final_safe.physical_overlap_errors),
            "valid": final_official.ok and final_safe.ok,
        },
        "seconds": round(time.perf_counter() - t0, 6),
        "checkpoint": "next",
    }
    (args.out_dir / "cycle-filtered-batch.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
