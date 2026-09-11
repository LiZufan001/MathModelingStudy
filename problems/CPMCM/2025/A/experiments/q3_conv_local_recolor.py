from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph
from q2_model import CACHE_CAPACITIES, Q2Solution
from q2_validator import validate_q2_solution
from q3_audit import physical_epochs
from q3_dependencies import official_literal_reuse_edges
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult


@dataclass(frozen=True, slots=True)
class LocalRecolorTrial:
    buf_id: int
    old_offset: int
    new_offset: int
    q2_valid: bool
    safe_valid: bool | None
    official_cycles: int | None
    safe_cycles: int | None
    official_reuse_edges: int | None
    error: str = ""


@dataclass(frozen=True, slots=True)
class LocalRecolorSearchResult:
    baseline_solution: Q2Solution
    baseline_official: Q3TimingResult
    baseline_safe: Q3TimingResult
    best_solution: Q2Solution
    best_official: Q3TimingResult
    best_safe: Q3TimingResult
    target_buffers: tuple[int, ...]
    trials: tuple[LocalRecolorTrial, ...]

    @property
    def improved(self) -> bool:
        return self.best_official.total_cycles < self.baseline_official.total_cycles


def critical_reuse_targets(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_targets: int = 6,
    official_timing: Q3TimingResult | None = None,
) -> tuple[int, ...]:
    """Return buffers whose initial ALLOC is on a literal-reuse critical edge.

    Targets are ordered from the tail of the current official critical path toward
    the head.  This keeps the search focused on serialization that contributes to
    the makespan, rather than every reuse edge in the graph.
    """

    if max_targets <= 0:
        return ()
    timing = official_timing
    if timing is None:
        timing = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
        timing.require_ok()
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    reuse = official_literal_reuse_edges(graph, solution, pos)
    path_edges = list(zip(timing.critical_path, timing.critical_path[1:]))
    out: list[int] = []
    seen: set[int] = set()
    for u, v in reversed(path_edges):
        if (u, v) not in reuse:
            continue
        node = graph.nodes.get(v)
        if node is None or not node.is_alloc or node.buf_id is None:
            continue
        if node.buf_id in seen:
            continue
        seen.add(node.buf_id)
        out.append(node.buf_id)
        if len(out) >= max_targets:
            break
    return tuple(out)


def _address_pressure(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    target_buf: int,
) -> tuple[str, int, list[int]]:
    alloc = graph.alloc_node_for_buffer(target_buf)
    if alloc is None or alloc.memory_type is None or alloc.size is None:
        raise ValueError(f"buffer {target_buf} lacks complete ALLOC metadata")
    memory_type = alloc.memory_type
    capacity = CACHE_CAPACITIES[memory_type]
    pressure = [0] * capacity

    def add(buf_id: int, start: int) -> None:
        if buf_id == target_buf:
            return
        other = graph.alloc_node_for_buffer(buf_id)
        if other is None or other.memory_type != memory_type or other.size is None:
            return
        end = start + other.size
        if start < 0 or end > capacity:
            return
        for address in range(start, end):
            pressure[address] += 1

    for buf_id, start in solution.initial_offsets.items():
        add(buf_id, start)
    for spill in solution.spills:
        add(spill.buf_id, spill.new_offset)
    return memory_type, alloc.size, pressure


def _blocked_initial_bytes(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    target_buf: int,
) -> list[int]:
    """Return a byte mask blocked during the target's initial sequential epoch.

    This is an exact *necessary* prefilter for an initial-offset-only move under the
    submitted Q2 event stream.  Any other residency epoch whose schedule-position
    interval overlaps the target initial epoch must occupy disjoint bytes.  The
    final winner still goes through the independent full Q2 replay and both Q3
    evaluators; this mask only avoids replaying candidates that are guaranteed to
    fail physical overlap.
    """

    alloc = graph.alloc_node_for_buffer(target_buf)
    if alloc is None or alloc.memory_type is None:
        raise ValueError(f"buffer {target_buf} lacks complete ALLOC metadata")
    memory_type = alloc.memory_type
    capacity = CACHE_CAPACITIES[memory_type]
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    epochs = physical_epochs(graph, solution)
    target = next(
        (
            epoch
            for epoch in epochs
            if epoch.buf_id == target_buf and epoch.acquire_node == alloc.id
        ),
        None,
    )
    if target is None:
        raise ValueError(f"buffer {target_buf} has no initial residency epoch")
    target_a = pos[target.acquire_node]
    target_b = pos[target.release_node]
    blocked = [0] * capacity

    for epoch in epochs:
        if epoch.buf_id == target_buf or epoch.memory_type != memory_type:
            continue
        other_a = pos[epoch.acquire_node]
        other_b = pos[epoch.release_node]
        if max(target_a, other_a) >= min(target_b, other_b):
            continue
        for address in range(epoch.start, epoch.end):
            blocked[address] = 1
    return blocked


def candidate_initial_offsets(
    graph: ComputeGraph,
    solution: Q2Solution,
    buf_id: int,
    *,
    max_starts: int = 12,
) -> tuple[int, ...]:
    """Propose diverse low-history-pressure, sequentially feasible offsets.

    The pressure score counts how often bytes are occupied by *other* initial/SPILL
    residency epochs.  Before ranking, a schedule-position residency mask removes
    every start that is guaranteed to overlap a simultaneously resident epoch.
    This reduces expensive full replays without changing the final correctness
    gate or encoding any case/operator names.
    """

    if max_starts <= 0:
        return ()
    alloc = graph.alloc_node_for_buffer(buf_id)
    if alloc is None or alloc.memory_type is None or alloc.size is None:
        raise ValueError(f"buffer {buf_id} lacks complete ALLOC metadata")
    _, size, pressure = _address_pressure(graph, solution, target_buf=buf_id)
    blocked = _blocked_initial_bytes(graph, solution, target_buf=buf_id)
    capacity = CACHE_CAPACITIES[alloc.memory_type]
    current = solution.initial_offsets[buf_id]
    if size == 0 or size > capacity:
        return ()

    pressure_prefix = [0]
    blocked_prefix = [0]
    for value, unavailable in zip(pressure, blocked):
        pressure_prefix.append(pressure_prefix[-1] + value)
        blocked_prefix.append(blocked_prefix[-1] + unavailable)

    scored: list[tuple[int, int, int]] = []
    for start in range(0, capacity - size + 1):
        if start == current:
            continue
        if blocked_prefix[start + size] - blocked_prefix[start] != 0:
            continue
        score = pressure_prefix[start + size] - pressure_prefix[start]
        scored.append((score, abs(start - current), start))
    scored.sort()

    # Keep neighbouring starts from consuming the whole budget.  The pressure and
    # overlap signatures are piecewise constant between placement boundaries, so
    # spatial diversity gives more distinct reuse patterns per strict replay.
    min_gap = max(1, size // 4)
    chosen: list[int] = []
    for _, _, start in scored:
        if all(abs(start - other) >= min_gap for other in chosen):
            chosen.append(start)
            if len(chosen) >= max_starts:
                break
    if len(chosen) < max_starts:
        for _, _, start in scored:
            if start not in chosen:
                chosen.append(start)
                if len(chosen) >= max_starts:
                    break
    return tuple(chosen)


def move_initial_offset(
    solution: Q2Solution,
    buf_id: int,
    new_offset: int,
) -> Q2Solution:
    offsets = dict(solution.initial_offsets)
    if buf_id not in offsets:
        raise ValueError(f"buffer {buf_id} has no initial offset")
    offsets[buf_id] = new_offset
    return Q2Solution(solution.schedule, offsets, solution.spills)


def search_q3_critical_recolor(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_targets: int = 6,
    max_starts: int = 12,
) -> LocalRecolorSearchResult:
    """Search single-buffer initial-offset moves on critical literal reuse edges.

    SPILL identity/order/offsets and the global schedule are frozen.  Every
    candidate first enters the official evaluator, which already performs a full
    independent Q2 replay.  The more expensive residency-safe evaluator is only
    run for candidates that strictly beat the current official best.  The final
    winner is replayed once more by the standalone Q2 validator.
    """

    base_q2 = validate_q2_solution(graph, solution)
    base_q2.require_ok()
    baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()
    baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    base_spill_buffers = tuple(spill.buf_id for spill in solution.spills)

    targets = critical_reuse_targets(
        graph,
        solution,
        max_targets=max_targets,
        official_timing=baseline_official,
    )
    best_solution = solution
    best_safe = baseline_safe
    best_official = baseline_official
    trials: list[LocalRecolorTrial] = []

    for buf_id in targets:
        old_offset = solution.initial_offsets[buf_id]
        for new_offset in candidate_initial_offsets(
            graph,
            solution,
            buf_id,
            max_starts=max_starts,
        ):
            candidate = move_initial_offset(solution, buf_id, new_offset)
            try:
                # official evaluator includes strict Q2 replay internally, so do
                # not redundantly validate the same candidate before this call.
                official = evaluate_q3_solution(
                    graph,
                    candidate,
                    reuse_mode="official_literal",
                )
                if not official.ok:
                    q2_valid = not any(
                        error.startswith("Q2 invalid:") for error in official.errors
                    )
                    trials.append(
                        LocalRecolorTrial(
                            buf_id,
                            old_offset,
                            new_offset,
                            q2_valid,
                            None,
                            None,
                            None,
                            None,
                            "; ".join(official.errors[:2]),
                        )
                    )
                    continue

                # No safe replay is needed if this candidate cannot become the
                # official winner.  Safety remains a hard gate for every candidate
                # that is actually competitive for acceptance.
                if official.total_cycles >= best_official.total_cycles:
                    trials.append(
                        LocalRecolorTrial(
                            buf_id,
                            old_offset,
                            new_offset,
                            True,
                            None,
                            official.total_cycles,
                            None,
                            official.reuse_edge_count,
                            "safe replay skipped: not official-competitive",
                        )
                    )
                    continue

                safe = evaluate_q3_solution(
                    graph,
                    candidate,
                    reuse_mode="residency_safe",
                )
                if not safe.ok:
                    trials.append(
                        LocalRecolorTrial(
                            buf_id,
                            old_offset,
                            new_offset,
                            True,
                            False,
                            official.total_cycles,
                            None,
                            official.reuse_edge_count,
                            "; ".join(safe.errors[:2]),
                        )
                    )
                    continue

                trials.append(
                    LocalRecolorTrial(
                        buf_id,
                        old_offset,
                        new_offset,
                        True,
                        True,
                        official.total_cycles,
                        safe.total_cycles,
                        official.reuse_edge_count,
                    )
                )
                best_solution = candidate
                best_safe = safe
                best_official = official
            except Exception as exc:
                trials.append(
                    LocalRecolorTrial(
                        buf_id,
                        old_offset,
                        new_offset,
                        False,
                        None,
                        None,
                        None,
                        None,
                        f"{type(exc).__name__}: {exc}",
                    )
                )

    final_q2 = validate_q2_solution(graph, best_solution)
    final_q2.require_ok()
    if final_q2.extra_traffic != base_q2.extra_traffic:
        raise AssertionError("local recolor changed extra traffic")
    if final_q2.spill_count != base_q2.spill_count:
        raise AssertionError("local recolor changed spill count")
    if tuple(spill.buf_id for spill in best_solution.spills) != base_spill_buffers:
        raise AssertionError("local recolor changed spill victim identity/order")

    return LocalRecolorSearchResult(
        solution,
        baseline_official,
        baseline_safe,
        best_solution,
        best_official,
        best_safe,
        targets,
        tuple(trials),
    )
