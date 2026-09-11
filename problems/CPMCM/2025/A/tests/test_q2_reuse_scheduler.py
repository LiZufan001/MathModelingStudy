from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_reuse_scheduler import (
    Q2ReuseScheduleConfig,
    _build_l0_counted_footprints,
    _counted_buffer_sizes,
    schedule_q2_reuse_aware,
)
from validators import validate_buffer_lifetimes


def test_reuse_scheduler_clusters_ready_operations_that_share_a_hot_buffer() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 1, "L1"),
        Node(1, "ALLOC", 1, 1, "L1"),
        Node(2, "USE", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(3, "USE", pipe="VECTOR", cycles=1, bufs=(1,)),
        Node(4, "USE", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(5, "USE", pipe="VECTOR", cycles=1, bufs=(1,)),
        Node(6, "FREE", 0, 1, "L1"),
        Node(7, "FREE", 1, 1, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [
            (0, 2), (0, 4),
            (1, 2), (1, 3), (1, 4), (1, 5),
            (2, 6), (4, 6),
            (3, 7), (5, 7),
        ],
    )
    result = schedule_q2_reuse_aware(
        graph,
        Q2ReuseScheduleConfig(hot_window=4, release_weight=1, probe_per_buffer=8),
    )
    assert result.order == (0, 1, 2, 4, 6, 3, 5, 7)
    assert result.affinity_decisions >= 1
    assert result.footprint_decisions == 0
    assert result.evaluation.valid


def test_reuse_scheduler_preserves_single_live_buffer_per_l0_type() -> None:
    nodes = [
        Node(0, "ALLOC", 0, 1, "L0A"),
        Node(1, "USE", pipe="CUBE", cycles=1, bufs=(0,)),
        Node(2, "FREE", 0, 1, "L0A"),
        Node(3, "ALLOC", 1, 1, "L0A"),
        Node(4, "USE", pipe="CUBE", cycles=1, bufs=(1,)),
        Node(5, "FREE", 1, 1, "L0A"),
    ]
    graph = ComputeGraph.from_edges(nodes, [(0, 1), (1, 2), (3, 4), (4, 5)])
    result = schedule_q2_reuse_aware(graph)
    assert result.order == (0, 1, 2, 3, 4, 5)
    validation = validate_buffer_lifetimes(graph, result.order)
    assert validation.ok, validation.errors


def test_two_hop_l0_footprint_reaches_counted_buffer_through_local_buffer() -> None:
    nodes = [
        Node(0, "ALLOC", 10, 1, "L0C"),
        Node(1, "ALLOC", 11, 1, "L0A"),
        Node(2, "ALLOC", 20, 7, "L1"),
        Node(3, "MOVE", pipe="MTE1", cycles=1, bufs=(11, 20)),
        Node(4, "MATMUL", pipe="CUBE", cycles=1, bufs=(10, 11)),
        Node(5, "FREE", 10, 1, "L0C"),
        Node(6, "FREE", 11, 1, "L0A"),
        Node(7, "FREE", 20, 7, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [(0, 4), (1, 3), (2, 3), (3, 4), (4, 5), (4, 6), (4, 7)],
    )
    footprints = _build_l0_counted_footprints(graph, _counted_buffer_sizes(graph))
    assert footprints[0] == (20,)


def test_footprint_affinity_changes_which_ready_l0_task_opens_next() -> None:
    # Three independent L0C tasks are ready from the start.  Task 0 and task 2
    # share L1 buffer 100; task 1 uses L1 buffer 101.  Node-id order would open
    # task 1 after task 0, while footprint affinity should choose task 2.
    nodes = [
        Node(0, "ALLOC", 10, 1, "L0C"),
        Node(1, "ALLOC", 11, 1, "L0C"),
        Node(2, "ALLOC", 12, 1, "L0C"),
        Node(3, "ALLOC", 100, 1, "L1"),
        Node(4, "ALLOC", 101, 1, "L1"),
        Node(5, "USE", pipe="CUBE", cycles=1, bufs=(10, 100)),
        Node(6, "FREE", 10, 1, "L0C"),
        Node(7, "USE", pipe="CUBE", cycles=1, bufs=(11, 101)),
        Node(8, "FREE", 11, 1, "L0C"),
        Node(9, "USE", pipe="CUBE", cycles=1, bufs=(12, 100)),
        Node(10, "FREE", 12, 1, "L0C"),
        Node(11, "FREE", 100, 1, "L1"),
        Node(12, "FREE", 101, 1, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [
            (0, 5), (3, 5), (5, 6),
            (1, 7), (4, 7), (7, 8),
            (2, 9), (3, 9), (9, 10),
            (5, 11), (9, 11),
            (7, 12),
        ],
    )
    result = schedule_q2_reuse_aware(
        graph,
        Q2ReuseScheduleConfig(
            hot_window=1,
            release_weight=0,
            probe_per_buffer=8,
            footprint_weight=1,
            footprint_min_buffers=1,
        ),
    )
    assert result.order.index(2) < result.order.index(1)
    assert result.footprint_decisions >= 1
    validation = validate_buffer_lifetimes(graph, result.order)
    assert validation.ok, validation.errors
