from __future__ import annotations

import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph
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
from q3_model import Q3TimingResult, node_cycles
from q3_spill_batch_optimizer import (
    _pipe_predecessor,
    _topological_order,
    critical_spill_candidates,
)


@dataclass(frozen=True, slots=True)
class CycleAwareExchangeTrial:
    spill_index: int
    target_edge: tuple[int, int]
    blocker_edge: tuple[int, int]
    blocker_pipe: str | None
    blocker_node_cycles: int
    witness_path_length: int
    q2_valid: bool
    safe_valid: bool | None
    official_cycles: int | None
    safe_cycles: int | None
    changed_positions: int
    error: str = ""


@dataclass(frozen=True, slots=True)
class CycleAwareExchangeResult:
    baseline_solution: Q2Solution
    baseline_official: Q3TimingResult
    baseline_safe: Q3TimingResult
    best_solution: Q2Solution
    best_official: Q3TimingResult
    best_safe: Q3TimingResult
    best_exchange: tuple[int, tuple[int, int], tuple[int, int]] | None
    trials: tuple[CycleAwareExchangeTrial, ...]

    @property
    def improved(self) -> bool:
        return self.best_official.total_cycles < self.baseline_official.total_cycles


def _find_path(
    nodes: set[int],
    edges: set[tuple[int, int]],
    start: int,
    goal: int,
) -> tuple[int, ...] | None:
    """Return one shortest directed path from start to goal, if present."""
    if start == goal:
        return (start,)
    succ: dict[int, list[int]] = defaultdict(list)
    for u, v in edges:
        if u in nodes and v in nodes:
            succ[u].append(v)
    for values in succ.values():
        values.sort()

    parent: dict[int, int | None] = {start: None}
    queue = deque([start])
    while queue:
        u = queue.popleft()
        for v in succ.get(u, ()):
            if v in parent:
                continue
            parent[v] = u
            if v == goal:
                chain = [goal]
                cur = goal
                while cur != start:
                    prev = parent[cur]
                    if prev is None:
                        raise RuntimeError("path reconstruction lost predecessor")
                    cur = prev
                    chain.append(cur)
                chain.reverse()
                return tuple(chain)
            queue.append(v)
    return None


def search_q3_cycle_aware_spill_exchanges(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_targets: int = 4,
    max_blockers_per_target: int = 8,
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> CycleAwareExchangeResult:
    """Try a minimal two-edge exchange for cycle-blocked critical SPILL_OUT moves.

    For each top-ranked critical SPILL_OUT boundary, first remove its mutable
    predecessor Pipe edge. If another dependency path still runs from the old
    predecessor to the SPILL_OUT, reversing the target edge would create a cycle.
    We then inspect that witness path and pair the target reversal with exactly
    one other mutable Pipe-edge reversal from the path. This is deliberately a
    bounded 2-edge neighborhood rather than an unconstrained cycle repair.

    Every accepted candidate preserves exact SPILL records/count/traffic and must
    pass strict Q2, official-literal, and residency-safe replay.
    """
    if max_targets <= 0 or max_blockers_per_target <= 0:
        raise ValueError("max_targets and max_blockers_per_target must be positive")

    base_q2 = validate_q2_solution(graph, solution)
    base_q2.require_ok()
    if baseline_official is None:
        baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    if baseline_safe is None:
        baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()

    nodes = augmented_nodes(graph, solution)
    node_ids = set(nodes)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    original = original_edges(graph)
    spills = spill_edges(graph, solution, nodes, pos)
    reuse = residency_safe_reuse_edges(graph, solution)
    fixed = original | spills | reuse
    pipes = pipe_edges(solution, nodes)
    base_spills = tuple((spill.buf_id, spill.new_offset) for spill in solution.spills)

    ranked = critical_spill_candidates(
        graph,
        solution,
        baseline_official,
        max_switches=max_targets,
    )

    best_solution = solution
    best_official = baseline_official
    best_safe = baseline_safe
    best_exchange: tuple[int, tuple[int, int], tuple[int, int]] | None = None
    trials: list[CycleAwareExchangeTrial] = []

    for target in ranked:
        prev_out = _pipe_predecessor(solution, nodes, target.out_id)
        if prev_out is None:
            continue
        target_edge = (prev_out, target.out_id)
        if target_edge not in pipes or target_edge in fixed:
            continue

        without_target = set(fixed)
        without_target.update(pipes - {target_edge})
        witness = _find_path(node_ids, without_target, prev_out, target.out_id)
        if witness is None:
            # Simple target reversal is acyclic and belongs to the single-switch
            # operator; do not duplicate that search here.
            continue

        path_edges = tuple(zip(witness, witness[1:]))
        blockers = [
            edge
            for edge in path_edges
            if edge in pipes and edge not in fixed and edge != target_edge
        ]
        blockers = sorted(
            set(blockers),
            key=lambda edge: (
                -node_cycles(nodes[edge[1]]),
                pos[edge[1]],
                edge,
            ),
        )[:max_blockers_per_target]

        for blocker_edge in blockers:
            reverse_edges = {target_edge, blocker_edge}
            try:
                constrained = set(fixed)
                constrained.update(pipes - reverse_edges)
                constrained.update((v, u) for u, v in reverse_edges)
                order = _topological_order(nodes, constrained, pos)
                changed = sum(a != b for a, b in zip(order, solution.schedule))
                candidate_solution = Q2Solution(order, solution.initial_offsets, solution.spills)
                q2 = validate_q2_solution(graph, candidate_solution)
                if not q2.ok:
                    trials.append(
                        CycleAwareExchangeTrial(
                            target.spill_index,
                            target_edge,
                            blocker_edge,
                            nodes[blocker_edge[1]].pipe,
                            node_cycles(nodes[blocker_edge[1]]),
                            len(witness) - 1,
                            False,
                            False,
                            None,
                            None,
                            changed,
                            "; ".join(q2.errors[:2]),
                        )
                    )
                    continue
                if q2.spill_count != base_q2.spill_count or q2.extra_traffic != base_q2.extra_traffic:
                    raise AssertionError("cycle-aware exchange changed Q2 traffic/spill count")
                if tuple((s.buf_id, s.new_offset) for s in candidate_solution.spills) != base_spills:
                    raise AssertionError("cycle-aware exchange changed exact SPILL records")

                official = evaluate_q3_solution(
                    graph,
                    candidate_solution,
                    reuse_mode="official_literal",
                )
                official.require_ok()
                if official.total_cycles > best_official.total_cycles:
                    trials.append(
                        CycleAwareExchangeTrial(
                            target.spill_index,
                            target_edge,
                            blocker_edge,
                            nodes[blocker_edge[1]].pipe,
                            node_cycles(nodes[blocker_edge[1]]),
                            len(witness) - 1,
                            True,
                            None,
                            official.total_cycles,
                            None,
                            changed,
                            "residency-safe replay skipped: official score not competitive",
                        )
                    )
                    continue

                safe = evaluate_q3_solution(
                    graph,
                    candidate_solution,
                    reuse_mode="residency_safe",
                )
                if not safe.ok:
                    trials.append(
                        CycleAwareExchangeTrial(
                            target.spill_index,
                            target_edge,
                            blocker_edge,
                            nodes[blocker_edge[1]].pipe,
                            node_cycles(nodes[blocker_edge[1]]),
                            len(witness) - 1,
                            True,
                            False,
                            official.total_cycles,
                            None,
                            changed,
                            "; ".join(safe.errors[:2]),
                        )
                    )
                    continue

                trials.append(
                    CycleAwareExchangeTrial(
                        target.spill_index,
                        target_edge,
                        blocker_edge,
                        nodes[blocker_edge[1]].pipe,
                        node_cycles(nodes[blocker_edge[1]]),
                        len(witness) - 1,
                        True,
                        True,
                        official.total_cycles,
                        safe.total_cycles,
                        changed,
                    )
                )
                key = (
                    official.total_cycles,
                    safe.total_cycles,
                    target.spill_index,
                    blocker_edge,
                )
                current_key = (
                    best_official.total_cycles,
                    best_safe.total_cycles,
                    best_exchange[0] if best_exchange is not None else 1 << 60,
                    best_exchange[2] if best_exchange is not None else (1 << 60, 1 << 60),
                )
                if key < current_key:
                    best_solution = candidate_solution
                    best_official = official
                    best_safe = safe
                    best_exchange = (target.spill_index, target_edge, blocker_edge)
            except Exception as exc:
                trials.append(
                    CycleAwareExchangeTrial(
                        target.spill_index,
                        target_edge,
                        blocker_edge,
                        nodes[blocker_edge[1]].pipe,
                        node_cycles(nodes[blocker_edge[1]]),
                        len(witness) - 1,
                        False,
                        False,
                        None,
                        None,
                        0,
                        f"{type(exc).__name__}: {exc}",
                    )
                )

    final_q2 = validate_q2_solution(graph, best_solution)
    final_q2.require_ok()
    if final_q2.spill_count != base_q2.spill_count or final_q2.extra_traffic != base_q2.extra_traffic:
        raise AssertionError("cycle-aware exchange final Q2 invariants changed")
    if tuple((s.buf_id, s.new_offset) for s in best_solution.spills) != base_spills:
        raise AssertionError("cycle-aware exchange final SPILL records changed")
    final_official = evaluate_q3_solution(graph, best_solution, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, best_solution, reuse_mode="residency_safe")
    final_safe.require_ok()

    return CycleAwareExchangeResult(
        solution,
        baseline_official,
        baseline_safe,
        best_solution,
        final_official,
        final_safe,
        best_exchange,
        tuple(trials),
    )
