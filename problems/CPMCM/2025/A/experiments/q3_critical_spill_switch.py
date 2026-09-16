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
from q3_dependencies import (
    augmented_nodes,
    original_edges,
    pipe_edges,
    residency_safe_reuse_edges,
    spill_edges,
)
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult, node_cycles


@dataclass(frozen=True, slots=True)
class CriticalSpillSwitchCandidate:
    spill_index: int
    out_id: int
    in_id: int
    left_run_cycles: int
    right_run_cycles: int

    @property
    def combined_run_cycles(self) -> int:
        return self.left_run_cycles + self.right_run_cycles


@dataclass(frozen=True, slots=True)
class CriticalSpillSwitchTrial:
    spill_index: int
    mode: str
    reversed_edges: tuple[tuple[int, int], ...]
    left_run_cycles: int
    right_run_cycles: int
    q2_valid: bool
    safe_valid: bool | None
    official_cycles: int | None
    safe_cycles: int | None
    changed_positions: int
    error: str = ""


@dataclass(frozen=True, slots=True)
class CriticalSpillSwitchResult:
    baseline_solution: Q2Solution
    baseline_official: Q3TimingResult
    baseline_safe: Q3TimingResult
    best_solution: Q2Solution
    best_official: Q3TimingResult
    best_safe: Q3TimingResult
    best_move: tuple[int, str] | None
    candidates: tuple[CriticalSpillSwitchCandidate, ...]
    trials: tuple[CriticalSpillSwitchTrial, ...]

    @property
    def improved(self) -> bool:
        return self.best_official.total_cycles < self.baseline_official.total_cycles


def critical_spill_switch_candidates(
    graph: ComputeGraph,
    solution: Q2Solution,
    official_timing: Q3TimingResult,
    *,
    max_switches: int = 8,
) -> tuple[CriticalSpillSwitchCandidate, ...]:
    """Rank critical SPILL_OUT->SPILL_IN switches by serialized run weight.

    Conv1's saturated critical path is dominated by long MTE3 and MTE2 runs that
    are stitched together by a small number of SPILL dependencies. A switch is
    interesting when the matching SPILL_OUT (MTE3) -> SPILL_IN (MTE2) edge lies
    directly on the official critical path. Rank primarily by the combined cycle
    weight of the contiguous MTE3 run ending at OUT and MTE2 run starting at IN.
    This deliberately surfaces a switch adjacent to one enormous serialized run
    even when the run on the other side is short; those are exactly the boundaries
    that downstream-only and min-side ranking can miss.
    """

    if max_switches <= 0:
        return ()
    nodes = augmented_nodes(graph, solution)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    s_edges = spill_edges(graph, solution, nodes, pos)
    path = official_timing.critical_path
    n = graph.node_count
    ranked: list[tuple[int, int, int, CriticalSpillSwitchCandidate]] = []

    for i, (u, v) in enumerate(zip(path, path[1:])):
        if (u, v) not in s_edges or u < n or v < n:
            continue
        if nodes[u].op != "SPILL_OUT" or nodes[v].op != "SPILL_IN":
            continue
        out_relative = u - n
        in_relative = v - n
        if out_relative % 2 != 0 or in_relative % 2 != 1:
            continue
        spill_index = out_relative // 2
        if in_relative // 2 != spill_index:
            continue
        if nodes[u].pipe != "MTE3" or nodes[v].pipe != "MTE2":
            continue

        left_cycles = 0
        j = i
        while j >= 0 and nodes[path[j]].pipe == "MTE3":
            left_cycles += node_cycles(nodes[path[j]])
            j -= 1
        right_cycles = 0
        j = i + 1
        while j < len(path) and nodes[path[j]].pipe == "MTE2":
            right_cycles += node_cycles(nodes[path[j]])
            j += 1

        candidate = CriticalSpillSwitchCandidate(
            spill_index,
            u,
            v,
            left_cycles,
            right_cycles,
        )
        ranked.append(
            (
                -candidate.combined_run_cycles,
                -max(left_cycles, right_cycles),
                spill_index,
                candidate,
            )
        )

    ranked.sort()
    return tuple(item[-1] for item in ranked[:max_switches])


def _pipe_predecessor(
    solution: Q2Solution,
    nodes,
    node_id: int,
) -> int | None:
    pipe = nodes[node_id].pipe
    if pipe is None:
        return None
    previous: int | None = None
    for current in solution.schedule:
        if nodes[current].pipe != pipe:
            continue
        if current == node_id:
            return previous
        previous = current
    raise ValueError(f"node {node_id} absent from its pipe sequence")


def search_q3_critical_spill_switch_bubbles(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_switches: int = 8,
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> CriticalSpillSwitchResult:
    """Bubble endpoints of high-impact critical SPILL pipe switches one slot earlier.

    For each ranked critical SPILL_OUT(MTE3)->SPILL_IN(MTE2) edge, try three
    fixed-traffic schedule perturbations: move the OUT one MTE3 slot earlier,
    move the IN one MTE2 slot earlier, and move both. Every other same-Pipe
    adjacency remains frozen. Original/SPILL/residency-safe correctness edges
    remain mandatory, and no candidate is accepted before strict Q2, official,
    and residency-safe replay with identical SPILL records and extra traffic.
    """

    if max_switches <= 0:
        raise ValueError("max_switches must be positive")
    base_q2 = validate_q2_solution(graph, solution)
    base_q2.require_ok()
    if baseline_official is None:
        baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    if baseline_safe is None:
        baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()

    nodes = augmented_nodes(graph, solution)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    fixed = (
        original_edges(graph)
        | spill_edges(graph, solution, nodes, pos)
        | residency_safe_reuse_edges(graph, solution)
    )
    pipes = pipe_edges(solution, nodes)
    candidates = critical_spill_switch_candidates(
        graph,
        solution,
        baseline_official,
        max_switches=max_switches,
    )
    base_spills = tuple((spill.buf_id, spill.new_offset) for spill in solution.spills)

    best_solution = solution
    best_official = baseline_official
    best_safe = baseline_safe
    best_move: tuple[int, str] | None = None
    trials: list[CriticalSpillSwitchTrial] = []

    for switch in candidates:
        prev_out = _pipe_predecessor(solution, nodes, switch.out_id)
        prev_in = _pipe_predecessor(solution, nodes, switch.in_id)
        reversible: dict[str, tuple[int, int]] = {}
        if prev_out is not None:
            edge = (prev_out, switch.out_id)
            if edge in pipes and edge not in fixed:
                reversible["out_earlier"] = edge
        if prev_in is not None:
            edge = (prev_in, switch.in_id)
            if edge in pipes and edge not in fixed:
                reversible["in_earlier"] = edge

        modes: list[tuple[str, tuple[tuple[int, int], ...]]] = []
        if "out_earlier" in reversible:
            modes.append(("out_earlier", (reversible["out_earlier"],)))
        if "in_earlier" in reversible:
            modes.append(("in_earlier", (reversible["in_earlier"],)))
        if len(reversible) == 2:
            modes.append(
                (
                    "both_earlier",
                    (reversible["out_earlier"], reversible["in_earlier"]),
                )
            )

        if not modes:
            trials.append(
                CriticalSpillSwitchTrial(
                    switch.spill_index,
                    "no_mutable_endpoint",
                    (),
                    switch.left_run_cycles,
                    switch.right_run_cycles,
                    False,
                    False,
                    None,
                    None,
                    0,
                    "both endpoint predecessor pipe edges are fixed correctness edges",
                )
            )
            continue

        for mode, reverse_edges in modes:
            try:
                constrained = set(fixed)
                constrained.update(pipes - set(reverse_edges))
                constrained.update((v, u) for u, v in reverse_edges)
                order = _topological_order(nodes, constrained, pos)
                changed = sum(a != b for a, b in zip(order, solution.schedule))
                candidate_solution = Q2Solution(order, solution.initial_offsets, solution.spills)
                q2 = validate_q2_solution(graph, candidate_solution)
                if not q2.ok:
                    trials.append(
                        CriticalSpillSwitchTrial(
                            switch.spill_index,
                            mode,
                            reverse_edges,
                            switch.left_run_cycles,
                            switch.right_run_cycles,
                            False,
                            False,
                            None,
                            None,
                            changed,
                            "; ".join(q2.errors[:2]),
                        )
                    )
                    continue
                if q2.extra_traffic != base_q2.extra_traffic or q2.spill_count != base_q2.spill_count:
                    raise AssertionError("critical spill switch changed Q2 traffic/spill count")
                if tuple((s.buf_id, s.new_offset) for s in candidate_solution.spills) != base_spills:
                    raise AssertionError("critical spill switch changed spill record identity/order/offset")

                official = evaluate_q3_solution(
                    graph,
                    candidate_solution,
                    reuse_mode="official_literal",
                )
                official.require_ok()
                if official.total_cycles > best_official.total_cycles:
                    trials.append(
                        CriticalSpillSwitchTrial(
                            switch.spill_index,
                            mode,
                            reverse_edges,
                            switch.left_run_cycles,
                            switch.right_run_cycles,
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
                        CriticalSpillSwitchTrial(
                            switch.spill_index,
                            mode,
                            reverse_edges,
                            switch.left_run_cycles,
                            switch.right_run_cycles,
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
                    CriticalSpillSwitchTrial(
                        switch.spill_index,
                        mode,
                        reverse_edges,
                        switch.left_run_cycles,
                        switch.right_run_cycles,
                        True,
                        True,
                        official.total_cycles,
                        safe.total_cycles,
                        changed,
                    )
                )
                if (official.total_cycles, safe.total_cycles, switch.spill_index, mode) < (
                    best_official.total_cycles,
                    best_safe.total_cycles,
                    best_move[0] if best_move is not None else 1 << 60,
                    best_move[1] if best_move is not None else "~",
                ):
                    best_solution = candidate_solution
                    best_official = official
                    best_safe = safe
                    best_move = (switch.spill_index, mode)
            except Exception as exc:
                trials.append(
                    CriticalSpillSwitchTrial(
                        switch.spill_index,
                        mode,
                        reverse_edges,
                        switch.left_run_cycles,
                        switch.right_run_cycles,
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
    if final_q2.extra_traffic != base_q2.extra_traffic or final_q2.spill_count != base_q2.spill_count:
        raise AssertionError("critical spill switch final Q2 invariants changed")
    if tuple((s.buf_id, s.new_offset) for s in best_solution.spills) != base_spills:
        raise AssertionError("critical spill switch final spill records changed")
    final_official = evaluate_q3_solution(graph, best_solution, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, best_solution, reuse_mode="residency_safe")
    final_safe.require_ok()

    return CriticalSpillSwitchResult(
        solution,
        baseline_official,
        baseline_safe,
        best_solution,
        final_official,
        final_safe,
        best_move,
        candidates,
        tuple(trials),
    )
