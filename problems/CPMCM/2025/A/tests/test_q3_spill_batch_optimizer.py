from __future__ import annotations

from model import ComputeGraph, Node
from q2_model import Q2Solution, SpillRecord
from q2_validator import validate_q2_solution
from q3_spill_batch_optimizer import (
    optimize_q3_critical_spill_batches,
    search_q3_critical_spill_batches,
)


def _fixture() -> tuple[ComputeGraph, Q2Solution]:
    nodes = [
        Node(0, "ALLOC", 0, 1, "L1"),
        Node(1, "MTE3_DISTRACTOR", pipe="MTE3", cycles=100),
        Node(2, "MTE2_DISTRACTOR", pipe="MTE2", cycles=100),
        Node(3, "FREE", 0, 1, "L1"),
    ]
    graph = ComputeGraph.from_edges(nodes, [])
    solution = Q2Solution(
        schedule=(0, 1, 4, 5, 2, 3),
        initial_offsets={0: 0},
        spills=(SpillRecord(0, 0),),
    )
    validate_q2_solution(graph, solution).require_ok()
    return graph, solution


def test_formal_spill_batch_preserves_q2_and_improves_fixture() -> None:
    graph, solution = _fixture()
    result = search_q3_critical_spill_batches(
        graph,
        solution,
        max_switches=4,
        prefix_sizes=(1, 2, 4),
    )
    assert result.improved
    assert result.best_prefix_size == 1
    assert result.best_official.total_cycles == 404
    assert result.best_safe.ok
    assert result.best_solution.spills == solution.spills
    final_q2 = validate_q2_solution(graph, result.best_solution)
    final_q2.require_ok()
    assert final_q2.spill_count == 1


def test_formal_iterative_spill_batch_fresh_reranks_until_saturation() -> None:
    graph, solution = _fixture()
    result = optimize_q3_critical_spill_batches(
        graph,
        solution,
        max_rounds=4,
        max_switches=4,
        prefix_sizes=(1, 2, 4),
    )
    assert result.improved
    assert result.accepted_rounds == 1
    assert result.saturated
    assert len(result.rounds) == 2
    assert result.rounds[0].best_prefix_size == 1
    assert result.final_official.total_cycles == 404
    assert result.final_safe.ok
    assert result.final_solution.spills == solution.spills


def test_formal_iterative_spill_batch_rejects_empty_prefix_portfolio() -> None:
    graph, solution = _fixture()
    try:
        optimize_q3_critical_spill_batches(
            graph,
            solution,
            max_switches=4,
            prefix_sizes=(8, 16),
        )
    except ValueError as exc:
        assert "prefix_sizes" in str(exc)
    else:
        raise AssertionError("expected ValueError for an empty normalized prefix portfolio")
