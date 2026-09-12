from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph
from q2_model import CACHE_CAPACITIES, Q2Solution, SpillRecord, spill_node_ids
from q2_validator import validate_q2_solution
from q3_audit import physical_epochs
from q3_conv_local_recolor import OfficialFastContext, critical_reuse_targets, move_initial_offset
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult, ResidencyEpoch


@dataclass(frozen=True, slots=True)
class PairedEpochMove:
    target_buf: int
    old_initial_offset: int
    new_initial_offset: int
    spill_index: int
    spill_buf: int
    old_spill_offset: int
    new_spill_offset: int


@dataclass(frozen=True, slots=True)
class PairedEpochTrial:
    target_buf: int
    new_initial_offset: int
    blocker_spill_index: int
    new_spill_offset: int | None
    fast_official_cycles: int | None
    q2_valid: bool | None
    safe_valid: bool | None
    official_cycles: int | None
    safe_cycles: int | None
    error: str = ""


@dataclass(frozen=True, slots=True)
class PairedEpochSearchResult:
    baseline_solution: Q2Solution
    baseline_official: Q3TimingResult
    baseline_safe: Q3TimingResult
    best_solution: Q2Solution
    best_official: Q3TimingResult
    best_safe: Q3TimingResult
    best_move: PairedEpochMove | None
    target_buffers: tuple[int, ...]
    paired_start_count: int
    competitive_start_count: int
    strict_replay_count: int
    trials: tuple[PairedEpochTrial, ...]

    @property
    def improved(self) -> bool:
        return self.best_official.total_cycles < self.baseline_official.total_cycles


def _pos_overlap(pos: dict[int, int], a: ResidencyEpoch, b: ResidencyEpoch) -> bool:
    return max(pos[a.acquire_node], pos[b.acquire_node]) < min(
        pos[a.release_node], pos[b.release_node]
    )


def _address_overlap(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and b0 < a1


def _spill_index_for_epoch(graph: ComputeGraph, epoch: ResidencyEpoch) -> int | None:
    n = graph.node_count
    if epoch.acquire_node < n:
        return None
    relative = epoch.acquire_node - n
    if relative % 2 == 0:
        return None
    return relative // 2


def _initial_epoch(graph: ComputeGraph, epochs: list[ResidencyEpoch], buf_id: int) -> ResidencyEpoch:
    alloc = graph.alloc_node_for_buffer(buf_id)
    if alloc is None:
        raise ValueError(f"buffer {buf_id} lacks ALLOC")
    for epoch in epochs:
        if epoch.buf_id == buf_id and epoch.acquire_node == alloc.id:
            return epoch
    raise ValueError(f"buffer {buf_id} lacks initial residency epoch")


def _epoch_pressure_prefix(
    epochs: list[ResidencyEpoch],
    *,
    memory_type: str,
    capacity: int,
    exclude_acquire: int | None = None,
) -> list[int]:
    diff = [0] * (capacity + 1)
    for epoch in epochs:
        if epoch.memory_type != memory_type or epoch.acquire_node == exclude_acquire:
            continue
        diff[epoch.start] += 1
        diff[epoch.end] -= 1
    pressure = [0] * capacity
    active = 0
    for i in range(capacity):
        active += diff[i]
        pressure[i] = active
    prefix = [0]
    for value in pressure:
        prefix.append(prefix[-1] + value)
    return prefix


def paired_initial_starts(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    target_buf: int,
    max_starts: int = 24,
) -> tuple[tuple[int, int], ...]:
    """Return (new initial offset, sole blocking SPILL index) candidates.

    Unlike the production single-residency candidate generator, this deliberately
    keeps ranges that are blocked by exactly one movable SPILL_IN residency epoch.
    Any overlap with an initial/fixed epoch, or with two distinct SPILL epochs, is
    rejected.  A later paired move can then relocate that one blocker.
    """

    if max_starts <= 0:
        return ()
    epochs = physical_epochs(graph, solution)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    target = _initial_epoch(graph, epochs, target_buf)
    capacity = CACHE_CAPACITIES[target.memory_type]
    size = target.end - target.start
    old_start = solution.initial_offsets[target_buf]

    blockers_by_address: list[set[int]] = [set() for _ in range(capacity)]
    for epoch in epochs:
        if epoch.acquire_node == target.acquire_node or epoch.memory_type != target.memory_type:
            continue
        if not _pos_overlap(pos, target, epoch):
            continue
        spill_index = _spill_index_for_epoch(graph, epoch)
        token = spill_index if spill_index is not None else -1
        for address in range(epoch.start, epoch.end):
            blockers_by_address[address].add(token)

    pressure_prefix = _epoch_pressure_prefix(
        epochs,
        memory_type=target.memory_type,
        capacity=capacity,
        exclude_acquire=target.acquire_node,
    )
    scored: list[tuple[int, int, int, int]] = []
    for start in range(0, capacity - size + 1):
        if start == old_start:
            continue
        blockers: set[int] = set()
        for address in range(start, start + size):
            blockers.update(blockers_by_address[address])
            if -1 in blockers or len(blockers) > 1:
                break
        if -1 in blockers or len(blockers) != 1:
            continue
        spill_index = next(iter(blockers))
        if spill_index < 0:
            continue
        pressure = pressure_prefix[start + size] - pressure_prefix[start]
        scored.append((pressure, abs(start - old_start), start, spill_index))

    scored.sort()
    min_gap = max(1, size // 4)
    chosen: list[tuple[int, int]] = []
    for _, _, start, spill_index in scored:
        if all(abs(start - other_start) >= min_gap for other_start, _ in chosen):
            chosen.append((start, spill_index))
            if len(chosen) >= max_starts:
                break
    if len(chosen) < max_starts:
        for _, _, start, spill_index in scored:
            item = (start, spill_index)
            if item not in chosen:
                chosen.append(item)
                if len(chosen) >= max_starts:
                    break
    return tuple(chosen)


def _spill_epoch(graph: ComputeGraph, epochs: list[ResidencyEpoch], spill_index: int) -> ResidencyEpoch:
    _, in_id = spill_node_ids(graph, spill_index)
    for epoch in epochs:
        if epoch.acquire_node == in_id:
            return epoch
    raise ValueError(f"spill {spill_index} lacks SPILL_IN residency epoch")


def candidate_spill_offsets(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    target_buf: int,
    new_initial_offset: int,
    spill_index: int,
    max_starts: int = 8,
) -> tuple[int, ...]:
    if max_starts <= 0:
        return ()
    epochs = physical_epochs(graph, solution)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    target = _initial_epoch(graph, epochs, target_buf)
    moving = _spill_epoch(graph, epochs, spill_index)
    if target.memory_type != moving.memory_type or not _pos_overlap(pos, target, moving):
        return ()

    capacity = CACHE_CAPACITIES[moving.memory_type]
    size = moving.end - moving.start
    block_diff = [0] * (capacity + 1)
    pressure_diff = [0] * (capacity + 1)
    for epoch in epochs:
        if epoch.memory_type != moving.memory_type or epoch.acquire_node == moving.acquire_node:
            continue
        pressure_diff[epoch.start] += 1
        pressure_diff[epoch.end] -= 1
        if epoch.acquire_node == target.acquire_node:
            continue
        if _pos_overlap(pos, moving, epoch):
            block_diff[epoch.start] += 1
            block_diff[epoch.end] -= 1

    blocked_prefix = [0]
    pressure_prefix = [0]
    blocked = 0
    pressure = 0
    for i in range(capacity):
        blocked += block_diff[i]
        pressure += pressure_diff[i]
        blocked_prefix.append(blocked_prefix[-1] + (1 if blocked else 0))
        pressure_prefix.append(pressure_prefix[-1] + pressure)

    target_size = target.end - target.start
    target_end = new_initial_offset + target_size
    old_offset = solution.spills[spill_index].new_offset
    scored: list[tuple[int, int, int]] = []
    for start in range(0, capacity - size + 1):
        if start == old_offset:
            continue
        end = start + size
        if blocked_prefix[end] - blocked_prefix[start] != 0:
            continue
        if _address_overlap(start, end, new_initial_offset, target_end):
            continue
        pressure_score = pressure_prefix[end] - pressure_prefix[start]
        scored.append((pressure_score, abs(start - old_offset), start))
    scored.sort()
    return tuple(start for _, _, start in scored[:max_starts])


def move_paired_epoch(
    solution: Q2Solution,
    *,
    target_buf: int,
    new_initial_offset: int,
    spill_index: int,
    new_spill_offset: int,
) -> Q2Solution:
    offsets = dict(solution.initial_offsets)
    offsets[target_buf] = new_initial_offset
    spills = list(solution.spills)
    old = spills[spill_index]
    spills[spill_index] = SpillRecord(old.buf_id, new_spill_offset)
    return Q2Solution(solution.schedule, offsets, tuple(spills))


def search_q3_paired_epoch_recolor(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_targets: int = 6,
    max_initial_starts: int = 24,
    max_spill_starts: int = 8,
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> PairedEpochSearchResult:
    """Search one initial-residency + one SPILL_IN address move at fixed traffic.

    Official Appendix-C literal reuse depends only on initial ALLOC placements, so
    the SPILL_IN relocation is a feasibility-enabling companion move.  Fast
    official screening scores only the initial move exactly; a candidate is never
    accepted until the paired solution passes strict Q2, residency-safe timing,
    and a full official-literal replay.
    """

    base_q2 = validate_q2_solution(graph, solution)
    base_q2.require_ok()
    if baseline_official is None:
        baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    if baseline_safe is None:
        baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()
    spill_bufs = tuple(spill.buf_id for spill in solution.spills)

    fast_context = OfficialFastContext.build(graph, solution)
    baseline_fast = fast_context.score(graph, solution)
    if baseline_fast.total_cycles != baseline_official.total_cycles:
        raise AssertionError("paired search fast baseline disagrees with official evaluator")

    targets = critical_reuse_targets(
        graph,
        solution,
        max_targets=max_targets,
        official_timing=baseline_official,
        reuse_edges=fast_context.baseline_reuse_edges,
    )
    best_solution = solution
    best_official = baseline_official
    best_safe = baseline_safe
    best_move: PairedEpochMove | None = None
    trials: list[PairedEpochTrial] = []
    paired_start_count = 0
    competitive_start_count = 0
    strict_replay_count = 0

    for target_buf in targets:
        old_initial = solution.initial_offsets[target_buf]
        for new_initial, spill_index in paired_initial_starts(
            graph,
            solution,
            target_buf=target_buf,
            max_starts=max_initial_starts,
        ):
            paired_start_count += 1
            initial_only = move_initial_offset(solution, target_buf, new_initial)
            fast = fast_context.score(graph, initial_only)
            if fast.total_cycles >= best_official.total_cycles:
                trials.append(
                    PairedEpochTrial(
                        target_buf,
                        new_initial,
                        spill_index,
                        None,
                        fast.total_cycles,
                        None,
                        None,
                        None,
                        None,
                        "paired start skipped: exact official score not competitive",
                    )
                )
                continue
            competitive_start_count += 1
            spill = solution.spills[spill_index]
            spill_starts = candidate_spill_offsets(
                graph,
                solution,
                target_buf=target_buf,
                new_initial_offset=new_initial,
                spill_index=spill_index,
                max_starts=max_spill_starts,
            )
            if not spill_starts:
                trials.append(
                    PairedEpochTrial(
                        target_buf,
                        new_initial,
                        spill_index,
                        None,
                        fast.total_cycles,
                        None,
                        None,
                        None,
                        None,
                        "no feasible companion SPILL_IN offset",
                    )
                )
                continue

            for new_spill in spill_starts:
                candidate = move_paired_epoch(
                    solution,
                    target_buf=target_buf,
                    new_initial_offset=new_initial,
                    spill_index=spill_index,
                    new_spill_offset=new_spill,
                )
                strict_replay_count += 1
                q2 = validate_q2_solution(graph, candidate)
                if not q2.ok:
                    trials.append(
                        PairedEpochTrial(
                            target_buf,
                            new_initial,
                            spill_index,
                            new_spill,
                            fast.total_cycles,
                            False,
                            None,
                            None,
                            None,
                            "; ".join(q2.errors[:2]),
                        )
                    )
                    continue
                if q2.extra_traffic != base_q2.extra_traffic or q2.spill_count != base_q2.spill_count:
                    raise AssertionError("paired epoch move changed Q2 traffic or spill count")
                if tuple(record.buf_id for record in candidate.spills) != spill_bufs:
                    raise AssertionError("paired epoch move changed spill victim identity/order")

                safe = evaluate_q3_solution(graph, candidate, reuse_mode="residency_safe")
                if not safe.ok:
                    trials.append(
                        PairedEpochTrial(
                            target_buf,
                            new_initial,
                            spill_index,
                            new_spill,
                            fast.total_cycles,
                            True,
                            False,
                            None,
                            None,
                            "; ".join(safe.errors[:2]),
                        )
                    )
                    continue

                official = evaluate_q3_solution(graph, candidate, reuse_mode="official_literal")
                official.require_ok()
                if official.total_cycles != fast.total_cycles:
                    raise AssertionError(
                        f"paired official score mismatch: fast={fast.total_cycles}, full={official.total_cycles}"
                    )
                if official.reuse_edge_count != fast.reuse_edge_count:
                    raise AssertionError("paired official reuse-edge count mismatch")
                trials.append(
                    PairedEpochTrial(
                        target_buf,
                        new_initial,
                        spill_index,
                        new_spill,
                        fast.total_cycles,
                        True,
                        True,
                        official.total_cycles,
                        safe.total_cycles,
                    )
                )
                key = (official.total_cycles, safe.total_cycles, new_initial, spill_index, new_spill)
                best_key = (
                    best_official.total_cycles,
                    best_safe.total_cycles,
                    best_move.new_initial_offset if best_move else old_initial,
                    best_move.spill_index if best_move else -1,
                    best_move.new_spill_offset if best_move else -1,
                )
                if key < best_key:
                    best_solution = candidate
                    best_official = official
                    best_safe = safe
                    best_move = PairedEpochMove(
                        target_buf,
                        old_initial,
                        new_initial,
                        spill_index,
                        spill.buf_id,
                        spill.new_offset,
                        new_spill,
                    )
                # Official score is independent of the companion SPILL offset.
                # Once one safe-valid companion is found for this initial move,
                # additional offsets cannot improve the ranking objective.
                break

    final_q2 = validate_q2_solution(graph, best_solution)
    final_q2.require_ok()
    if final_q2.extra_traffic != base_q2.extra_traffic or final_q2.spill_count != base_q2.spill_count:
        raise AssertionError("paired search final Q2 invariants changed")
    if tuple(record.buf_id for record in best_solution.spills) != spill_bufs:
        raise AssertionError("paired search final spill victim identity/order changed")
    final_official = evaluate_q3_solution(graph, best_solution, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, best_solution, reuse_mode="residency_safe")
    final_safe.require_ok()
    if final_official.total_cycles != best_official.total_cycles:
        raise AssertionError("paired search final official replay drifted")
    if final_safe.total_cycles != best_safe.total_cycles:
        raise AssertionError("paired search final safe replay drifted")

    return PairedEpochSearchResult(
        solution,
        baseline_official,
        baseline_safe,
        best_solution,
        final_official,
        final_safe,
        best_move,
        targets,
        paired_start_count,
        competitive_start_count,
        strict_replay_count,
        tuple(trials),
    )
