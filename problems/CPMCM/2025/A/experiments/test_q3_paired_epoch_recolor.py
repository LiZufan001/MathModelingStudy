from __future__ import annotations

import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_model import Q2Solution, SpillRecord
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution
from q3_paired_epoch_recolor import search_q3_paired_epoch_recolor


def _paired_fixture() -> tuple[ComputeGraph, Q2Solution]:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L1"),
        Node(1, "PREV", pipe="CUBE", cycles=100, bufs=(0,)),
        Node(2, "FREE", 0, 4, "L1"),
        Node(3, "ALLOC", 1, 4, "L1"),
        Node(4, "FREE", 1, 4, "L1"),
        Node(5, "ALLOC", 2, 4, "L1"),
        Node(6, "TARGET", pipe="VECTOR", cycles=100, bufs=(2,)),
        Node(7, "FREE", 2, 4, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [(0, 1), (1, 2), (3, 4), (5, 6), (6, 7)],
    )
    # N=8 -> spill 0 nodes are 8 (OUT) and 9 (IN).  The target buffer starts
    # at 0, where official literal reuse serializes it behind buffer 0.  Moving
    # target to 4 would remove that edge, but SPILL_IN(1) currently occupies 4.
    # Relocating that SPILL_IN epoch to 8 makes the improving initial move legal.
    solution = Q2Solution(
        schedule=(0, 1, 2, 3, 8, 9, 5, 6, 7, 4),
        initial_offsets={0: 0, 1: 8, 2: 0},
        spills=(SpillRecord(1, 4),),
    )
    validate_q2_solution(graph, solution).require_ok()
    return graph, solution


def test_pair_move_enables_official_improvement_blocked_by_spill_epoch() -> None:
    graph, solution = _paired_fixture()
    baseline = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline.require_ok()
    assert baseline.total_cycles == 200

    result = search_q3_paired_epoch_recolor(
        graph,
        solution,
        max_targets=2,
        max_initial_starts=16,
        max_spill_starts=8,
    )
    assert result.improved
    assert result.best_official.total_cycles == 100
    assert result.best_safe.ok
    assert result.best_move is not None
    assert result.best_move.target_buf == 2
    assert result.best_move.spill_index == 0
    assert result.best_move.new_initial_offset != 0
    assert result.best_move.new_spill_offset != 4
    final_q2 = validate_q2_solution(graph, result.best_solution)
    final_q2.require_ok()
    assert final_q2.extra_traffic == validate_q2_solution(graph, solution).extra_traffic
    assert tuple(s.buf_id for s in result.best_solution.spills) == (1,)
