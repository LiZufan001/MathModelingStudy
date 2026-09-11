from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from evaluator import evaluate_q1
from model import ComputeGraph, Node
from parser import load_graph
from q1_scheduler import schedule_q1_baseline
from validators import validate_topological_order


def diamond_graph() -> ComputeGraph:
    nodes = [
        Node(0, "ALLOC", 0, 10, "L1"),
        Node(1, "OP", pipe="VECTOR", cycles=2, bufs=(0,)),
        Node(2, "ALLOC", 1, 20, "UB"),
        Node(3, "OP", pipe="VECTOR", cycles=2, bufs=(1,)),
        Node(4, "FREE", 0, 10, "L1"),
        Node(5, "FREE", 1, 20, "UB"),
    ]
    edges = [(0, 1), (1, 4), (2, 3), (3, 5)]
    return ComputeGraph.from_edges(nodes, edges)


def test_topology_rejects_dependency_violation() -> None:
    graph = diamond_graph()
    result = validate_topological_order(graph, [1, 0, 4, 2, 3, 5])
    assert not result.ok
    assert any("0 must precede 1" in e for e in result.errors)


def test_q1_peak_is_recomputed_from_order() -> None:
    graph = diamond_graph()
    eval_ = evaluate_q1(graph, [0, 1, 4, 2, 3, 5])
    assert eval_.valid
    assert eval_.peak_residency == 20


def test_q1_baseline_prefers_free_before_independent_alloc() -> None:
    graph = diamond_graph()
    result = schedule_q1_baseline(graph)
    assert result.evaluation.valid
    assert result.evaluation.peak_residency == 20
    assert result.order.index(4) < result.order.index(2)


def test_l0_constraint_blocks_second_live_buffer() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 8, "L0A"),
        Node(1, "FREE", 0, 8, "L0A"),
        Node(2, "ALLOC", 1, 8, "L0A"),
        Node(3, "FREE", 1, 8, "L0A"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (2, 3)])
    result = schedule_q1_baseline(graph)
    assert result.evaluation.valid
    assert result.order.index(1) < result.order.index(2) or result.order.index(3) < result.order.index(0)


def test_parser_matches_official_csv_shape(tmp_path: Path) -> None:
    nodes = tmp_path / "sample_Nodes.csv"
    edges = tmp_path / "sample_Edges.csv"
    nodes.write_text(
        'Id,Op,BufId,Size,Type,Pipe,Cycles,Bufs\n'
        '0,ALLOC,0,256,L0C,,,\n'
        '1,ALLOC,1,128,L1,,,\n'
        '2,COPY_IN,,,,MTE2,325,"1"\n'
        '3,FREE,1,128,L1,,,\n'
        '4,FREE,0,256,L0C,,,\n',
        encoding="utf-8",
    )
    edges.write_text('StartNodeId,EndNodeId\n1,2\n2,3\n0,4\n', encoding="utf-8")
    graph = load_graph(nodes, edges)
    assert graph.node_count == 5
    assert graph.edge_count == 3
    assert graph.nodes[2].bufs == (1,)
    assert graph.nodes[2].pipe == "MTE2"


def test_scheduler_rejects_cycle() -> None:
    nodes = [Node(0, "OP"), Node(1, "OP")]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (1, 0)])
    with pytest.raises(ValueError, match="cyclic or unschedulable"):
        schedule_q1_baseline(graph)
