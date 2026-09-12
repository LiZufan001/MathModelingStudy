from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
EXP = Path(__file__).resolve().parent
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from model import ComputeGraph
from q2_model import CACHE_CAPACITIES, Q2Solution
from q2_validator import validate_q2_solution
from q3_audit import physical_epochs
from q3_conv_local_recolor import OfficialFastContext, move_initial_offset
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult, ResidencyEpoch
from q3_paired_epoch_recolor import (
    PairedEpochMove,
    candidate_spill_offsets,
    move_paired_epoch,
)


@dataclass(frozen=True, slots=True)
class EdgeCutCandidate:
    free_node: int
    previous_buf: int
    target_buf: int
    new_initial_offset: int
    blocker_spill_index: int
    incoming_edge_count: int


@dataclass(frozen=True, slots=True)
class EdgeCutTrial:
    candidate: EdgeCutCandidate
    fast_official_cycles: int
    new_spill_offset: int | None
    q2_valid: bool | None
    safe_valid: bool | None
    official_cycles: int | None
    safe_cycles: int | None
    error: str = ""


@dataclass(frozen=True, slots=True)
class EdgeCutPairedResult:
    baseline_solution: Q2Solution
    baseline_official: Q3TimingResult
    baseline_safe: Q3TimingResult
    best_solution: Q2Solution
    best_official: Q3TimingResult
    best_safe: Q3TimingResult
    best_move: PairedEpochMove | None
    critical_reuse_edges: tuple[tuple[int, int], ...]
    generated_count: int
    competitive_count: int
    strict_replay_count: int
    blocker_histogram: tuple[tuple[str, int], ...]
    trials: tuple[EdgeCutTrial, ...]

    @property
    def improved(self) -> bool:
        return self.best_official.total_cycles < self.baseline_official.total_cycles


def _position_overlap(pos: dict[int, int], a: ResidencyEpoch, b: ResidencyEpoch) -> bool:
    return max(pos[a.acquire_node], pos[b.acquire_node]) < min(
        pos[a.release_node], pos[b.release_node]
    )


def _initial_epoch(graph: ComputeGraph, epochs: list[ResidencyEpoch], buf_id: int) -> ResidencyEpoch:
    alloc = graph.alloc_node_for_buffer(buf_id)
    if alloc is None:
        raise ValueError(f"buffer {buf_id} lacks ALLOC")
    for epoch in epochs:
        if epoch.buf_id == buf_id and epoch.acquire_node == alloc.id:
            return epoch
    raise ValueError(f"buffer {buf_id} lacks initial residency epoch")


def _spill_index_from_acquire(graph: ComputeGraph, acquire_node: int) -> int | None:
    n = graph.node_count
    if acquire_node < n:
        return None
    relative = acquire_node - n
    if relative % 2 == 0:
        return None
    return relative // 2


def _critical_reuse_edges(
    graph: ComputeGraph,
    solution: Q2Solution,
    timing: Q3TimingResult,
    reuse_edges: frozenset[tuple[int, int]],
) -> tuple[tuple[int, int], ...]:
    out: list[tuple[int, int]] = []
    for u, v in reversed(list(zip(timing.critical_path, timing.critical_path[1:]))):
        if (u, v) not in reuse_edges:
            continue
        source = graph.nodes.get(u)
        target = graph.nodes.get(v)
        if source is None or target is None:
            continue
        if not source.is_free or source.buf_id is None:
            continue
        if not target.is_alloc or target.buf_id is None:
            continue
        out.append((u, v))
    return tuple(out)


def _blocking_epochs(
    graph: ComputeGraph,
    solution: Q2Solution,
    epochs: list[ResidencyEpoch],
    pos: dict[int, int],
    *,
    target_buf: int,
    new_start: int,
) -> tuple[set[int], int]:
    target = _initial_epoch(graph, epochs, target_buf)
    target_size = target.end - target.start
    new_end = new_start + target_size
    spill_blockers: set[int] = set()
    fixed_blockers = 0
    for epoch in epochs:
        if epoch.acquire_node == target.acquire_node or epoch.memory_type != target.memory_type:
            continue
        if not _position_overlap(pos, target, epoch):
            continue
        if not (new_start < epoch.end and epoch.start < new_end):
            continue
        spill_index = _spill_index_from_acquire(graph, epoch.acquire_node)
        if spill_index is None:
            fixed_blockers += 1
        else:
            spill_blockers.add(spill_index)
    return spill_blockers, fixed_blockers


def critical_edge_cut_candidates(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    fast_context: OfficialFastContext,
    official_timing: Q3TimingResult,
    max_edges: int = 6,
    max_starts_per_edge: int = 64,
) -> tuple[tuple[EdgeCutCandidate, ...], tuple[tuple[str, int], ...], tuple[tuple[int, int], ...]]:
    """Generate one-SPILL-blocked starts that explicitly cut a critical reuse edge.

    For critical edge FREE(previous)->ALLOC(target), the new target window must
    contain zero bytes whose literal last owner is `previous`.  This makes the
    candidate generation objective-aware before any timing score is evaluated.
    We then keep only windows whose Q2 positional conflict set is exactly one
    SPILL_IN epoch and no fixed/initial residency epoch.
    """

    if max_edges <= 0 or max_starts_per_edge <= 0:
        return (), (), ()
    epochs = physical_epochs(graph, solution)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    edges = _critical_reuse_edges(
        graph,
        solution,
        official_timing,
        fast_context.baseline_reuse_edges,
    )[:max_edges]
    histogram: dict[str, int] = {}
    generated: list[EdgeCutCandidate] = []

    for free_id, alloc_id in edges:
        previous = graph.nodes[free_id]
        target_node = graph.nodes[alloc_id]
        assert previous.buf_id is not None and target_node.buf_id is not None
        previous_buf = previous.buf_id
        target_buf = target_node.buf_id
        ctx = fast_context._target_context(target_buf)
        capacity = CACHE_CAPACITIES[ctx.memory_type]
        old_start = solution.initial_offsets[target_buf]

        ranked: list[tuple[int, int, int, int]] = []
        for start in range(0, capacity - ctx.size + 1):
            if start == old_start:
                continue
            owners = ctx.owner_before[start : start + ctx.size]
            if previous_buf in owners:
                histogram["critical_owner_present"] = histogram.get("critical_owner_present", 0) + 1
                continue

            spill_blockers, fixed_blockers = _blocking_epochs(
                graph,
                solution,
                epochs,
                pos,
                target_buf=target_buf,
                new_start=start,
            )
            if fixed_blockers:
                histogram["fixed_blocker"] = histogram.get("fixed_blocker", 0) + 1
                continue
            if not spill_blockers:
                histogram["no_blocker"] = histogram.get("no_blocker", 0) + 1
                continue
            if len(spill_blockers) != 1:
                key = f"spill_blockers_{len(spill_blockers)}"
                histogram[key] = histogram.get(key, 0) + 1
                continue

            incoming: set[int] = set()
            for owner in set(owners):
                if owner is None:
                    continue
                free = graph.free_node_for_buffer(owner)
                if free is not None and pos[free.id] < pos[alloc_id]:
                    incoming.add(free.id)
            spill_index = next(iter(spill_blockers))
            ranked.append((len(incoming), abs(start - old_start), start, spill_index))

        ranked.sort()
        for incoming_count, _, start, spill_index in ranked[:max_starts_per_edge]:
            generated.append(
                EdgeCutCandidate(
                    free_id,
                    previous_buf,
                    target_buf,
                    start,
                    spill_index,
                    incoming_count,
                )
            )

    return tuple(generated), tuple(sorted(histogram.items())), edges


def search_q3_edge_cut_paired_recolor(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_edges: int = 6,
    max_starts_per_edge: int = 64,
    max_spill_starts: int = 12,
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> EdgeCutPairedResult:
    base_q2 = validate_q2_solution(graph, solution)
    base_q2.require_ok()
    if baseline_official is None:
        baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    if baseline_safe is None:
        baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()
    base_spill_bufs = tuple(spill.buf_id for spill in solution.spills)

    fast_context = OfficialFastContext.build(graph, solution)
    candidates, histogram, critical_edges = critical_edge_cut_candidates(
        graph,
        solution,
        fast_context=fast_context,
        official_timing=baseline_official,
        max_edges=max_edges,
        max_starts_per_edge=max_starts_per_edge,
    )

    best_solution = solution
    best_official = baseline_official
    best_safe = baseline_safe
    best_move: PairedEpochMove | None = None
    trials: list[EdgeCutTrial] = []
    competitive_count = 0
    strict_replay_count = 0

    for candidate_meta in candidates:
        initial_only = move_initial_offset(
            solution,
            candidate_meta.target_buf,
            candidate_meta.new_initial_offset,
        )
        fast = fast_context.score(graph, initial_only)
        if fast.total_cycles >= best_official.total_cycles:
            trials.append(
                EdgeCutTrial(
                    candidate_meta,
                    fast.total_cycles,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "edge cut did not improve exact official timing",
                )
            )
            continue
        competitive_count += 1
        spill = solution.spills[candidate_meta.blocker_spill_index]
        companion_starts = candidate_spill_offsets(
            graph,
            solution,
            target_buf=candidate_meta.target_buf,
            new_initial_offset=candidate_meta.new_initial_offset,
            spill_index=candidate_meta.blocker_spill_index,
            max_starts=max_spill_starts,
        )
        if not companion_starts:
            trials.append(
                EdgeCutTrial(
                    candidate_meta,
                    fast.total_cycles,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "no feasible companion SPILL_IN offset",
                )
            )
            continue

        for new_spill in companion_starts:
            candidate_solution = move_paired_epoch(
                solution,
                target_buf=candidate_meta.target_buf,
                new_initial_offset=candidate_meta.new_initial_offset,
                spill_index=candidate_meta.blocker_spill_index,
                new_spill_offset=new_spill,
            )
            strict_replay_count += 1
            q2 = validate_q2_solution(graph, candidate_solution)
            if not q2.ok:
                trials.append(
                    EdgeCutTrial(
                        candidate_meta,
                        fast.total_cycles,
                        new_spill,
                        False,
                        None,
                        None,
                        None,
                        "; ".join(q2.errors[:2]),
                    )
                )
                continue
            if q2.extra_traffic != base_q2.extra_traffic or q2.spill_count != base_q2.spill_count:
                raise AssertionError("edge-cut paired move changed Q2 traffic/spill count")
            if tuple(s.buf_id for s in candidate_solution.spills) != base_spill_bufs:
                raise AssertionError("edge-cut paired move changed spill victim identity/order")

            safe = evaluate_q3_solution(graph, candidate_solution, reuse_mode="residency_safe")
            if not safe.ok:
                trials.append(
                    EdgeCutTrial(
                        candidate_meta,
                        fast.total_cycles,
                        new_spill,
                        True,
                        False,
                        None,
                        None,
                        "; ".join(safe.errors[:2]),
                    )
                )
                continue
            official = evaluate_q3_solution(graph, candidate_solution, reuse_mode="official_literal")
            official.require_ok()
            if official.total_cycles != fast.total_cycles or official.reuse_edge_count != fast.reuse_edge_count:
                raise AssertionError("edge-cut paired fast/full official mismatch")
            trials.append(
                EdgeCutTrial(
                    candidate_meta,
                    fast.total_cycles,
                    new_spill,
                    True,
                    True,
                    official.total_cycles,
                    safe.total_cycles,
                )
            )
            if (official.total_cycles, safe.total_cycles) < (
                best_official.total_cycles,
                best_safe.total_cycles,
            ):
                best_solution = candidate_solution
                best_official = official
                best_safe = safe
                best_move = PairedEpochMove(
                    candidate_meta.target_buf,
                    solution.initial_offsets[candidate_meta.target_buf],
                    candidate_meta.new_initial_offset,
                    candidate_meta.blocker_spill_index,
                    spill.buf_id,
                    spill.new_offset,
                    new_spill,
                )
            # Companion offset cannot alter official_literal timing; one valid
            # companion is enough for this initial placement.
            break

    final_q2 = validate_q2_solution(graph, best_solution)
    final_q2.require_ok()
    if final_q2.extra_traffic != base_q2.extra_traffic or final_q2.spill_count != base_q2.spill_count:
        raise AssertionError("edge-cut paired final Q2 invariants changed")
    if tuple(s.buf_id for s in best_solution.spills) != base_spill_bufs:
        raise AssertionError("edge-cut paired final spill identity/order changed")
    final_official = evaluate_q3_solution(graph, best_solution, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, best_solution, reuse_mode="residency_safe")
    final_safe.require_ok()

    return EdgeCutPairedResult(
        solution,
        baseline_official,
        baseline_safe,
        best_solution,
        final_official,
        final_safe,
        best_move,
        critical_edges,
        len(candidates),
        competitive_count,
        strict_replay_count,
        histogram,
        tuple(trials),
    )
