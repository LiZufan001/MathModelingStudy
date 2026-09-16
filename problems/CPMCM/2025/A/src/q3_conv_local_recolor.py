from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_model import CACHE_CAPACITIES, Q2Solution
from q2_validator import validate_q2_solution
from q3_audit import physical_epochs
from q3_dependencies import (
    augmented_nodes,
    official_literal_reuse_edges,
    original_edges,
    pipe_edges,
    spill_edges,
)
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult, node_cycles


@dataclass(frozen=True, slots=True)
class LocalRecolorTrial:
    buf_id: int
    old_offset: int
    new_offset: int
    q2_valid: bool | None
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


@dataclass(frozen=True, slots=True)
class FastOfficialScore:
    total_cycles: int
    reuse_edge_count: int


@dataclass(frozen=True, slots=True)
class _AllocMeta:
    node_id: int
    buf_id: int
    memory_type: str
    size: int
    start: int


@dataclass(frozen=True, slots=True)
class _TargetMoveContext:
    alloc_id: int
    buf_id: int
    memory_type: str
    size: int
    old_start: int
    owner_before: tuple[int | None, ...]
    first_after_alloc: tuple[int | None, ...]


@dataclass(slots=True)
class OfficialFastContext:
    """Cached Appendix-C timing context for fixed schedule/SPILL decisions.

    For the baseline placement, literal reuse-edge support is replayed once. A
    single initial-offset move can then change only the moved ALLOC's incoming
    reuse edges and, for bytes entering/leaving its range, the first later ALLOC
    touching each byte. After that later ALLOC overwrites the byte, baseline and
    candidate last-owner state are identical again. Candidate screening therefore
    updates only those edge-support counts instead of replaying every ALLOC byte.

    Any candidate that can win this exact fast screen is still replayed by the
    full Q2/Q3 validators before it is accepted.
    """

    schedule: tuple[int, ...]
    pos: dict[int, int]
    static_predecessors: dict[int, tuple[int, ...]]
    cycles: dict[int, int]
    baseline_offsets: dict[int, int]
    allocs: tuple[_AllocMeta, ...]
    alloc_index_by_buf: dict[int, int]
    free_op_by_buf: dict[int, int]
    baseline_reuse_support: dict[tuple[int, int], int]
    baseline_dynamic_predecessors: dict[int, tuple[int, ...]]
    target_move_contexts: dict[int, _TargetMoveContext] = field(default_factory=dict)

    @classmethod
    def build(cls, graph: ComputeGraph, solution: Q2Solution) -> "OfficialFastContext":
        nodes = augmented_nodes(graph, solution)
        pos = {node_id: index for index, node_id in enumerate(solution.schedule)}
        static_edges = (
            original_edges(graph)
            | spill_edges(graph, solution, nodes, pos)
            | pipe_edges(solution, nodes)
        )
        predecessors: dict[int, list[int]] = {node_id: [] for node_id in nodes}
        for u, v in static_edges:
            if u not in pos or v not in pos:
                raise ValueError(f"static timing edge ({u}->{v}) references absent node")
            if pos[u] >= pos[v]:
                raise ValueError(
                    f"static timing edge ({u}->{v}) contradicts schedule positions "
                    f"{pos[u]} >= {pos[v]}"
                )
            predecessors[v].append(u)

        allocs: list[_AllocMeta] = []
        alloc_index_by_buf: dict[int, int] = {}
        free_op_by_buf: dict[int, int] = {}
        for alloc in sorted(
            (node for node in graph.nodes.values() if node.is_alloc),
            key=lambda node: pos[node.id],
        ):
            if alloc.buf_id is None or alloc.memory_type is None or alloc.size is None:
                raise ValueError(f"ALLOC node {alloc.id} has incomplete metadata")
            start = solution.initial_offsets[alloc.buf_id]
            capacity = CACHE_CAPACITIES[alloc.memory_type]
            if start < 0 or start + alloc.size > capacity:
                raise ValueError(f"buffer {alloc.buf_id} initial range exceeds {alloc.memory_type}")
            alloc_index_by_buf[alloc.buf_id] = len(allocs)
            allocs.append(
                _AllocMeta(
                    alloc.id,
                    alloc.buf_id,
                    alloc.memory_type,
                    alloc.size,
                    start,
                )
            )
            free = graph.free_node_for_buffer(alloc.buf_id)
            if free is not None:
                free_op_by_buf[alloc.buf_id] = free.id

        last_owner: dict[str, list[int | None]] = {
            memory_type: [None] * capacity
            for memory_type, capacity in CACHE_CAPACITIES.items()
        }
        support: dict[tuple[int, int], int] = {}
        for alloc in allocs:
            owners = last_owner[alloc.memory_type]
            start = alloc.start
            end = start + alloc.size
            for previous_buf, count in Counter(owners[start:end]).items():
                if previous_buf is None:
                    continue
                free_id = free_op_by_buf.get(previous_buf)
                if free_id is None:
                    raise ValueError(f"buffer {previous_buf} lacks FREE")
                if pos[free_id] < pos[alloc.node_id]:
                    edge = (free_id, alloc.node_id)
                    support[edge] = support.get(edge, 0) + count
            owners[start:end] = [alloc.buf_id] * alloc.size

        dynamic_predecessors: dict[int, list[int]] = {}
        for u, v in support:
            dynamic_predecessors.setdefault(v, []).append(u)

        return cls(
            tuple(solution.schedule),
            pos,
            {node_id: tuple(preds) for node_id, preds in predecessors.items()},
            {node_id: node_cycles(node) for node_id, node in nodes.items()},
            dict(solution.initial_offsets),
            tuple(allocs),
            alloc_index_by_buf,
            free_op_by_buf,
            support,
            {node_id: tuple(preds) for node_id, preds in dynamic_predecessors.items()},
        )

    @property
    def baseline_reuse_edges(self) -> frozenset[tuple[int, int]]:
        return frozenset(self.baseline_reuse_support)

    def _edge_for_owner(self, owner: int | None, alloc_id: int) -> tuple[int, int] | None:
        if owner is None:
            return None
        free_id = self.free_op_by_buf.get(owner)
        if free_id is None:
            raise ValueError(f"buffer {owner} lacks FREE")
        if self.pos[free_id] < self.pos[alloc_id]:
            return free_id, alloc_id
        return None

    def _target_context(self, buf_id: int) -> _TargetMoveContext:
        cached = self.target_move_contexts.get(buf_id)
        if cached is not None:
            return cached
        target_index = self.alloc_index_by_buf.get(buf_id)
        if target_index is None:
            raise ValueError(f"buffer {buf_id} lacks initial ALLOC")
        target = self.allocs[target_index]
        capacity = CACHE_CAPACITIES[target.memory_type]

        owner_before: list[int | None] = [None] * capacity
        for alloc in self.allocs[:target_index]:
            if alloc.memory_type != target.memory_type:
                continue
            owner_before[alloc.start : alloc.start + alloc.size] = [alloc.buf_id] * alloc.size

        first_after: list[int | None] = [None] * capacity
        unresolved = capacity
        for alloc in self.allocs[target_index + 1 :]:
            if alloc.memory_type != target.memory_type:
                continue
            for address in range(alloc.start, alloc.start + alloc.size):
                if first_after[address] is None:
                    first_after[address] = alloc.node_id
                    unresolved -= 1
            if unresolved == 0:
                break

        context = _TargetMoveContext(
            target.node_id,
            target.buf_id,
            target.memory_type,
            target.size,
            target.start,
            tuple(owner_before),
            tuple(first_after),
        )
        self.target_move_contexts[buf_id] = context
        return context

    def _timing_score(
        self,
        reuse_edge_count: int,
        *,
        full_dynamic: dict[int, tuple[int, ...]] | None = None,
        overrides: dict[int, tuple[int, ...]] | None = None,
    ) -> FastOfficialScore:
        finish_times: dict[int, int] = {}
        total_cycles = 0
        for node_id in self.schedule:
            start = 0
            for pred in self.static_predecessors[node_id]:
                start = max(start, finish_times[pred])
            if full_dynamic is not None:
                dynamic = full_dynamic.get(node_id, ())
            elif overrides is not None and node_id in overrides:
                dynamic = overrides[node_id]
            else:
                dynamic = self.baseline_dynamic_predecessors.get(node_id, ())
            for pred in dynamic:
                start = max(start, finish_times[pred])
            finish = start + self.cycles[node_id]
            finish_times[node_id] = finish
            total_cycles = max(total_cycles, finish)
        return FastOfficialScore(total_cycles, reuse_edge_count)

    def _score_single_move(self, buf_id: int, new_start: int) -> FastOfficialScore:
        target = self._target_context(buf_id)
        capacity = CACHE_CAPACITIES[target.memory_type]
        new_end = new_start + target.size
        if new_start < 0 or new_end > capacity:
            raise ValueError(f"buffer {buf_id} initial range exceeds {target.memory_type}")
        old_start = target.old_start
        old_end = old_start + target.size
        deltas: dict[tuple[int, int], int] = {}

        def adjust(owner: int | None, alloc_id: int, amount: int) -> None:
            if amount == 0:
                return
            edge = self._edge_for_owner(owner, alloc_id)
            if edge is not None:
                deltas[edge] = deltas.get(edge, 0) + amount

        for owner, count in Counter(target.owner_before[old_start:old_end]).items():
            adjust(owner, target.alloc_id, -count)
        for owner, count in Counter(target.owner_before[new_start:new_end]).items():
            adjust(owner, target.alloc_id, count)

        for address in range(old_start, old_end):
            if new_start <= address < new_end:
                continue
            later_alloc = target.first_after_alloc[address]
            if later_alloc is None:
                continue
            adjust(target.buf_id, later_alloc, -1)
            adjust(target.owner_before[address], later_alloc, 1)
        for address in range(new_start, new_end):
            if old_start <= address < old_end:
                continue
            later_alloc = target.first_after_alloc[address]
            if later_alloc is None:
                continue
            adjust(target.owner_before[address], later_alloc, -1)
            adjust(target.buf_id, later_alloc, 1)

        overrides: dict[int, set[int]] = {}
        reuse_edge_count = len(self.baseline_reuse_support)
        for edge, delta in deltas.items():
            if delta == 0:
                continue
            baseline_count = self.baseline_reuse_support.get(edge, 0)
            candidate_count = baseline_count + delta
            if candidate_count < 0:
                raise AssertionError(
                    f"incremental reuse support became negative for edge {edge}: "
                    f"{baseline_count} + {delta}"
                )
            before = baseline_count > 0
            after = candidate_count > 0
            if before == after:
                continue
            u, v = edge
            preds = overrides.setdefault(v, set(self.baseline_dynamic_predecessors.get(v, ())))
            if after:
                preds.add(u)
                reuse_edge_count += 1
            else:
                preds.discard(u)
                reuse_edge_count -= 1

        return self._timing_score(
            reuse_edge_count,
            overrides={node_id: tuple(preds) for node_id, preds in overrides.items()},
        )

    def score(self, graph: ComputeGraph, solution: Q2Solution) -> FastOfficialScore:
        if tuple(solution.schedule) != self.schedule:
            raise ValueError("fast official context requires the frozen schedule")
        if solution.initial_offsets.keys() != self.baseline_offsets.keys():
            reuse = official_literal_reuse_edges(graph, solution, self.pos)
        else:
            changed = [
                buf_id
                for buf_id, old_start in self.baseline_offsets.items()
                if solution.initial_offsets[buf_id] != old_start
            ]
            if not changed:
                return self._timing_score(len(self.baseline_reuse_support))
            if len(changed) == 1:
                buf_id = changed[0]
                return self._score_single_move(buf_id, solution.initial_offsets[buf_id])
            reuse = official_literal_reuse_edges(graph, solution, self.pos)

        dynamic_predecessors: dict[int, list[int]] = {}
        for u, v in reuse:
            dynamic_predecessors.setdefault(v, []).append(u)
        return self._timing_score(
            len(reuse),
            full_dynamic={node_id: tuple(preds) for node_id, preds in dynamic_predecessors.items()},
        )


def critical_reuse_targets(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_targets: int = 6,
    official_timing: Q3TimingResult | None = None,
    reuse_edges: frozenset[tuple[int, int]] | set[tuple[int, int]] | None = None,
) -> tuple[int, ...]:
    if max_targets <= 0:
        return ()
    timing = official_timing
    if timing is None:
        timing = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
        timing.require_ok()
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    reuse = set(reuse_edges) if reuse_edges is not None else official_literal_reuse_edges(graph, solution, pos)
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


def _address_pressure(graph: ComputeGraph, solution: Q2Solution, *, target_buf: int) -> tuple[str, int, list[int]]:
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


def _blocked_initial_bytes(graph: ComputeGraph, solution: Q2Solution, *, target_buf: int) -> list[int]:
    alloc = graph.alloc_node_for_buffer(target_buf)
    if alloc is None or alloc.memory_type is None:
        raise ValueError(f"buffer {target_buf} lacks complete ALLOC metadata")
    memory_type = alloc.memory_type
    capacity = CACHE_CAPACITIES[memory_type]
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    epochs = physical_epochs(graph, solution)
    target = next((epoch for epoch in epochs if epoch.buf_id == target_buf and epoch.acquire_node == alloc.id), None)
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


def candidate_initial_offsets(graph: ComputeGraph, solution: Q2Solution, buf_id: int, *, max_starts: int = 12) -> tuple[int, ...]:
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


def move_initial_offset(solution: Q2Solution, buf_id: int, new_offset: int) -> Q2Solution:
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
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> LocalRecolorSearchResult:
    base_q2 = validate_q2_solution(graph, solution)
    base_q2.require_ok()
    if baseline_safe is None:
        baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()
    if baseline_official is None:
        baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    base_spill_buffers = tuple(spill.buf_id for spill in solution.spills)

    fast_context = OfficialFastContext.build(graph, solution)
    baseline_fast = fast_context.score(graph, solution)
    if baseline_fast.total_cycles != baseline_official.total_cycles:
        raise AssertionError(f"cached official scorer disagrees with baseline evaluator: {baseline_fast.total_cycles} != {baseline_official.total_cycles}")
    if baseline_fast.reuse_edge_count != baseline_official.reuse_edge_count:
        raise AssertionError("cached official scorer disagrees with baseline reuse-edge count")

    targets = critical_reuse_targets(
        graph,
        solution,
        max_targets=max_targets,
        official_timing=baseline_official,
        reuse_edges=fast_context.baseline_reuse_edges,
    )
    best_solution = solution
    best_safe = baseline_safe
    best_official = baseline_official
    trials: list[LocalRecolorTrial] = []

    for buf_id in targets:
        old_offset = solution.initial_offsets[buf_id]
        for new_offset in candidate_initial_offsets(graph, solution, buf_id, max_starts=max_starts):
            candidate = move_initial_offset(solution, buf_id, new_offset)
            fast = fast_context.score(graph, candidate)
            if fast.total_cycles >= best_official.total_cycles:
                trials.append(LocalRecolorTrial(buf_id, old_offset, new_offset, None, None, fast.total_cycles, None, fast.reuse_edge_count, "full replay skipped: cached official score not competitive"))
                continue
            official = evaluate_q3_solution(graph, candidate, reuse_mode="official_literal")
            if not official.ok:
                q2_valid = not any(error.startswith("Q2 invalid:") for error in official.errors)
                trials.append(LocalRecolorTrial(buf_id, old_offset, new_offset, q2_valid, None, None, None, None, "; ".join(official.errors[:2])))
                continue
            if official.total_cycles != fast.total_cycles:
                raise AssertionError(f"cached official score mismatch for buffer {buf_id} offset {new_offset}: {fast.total_cycles} != {official.total_cycles}")
            if official.reuse_edge_count != fast.reuse_edge_count:
                raise AssertionError(f"cached reuse-edge count mismatch for buffer {buf_id} offset {new_offset}")
            safe = evaluate_q3_solution(graph, candidate, reuse_mode="residency_safe")
            if not safe.ok:
                trials.append(LocalRecolorTrial(buf_id, old_offset, new_offset, True, False, official.total_cycles, None, official.reuse_edge_count, "; ".join(safe.errors[:2])))
                continue
            trials.append(LocalRecolorTrial(buf_id, old_offset, new_offset, True, True, official.total_cycles, safe.total_cycles, official.reuse_edge_count))
            best_solution = candidate
            best_safe = safe
            best_official = official

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
