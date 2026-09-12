from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph
from q2_model import Q2Solution, spill_node_ids
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution
from q3_model import Q3TimingResult


@dataclass(frozen=True, slots=True)
class SpillGapShiftTrial:
    spill_index: int
    buf_id: int
    old_gap: int
    new_gap: int
    q2_valid: bool
    safe_valid: bool | None
    official_cycles: int | None
    safe_cycles: int | None
    changed_positions: int
    error: str = ""


@dataclass(frozen=True, slots=True)
class SpillGapShiftResult:
    baseline_solution: Q2Solution
    baseline_official: Q3TimingResult
    baseline_safe: Q3TimingResult
    best_solution: Q2Solution
    best_official: Q3TimingResult
    best_safe: Q3TimingResult
    best_shift: tuple[int, int] | None
    critical_spill_indices: tuple[int, ...]
    trials: tuple[SpillGapShiftTrial, ...]

    @property
    def improved(self) -> bool:
        return self.best_official.total_cycles < self.baseline_official.total_cycles


def _touches_buffer(graph: ComputeGraph, node_id: int, buf_id: int) -> bool:
    if node_id >= graph.node_count:
        return False
    node = graph.nodes[node_id]
    if node.is_alloc or node.is_free:
        return node.buf_id == buf_id
    return buf_id in node.bufs


def _touch_nodes(graph: ComputeGraph, solution: Q2Solution, buf_id: int) -> list[int]:
    return [
        node_id
        for node_id in solution.schedule
        if _touches_buffer(graph, node_id, buf_id)
    ]


def _current_gap(
    graph: ComputeGraph,
    solution: Q2Solution,
    spill_index: int,
) -> tuple[list[int], int]:
    spill = solution.spills[spill_index]
    touches = _touch_nodes(graph, solution, spill.buf_id)
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    out_id, in_id = spill_node_ids(graph, spill_index)
    left = [i for i, node_id in enumerate(touches) if pos[node_id] < pos[out_id]]
    right = [i for i, node_id in enumerate(touches) if pos[node_id] > pos[in_id]]
    if not left or not right:
        raise ValueError(f"spill {spill_index} has no touch gap around its OUT/IN pair")
    left_index = max(left)
    right_index = min(right)
    if right_index != left_index + 1:
        raise ValueError(
            f"spill {spill_index} unexpectedly encloses a same-buffer touch: "
            f"{left_index}->{right_index}"
        )
    return touches, left_index


def _gap_has_other_same_buffer_spill(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    buf_id: int,
    left_touch: int,
    right_touch: int,
    exclude_spill_index: int,
) -> bool:
    pos = {node_id: i for i, node_id in enumerate(solution.schedule)}
    lo = pos[left_touch]
    hi = pos[right_touch]
    for index, spill in enumerate(solution.spills):
        if index == exclude_spill_index or spill.buf_id != buf_id:
            continue
        out_id, in_id = spill_node_ids(graph, index)
        if lo < pos[out_id] < pos[in_id] < hi:
            return True
    return False


def move_spill_pair_to_gap(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    spill_index: int,
    gap_index: int,
) -> Q2Solution:
    spill = solution.spills[spill_index]
    touches = _touch_nodes(graph, solution, spill.buf_id)
    if gap_index < 0 or gap_index + 1 >= len(touches):
        raise ValueError("target spill gap is outside buffer lifetime")
    left_touch = touches[gap_index]
    right_touch = touches[gap_index + 1]
    if _gap_has_other_same_buffer_spill(
        graph,
        solution,
        buf_id=spill.buf_id,
        left_touch=left_touch,
        right_touch=right_touch,
        exclude_spill_index=spill_index,
    ):
        raise ValueError("target gap already contains another spill for the same buffer")

    out_id, in_id = spill_node_ids(graph, spill_index)
    stripped = [node_id for node_id in solution.schedule if node_id not in {out_id, in_id}]
    left_pos = stripped.index(left_touch)
    stripped.insert(left_pos + 1, out_id)
    right_pos = stripped.index(right_touch)
    stripped.insert(right_pos, in_id)
    return Q2Solution(tuple(stripped), solution.initial_offsets, solution.spills)


def search_q3_critical_spill_gap_shifts(
    graph: ComputeGraph,
    solution: Q2Solution,
    *,
    max_spills: int = 16,
    gap_radius: int = 1,
    baseline_official: Q3TimingResult | None = None,
    baseline_safe: Q3TimingResult | None = None,
) -> SpillGapShiftResult:
    """Move a critical SPILL pair to a neighboring same-buffer use gap.

    The SPILL tuple, victim, new_offset, count, and official extra traffic are
    unchanged. Only OUT/IN placement in the global sequence moves. Unlike the
    production rescheduler, this can deliberately change which original uses lie
    before versus after the spill boundary. Proposals run strict Q2 and official
    replay first; only official-competitive moves pay for residency-safe replay,
    which remains mandatory before any move can be kept.
    """

    if max_spills <= 0 or gap_radius <= 0:
        raise ValueError("max_spills and gap_radius must be positive")
    base_q2 = validate_q2_solution(graph, solution)
    base_q2.require_ok()
    if baseline_official is None:
        baseline_official = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline_official.require_ok()
    if baseline_safe is None:
        baseline_safe = evaluate_q3_solution(graph, solution, reuse_mode="residency_safe")
    baseline_safe.require_ok()

    path_nodes = set(baseline_official.critical_path)
    critical: list[int] = []
    for spill_index in range(len(solution.spills)):
        out_id, in_id = spill_node_ids(graph, spill_index)
        if out_id in path_nodes or in_id in path_nodes:
            critical.append(spill_index)
    critical = critical[:max_spills]

    base_spills = tuple((spill.buf_id, spill.new_offset) for spill in solution.spills)
    best_solution = solution
    best_official = baseline_official
    best_safe = baseline_safe
    best_shift: tuple[int, int] | None = None
    trials: list[SpillGapShiftTrial] = []

    for spill_index in critical:
        spill = solution.spills[spill_index]
        try:
            touches, old_gap = _current_gap(graph, solution, spill_index)
        except Exception as exc:
            trials.append(
                SpillGapShiftTrial(
                    spill_index, spill.buf_id, -1, -1, False, False, None, None, 0,
                    f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        for delta in range(-gap_radius, gap_radius + 1):
            if delta == 0:
                continue
            new_gap = old_gap + delta
            if new_gap < 0 or new_gap + 1 >= len(touches):
                continue
            try:
                candidate = move_spill_pair_to_gap(
                    graph,
                    solution,
                    spill_index=spill_index,
                    gap_index=new_gap,
                )
                changed = sum(a != b for a, b in zip(candidate.schedule, solution.schedule))
                q2 = validate_q2_solution(graph, candidate)
                if not q2.ok:
                    trials.append(
                        SpillGapShiftTrial(
                            spill_index, spill.buf_id, old_gap, new_gap, False, False,
                            None, None, changed, "; ".join(q2.errors[:2]),
                        )
                    )
                    continue
                if q2.extra_traffic != base_q2.extra_traffic or q2.spill_count != base_q2.spill_count:
                    raise AssertionError("spill gap shift changed Q2 traffic/spill count")
                if tuple((s.buf_id, s.new_offset) for s in candidate.spills) != base_spills:
                    raise AssertionError("spill gap shift changed spill record identity/order/offset")

                official = evaluate_q3_solution(graph, candidate, reuse_mode="official_literal")
                official.require_ok()
                if official.total_cycles > best_official.total_cycles:
                    trials.append(
                        SpillGapShiftTrial(
                            spill_index,
                            spill.buf_id,
                            old_gap,
                            new_gap,
                            True,
                            None,
                            official.total_cycles,
                            None,
                            changed,
                            "residency-safe replay skipped: official score not competitive",
                        )
                    )
                    continue

                safe = evaluate_q3_solution(graph, candidate, reuse_mode="residency_safe")
                if not safe.ok:
                    trials.append(
                        SpillGapShiftTrial(
                            spill_index,
                            spill.buf_id,
                            old_gap,
                            new_gap,
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
                    SpillGapShiftTrial(
                        spill_index, spill.buf_id, old_gap, new_gap, True, True,
                        official.total_cycles, safe.total_cycles, changed,
                    )
                )
                if (official.total_cycles, safe.total_cycles, spill_index, new_gap) < (
                    best_official.total_cycles,
                    best_safe.total_cycles,
                    best_shift[0] if best_shift is not None else 1 << 60,
                    best_shift[1] if best_shift is not None else 1 << 60,
                ):
                    best_solution = candidate
                    best_official = official
                    best_safe = safe
                    best_shift = (spill_index, new_gap)
            except Exception as exc:
                trials.append(
                    SpillGapShiftTrial(
                        spill_index, spill.buf_id, old_gap, new_gap, False, False,
                        None, None, 0, f"{type(exc).__name__}: {exc}",
                    )
                )

    final_q2 = validate_q2_solution(graph, best_solution)
    final_q2.require_ok()
    if final_q2.extra_traffic != base_q2.extra_traffic or final_q2.spill_count != base_q2.spill_count:
        raise AssertionError("spill gap shift final Q2 invariants changed")
    if tuple((s.buf_id, s.new_offset) for s in best_solution.spills) != base_spills:
        raise AssertionError("spill gap shift final spill records changed")
    final_official = evaluate_q3_solution(graph, best_solution, reuse_mode="official_literal")
    final_official.require_ok()
    final_safe = evaluate_q3_solution(graph, best_solution, reuse_mode="residency_safe")
    final_safe.require_ok()

    return SpillGapShiftResult(
        solution,
        baseline_official,
        baseline_safe,
        best_solution,
        final_official,
        final_safe,
        best_shift,
        tuple(critical),
        tuple(trials),
    )
