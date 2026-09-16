from __future__ import annotations

from typing import Mapping

from model import ComputeGraph
from q2_model import CACHE_CAPACITIES, Q2Solution
from q2_validator import validate_q2_solution
from q3_audit import audit_physical_time_overlap, physical_epochs
from q3_dependencies import (
    augmented_nodes,
    official_literal_reuse_edges,
    original_edges,
    pipe_edges,
    residency_epoch_edges,
    residency_safe_reuse_edges,
    spill_edges,
)
from q3_model import Q3DualTimingResult, Q3TimingResult, ReuseMode, node_cycles


def _empty_result(reuse_mode: ReuseMode, errors: tuple[str, ...]) -> Q3TimingResult:
    return Q3TimingResult(
        False,
        errors,
        reuse_mode,
        0,
        {},
        {},
        (),
        {},
        {},
        0,
        0,
        0,
        0,
        (),
    )


def evaluate_q3_solution(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    reuse_mode: ReuseMode = "residency_safe",
    capacities: Mapping[str, int] = CACHE_CAPACITIES,
) -> Q3TimingResult:
    """Evaluate Appendix-C ASAP timing for a strict Q2/Q3 solution.

    The submitted global sequence fixes instruction order *within each Pipe*.
    Different Pipes remain parallel. Timing edges are the union of original DAG
    dependencies, Appendix-B SPILL dependencies, address-reuse dependencies, and
    same-Pipe serialization. Residency-safe mode additionally preserves each
    physical epoch's acquire->release lifetime; those safety edges are deliberately
    excluded from reuse-edge statistics.
    """

    q2 = validate_q2_solution(graph, solution, capacities)
    if not q2.ok:
        return _empty_result(
            reuse_mode,
            tuple(f"Q2 invalid: {error}" for error in q2.errors),
        )

    try:
        nodes = augmented_nodes(graph, solution)
        pos = {node_id: index for index, node_id in enumerate(solution.schedule)}

        base_edges = original_edges(graph)
        s_edges = spill_edges(graph, solution, nodes, pos)
        if reuse_mode == "official_literal":
            r_edges = official_literal_reuse_edges(graph, solution, pos, capacities)
            lifetime_edges: set[tuple[int, int]] = set()
        elif reuse_mode == "residency_safe":
            r_edges = residency_safe_reuse_edges(graph, solution, capacities)
            lifetime_edges = residency_epoch_edges(graph, solution)
        else:
            raise ValueError(f"unknown reuse_mode {reuse_mode!r}")
        p_edges = pipe_edges(solution, nodes)
        all_edges = base_edges | s_edges | r_edges | lifetime_edges | p_edges

        predecessors: dict[int, set[int]] = {node_id: set() for node_id in nodes}
        errors: list[str] = []
        for u, v in all_edges:
            if u not in pos or v not in pos:
                errors.append(f"timing edge ({u}->{v}) references node absent from schedule")
                continue
            if pos[u] >= pos[v]:
                errors.append(
                    f"timing edge ({u}->{v}) contradicts schedule positions "
                    f"{pos[u]} >= {pos[v]}"
                )
                if len(errors) >= 40:
                    break
            predecessors[v].add(u)
        if errors:
            return Q3TimingResult(
                False,
                tuple(errors),
                reuse_mode,
                0,
                {},
                {},
                (),
                {},
                {},
                len(base_edges),
                len(s_edges),
                len(r_edges),
                len(p_edges),
                (),
            )

        start_times: dict[int, int] = {}
        finish_times: dict[int, int] = {}
        parent: dict[int, int | None] = {}
        pipe_busy: dict[str, int] = {}

        for node_id in solution.schedule:
            preds = predecessors[node_id]
            if preds:
                critical_parent = min(
                    preds,
                    key=lambda pred: (-finish_times[pred], pred),
                )
                start = finish_times[critical_parent]
                parent[node_id] = critical_parent
            else:
                start = 0
                parent[node_id] = None
            cycles = node_cycles(nodes[node_id])
            finish = start + cycles
            start_times[node_id] = start
            finish_times[node_id] = finish
            pipe = nodes[node_id].pipe
            if pipe is not None:
                pipe_busy[pipe] = pipe_busy.get(pipe, 0) + cycles

        if finish_times:
            terminal = min(
                finish_times,
                key=lambda node_id: (-finish_times[node_id], node_id),
            )
            total_cycles = finish_times[terminal]
        else:
            terminal = None
            total_cycles = 0

        critical_reversed: list[int] = []
        cursor = terminal
        while cursor is not None:
            critical_reversed.append(cursor)
            cursor = parent[cursor]
        critical_path = tuple(reversed(critical_reversed))

        utilization = {
            pipe: (busy / total_cycles if total_cycles else 0.0)
            for pipe, busy in sorted(pipe_busy.items())
        }
        overlap_errors = audit_physical_time_overlap(
            physical_epochs(graph, solution),
            start_times,
            finish_times,
            capacities,
        )
        if reuse_mode == "residency_safe" and overlap_errors:
            errors.extend(
                f"residency-safe timing overlap: {message}"
                for message in overlap_errors
            )

        return Q3TimingResult(
            not errors,
            tuple(errors),
            reuse_mode,
            total_cycles,
            start_times,
            finish_times,
            critical_path,
            pipe_busy,
            utilization,
            len(base_edges),
            len(s_edges),
            len(r_edges),
            len(p_edges),
            overlap_errors,
        )
    except Exception as exc:
        return _empty_result(reuse_mode, (f"{type(exc).__name__}: {exc}",))


def evaluate_q3_both(
    graph: ComputeGraph,
    solution: Q2Solution,
    capacities: Mapping[str, int] = CACHE_CAPACITIES,
) -> Q3DualTimingResult:
    return Q3DualTimingResult(
        official_literal=evaluate_q3_solution(
            graph,
            solution,
            reuse_mode="official_literal",
            capacities=capacities,
        ),
        residency_safe=evaluate_q3_solution(
            graph,
            solution,
            reuse_mode="residency_safe",
            capacities=capacities,
        ),
    )
