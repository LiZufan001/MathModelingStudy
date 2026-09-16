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
from q3_edge_cut_paired_recolor import search_q3_edge_cut_paired_recolor
from q3_evaluator import evaluate_q3_solution


def _fixture() -> tuple[ComputeGraph, Q2Solution]:
    nodes = [
        Node(0, "ALLOC", 0, 4, "L1"),
        Node(1, "PREV", pipe="CUBE", cycles=500, bufs=(0,)),
        Node(2, "FREE", 0, 4, "L1"),
        Node(3, "ALLOC", 1, 4, "L1"),
        Node(4, "FREE", 1, 4, "L1"),
        Node(5, "ALLOC", 2, 4, "L1"),
        Node(6, "TARGET", pipe="VECTOR", cycles=500, bufs=(2,)),
        Node(7, "FREE", 2, 4, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [(0, 1), (1, 2), (3, 4), (5, 6), (6, 7)],
    )
    solution = Q2Solution(
        schedule=(0, 1, 2, 3, 8, 9, 5, 6, 7, 4),
        initial_offsets={0: 0, 1: 8, 2: 0},
        spills=(SpillRecord(1, 4),),
    )
    validate_q2_solution(graph, solution).require_ok()
    return graph, solution


def test_edge_cut_guidance_finds_spill_blocked_critical_reuse_removal() -> None:
    graph, solution = _fixture()
    baseline = evaluate_q3_solution(graph, solution, reuse_mode="official_literal")
    baseline.require_ok()
    assert baseline.total_cycles == 1000

    result = search_q3_edge_cut_paired_recolor(
        graph,
        solution,
        max_edges=4,
        max_starts_per_edge=32,
        max_spill_starts=8,
    )
    assert result.critical_reuse_edges
    assert result.generated_count > 0
    assert result.competitive_count > 0
    assert result.strict_replay_count > 0
    assert result.improved
    assert result.best_official.total_cycles == 500
    assert result.best_safe.ok
    assert result.best_move is not None
    assert result.best_move.target_buf == 2
    assert result.best_move.spill_index == 0
    final_q2 = validate_q2_solution(graph, result.best_solution)
    final_q2.require_ok()
    assert tuple(s.buf_id for s in result.best_solution.spills) == (1,)
