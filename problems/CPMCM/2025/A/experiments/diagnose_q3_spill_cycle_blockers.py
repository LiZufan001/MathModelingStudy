from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from model import ComputeGraph
from parser import load_case
from probe_q3_single_switch_checkpoint import CASES, _read_solution
from q3_dependencies import (
    augmented_nodes,
    original_edges,
    pipe_edges,
    residency_safe_reuse_edges,
    spill_edges,
)
from q3_evaluator import evaluate_q3_solution
from q3_spill_batch_optimizer import _pipe_predecessor, critical_spill_candidates


def _cycle_witness(node_ids: set[int], edges: set[tuple[int, int]]) -> tuple[int, ...] | None:
    """Return one directed cycle without recursion, or None if the graph is acyclic."""
    succ: dict[int, list[int]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in node_ids}
    for u, v in edges:
        if u not in indegree or v not in indegree:
            continue
        succ[u].append(v)
        indegree[v] += 1

    ready = deque(node for node, degree in indegree.items() if degree == 0)
    while ready:
        u = ready.popleft()
        for v in succ.get(u, ()):
            indegree[v] -= 1
            if indegree[v] == 0:
                ready.append(v)

    residual = {node for node, degree in indegree.items() if degree > 0}
    if not residual:
        return None

    state: dict[int, int] = {node: 0 for node in residual}
    parent: dict[int, int | None] = {}
    for start in sorted(residual):
        if state[start] != 0:
            continue
        state[start] = 1
        parent[start] = None
        stack: list[tuple[int, object]] = [
            (start, iter(v for v in succ.get(start, ()) if v in residual))
        ]
        while stack:
            u, iterator = stack[-1]
            try:
                v = next(iterator)
            except StopIteration:
                state[u] = 2
                stack.pop()
                continue
            if state[v] == 0:
                state[v] = 1
                parent[v] = u
                stack.append((v, iter(w for w in succ.get(v, ()) if w in residual)))
                continue
            if state[v] == 1:
                chain = [u]
                cur = u
                while cur != v:
                    p = parent[cur]
                    if p is None:
                        raise RuntimeError("cycle reconstruction lost DFS parent")
                    cur = p
                    chain.append(cur)
                chain.reverse()
                chain.append(v)
                return tuple(chain)
    raise RuntimeError("Kahn residual was non-empty but no cycle witness was found")


def _parse_prefixes(raw: str) -> tuple[int, ...]:
    values = sorted({int(item.strip()) for item in raw.split(",") if item.strip()})
    if not values or values[0] <= 0:
        raise ValueError("prefix sizes must contain positive integers")
    return tuple(values)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Diagnose precedence-cycle blockers for critical-SPILL batch reversals"
    )
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--case", choices=CASES, required=True)
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-switches", type=int, default=64)
    ap.add_argument("--prefix-sizes", default="1,2,4,8,16,24,32,48,64")
    args = ap.parse_args()
    if args.max_switches <= 0:
        raise ValueError("max-switches must be positive")

    graph: ComputeGraph = load_case(args.data_dir, args.case)
    solution = _read_solution(args.input_dir, args.case)
    official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    official.require_ok()

    nodes = augmented_nodes(graph, solution)
    node_ids = set(nodes)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    original = original_edges(graph)
    spills = spill_edges(graph, solution, nodes, pos)
    reuse = residency_safe_reuse_edges(graph, solution)
    pipes = pipe_edges(solution, nodes)
    fixed = original | spills | reuse

    ranked = critical_spill_candidates(
        graph,
        solution,
        official,
        max_switches=args.max_switches,
    )
    mutable: list[tuple[int, tuple[int, int]]] = []
    for candidate in ranked:
        prev_out = _pipe_predecessor(solution, nodes, candidate.out_id)
        if prev_out is None:
            continue
        edge = (prev_out, candidate.out_id)
        if edge in pipes and edge not in fixed:
            mutable.append((candidate.spill_index, edge))

    requested = _parse_prefixes(args.prefix_sizes)
    sizes = sorted({min(size, len(mutable)) for size in requested if mutable})
    trials: list[dict[str, object]] = []
    for size in sizes:
        selected = mutable[:size]
        spill_indices = [item[0] for item in selected]
        reverse_edges = tuple(item[1] for item in selected)
        reverse_set = set(reverse_edges)
        constrained = set(fixed)
        constrained.update(pipes - reverse_set)
        constrained.update((v, u) for u, v in reverse_edges)
        cycle = _cycle_witness(node_ids, constrained)

        witness_edges: list[dict[str, object]] = []
        if cycle is not None:
            reversed_added = {(v, u) for u, v in reverse_edges}
            for u, v in zip(cycle, cycle[1:]):
                classes: list[str] = []
                if (u, v) in original:
                    classes.append("original")
                if (u, v) in spills:
                    classes.append("spill")
                if (u, v) in reuse:
                    classes.append("residency_reuse")
                if (u, v) in pipes:
                    classes.append("pipe_forward")
                if (u, v) in reversed_added:
                    classes.append("pipe_reversed")
                witness_edges.append({"u": u, "v": v, "classes": classes})

        trials.append(
            {
                "prefix_size": size,
                "spill_indices": spill_indices,
                "reverse_edges": [list(edge) for edge in reverse_edges],
                "creates_cycle": cycle is not None,
                "cycle_nodes": [] if cycle is None else list(cycle),
                "cycle_edges": witness_edges,
            }
        )

    payload = {
        "case": args.case,
        "official_cycles": official.total_cycles,
        "critical_path_length": len(official.critical_path),
        "ranked_candidate_count": len(ranked),
        "mutable_candidate_count": len(mutable),
        "mutable_spill_indices": [item[0] for item in mutable],
        "trials": trials,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
