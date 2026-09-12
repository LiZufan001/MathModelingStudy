from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph
from q2_model import Q2Solution
from q2_validator import validate_q2_solution
from q3_critical_pipe_swap import _topological_order
from q3_critical_spill_switch import _pipe_predecessor
from q3_dependencies import (
    augmented_nodes,
    original_edges,
    pipe_edges,
    residency_safe_reuse_edges,
    spill_edges,
)
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult


@dataclass(frozen=True, slots=True)
class CriticalSpillSwitchReplay:
    solution: Q2Solution
    official: Q3TimingResult
    safe: Q3TimingResult
    reversed_edges: tuple[tuple[int, int], ...]
    changed_positions: int


def replay_q3_critical_spill_switch_move(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    spill_index: int,
    mode: str,
    expected_reversed_edges: tuple[tuple[int, int], ...] | None = None,
) -> CriticalSpillSwitchReplay:
    """Replay one previously selected critical SPILL switch move exactly.

    This helper is intentionally narrower than the search operator.  It derives
    the current predecessor edges for the requested SPILL record, checks that the
    requested endpoint bubble(s) are still mutable, optionally verifies the exact
    edge recipe, then performs full Q2 + official + residency-safe validation.
    """
    base_q2 = validate_q2_solution(graph, solution)
    base_q2.require_ok()
    if spill_index < 0 or spill_index >= len(solution.spills):
        raise ValueError(f"spill_index {spill_index} is outside 0..{len(solution.spills) - 1}")

    nodes = augmented_nodes(graph, solution)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    n = graph.node_count
    out_id = n + 2 * spill_index
    in_id = out_id + 1
    if out_id not in nodes or in_id not in nodes:
        raise ValueError(f"spill {spill_index} augmented nodes are absent")
    if nodes[out_id].op != "SPILL_OUT" or nodes[in_id].op != "SPILL_IN":
        raise ValueError(f"spill {spill_index} augmented node roles changed")
    if nodes[out_id].pipe != "MTE3" or nodes[in_id].pipe != "MTE2":
        raise ValueError(f"spill {spill_index} augmented pipe roles changed")

    fixed = (
        original_edges(graph)
        | spill_edges(graph, solution, nodes, pos)
        | residency_safe_reuse_edges(graph, solution)
    )
    pipes = pipe_edges(solution, nodes)

    prev_out = _pipe_predecessor(solution, nodes, out_id)
    prev_in = _pipe_predecessor(solution, nodes, in_id)
    endpoint_edges: dict[str, tuple[int, int]] = {}
    if prev_out is not None:
        endpoint_edges["out_earlier"] = (prev_out, out_id)
    if prev_in is not None:
        endpoint_edges["in_earlier"] = (prev_in, in_id)

    if mode == "out_earlier":
        names = ("out_earlier",)
    elif mode == "in_earlier":
        names = ("in_earlier",)
    elif mode == "both_earlier":
        names = ("out_earlier", "in_earlier")
    else:
        raise ValueError(f"unsupported critical spill switch mode: {mode}")

    reverse_edges: list[tuple[int, int]] = []
    for name in names:
        edge = endpoint_edges.get(name)
        if edge is None:
            raise ValueError(f"{name} has no same-pipe predecessor")
        if edge not in pipes:
            raise ValueError(f"{name} edge {edge} is not a current same-pipe adjacency")
        if edge in fixed:
            raise ValueError(f"{name} edge {edge} is a fixed correctness edge")
        reverse_edges.append(edge)

    reversed_tuple = tuple(reverse_edges)
    if expected_reversed_edges is not None and reversed_tuple != expected_reversed_edges:
        raise AssertionError(
            f"critical spill switch recipe drifted: expected {expected_reversed_edges}, got {reversed_tuple}"
        )

    constrained = set(fixed)
    constrained.update(pipes - set(reversed_tuple))
    constrained.update((v, u) for u, v in reversed_tuple)
    order = _topological_order(nodes, constrained, pos)
    candidate = Q2Solution(order, solution.initial_offsets, solution.spills)

    q2 = validate_q2_solution(graph, candidate)
    q2.require_ok()
    if q2.extra_traffic != base_q2.extra_traffic or q2.spill_count != base_q2.spill_count:
        raise AssertionError("replayed critical spill switch changed Q2 traffic/spill count")
    base_spills = tuple((s.buf_id, s.new_offset) for s in solution.spills)
    candidate_spills = tuple((s.buf_id, s.new_offset) for s in candidate.spills)
    if candidate_spills != base_spills:
        raise AssertionError("replayed critical spill switch changed spill records")

    official = evaluate_q3_solution(graph, candidate, reuse_mode="official_literal")
    official.require_ok()
    safe = evaluate_q3_solution(graph, candidate, reuse_mode="residency_safe")
    safe.require_ok()

    return CriticalSpillSwitchReplay(
        candidate,
        official,
        safe,
        reversed_tuple,
        sum(a != b for a, b in zip(candidate.schedule, solution.schedule)),
    )
