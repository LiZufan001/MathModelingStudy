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


def test_task_anchor_routes_subordinate_l0_and_counted_allocs_together() -> None:
    # Task 0 and task 2 share L1=100.  Task 1 has smaller ids for both its L0C
    # and L0A roots, so changing only the outer L0C order would pick L0A=21 from
    # task 1, which cannot complete while task 2's L0C is live.  Coherent routing
    # must instead pick task 2's L0A=22 and keep the schedule feasible.
    nodes = [
        Node(0, "ALLOC", 10, 1, "L0C"),
        Node(1, "ALLOC", 11, 1, "L0C"),
        Node(2, "ALLOC", 12, 1, "L0C"),
        Node(3, "ALLOC", 20, 1, "L0A"),
        Node(4, "ALLOC", 21, 1, "L0A"),
        Node(5, "ALLOC", 22, 1, "L0A"),
        Node(6, "ALLOC", 100, 1, "L1"),
        Node(7, "ALLOC", 101, 1, "L1"),
        Node(8, "MOVE", pipe="MTE1", cycles=1, bufs=(20, 100)),
        Node(9, "MATMUL", pipe="CUBE", cycles=1, bufs=(10, 20)),
        Node(10, "FREE", 20, 1, "L0A"),
        Node(11, "FREE", 10, 1, "L0C"),
        Node(12, "MOVE", pipe="MTE1", cycles=1, bufs=(21, 101)),
        Node(13, "MATMUL", pipe="CUBE", cycles=1, bufs=(11, 21)),
        Node(14, "FREE", 21, 1, "L0A"),
        Node(15, "FREE", 11, 1, "L0C"),
        Node(16, "MOVE", pipe="MTE1", cycles=1, bufs=(22, 100)),
        Node(17, "MATMUL", pipe="CUBE", cycles=1, bufs=(12, 22)),
        Node(18, "FREE", 22, 1, "L0A"),
        Node(19, "FREE", 12, 1, "L0C"),
        Node(20, "FREE", 100, 1, "L1"),
        Node(21, "FREE", 101, 1, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [
            (3, 8), (6, 8), (8, 9), (0, 9), (9, 10), (9, 11),
            (4, 12), (7, 12), (12, 13), (1, 13), (13, 14), (13, 15),
            (5, 16), (6, 16), (16, 17), (2, 17), (17, 18), (17, 19),
            (8, 20), (16, 20), (12, 21),
        ],
    )
    result = schedule_q2_reuse_aware(
        graph,
        Q2ReuseScheduleConfig(
            hot_window=1,
            release_weight=0,
            probe_per_buffer=16,
            footprint_weight=1,
            footprint_min_buffers=1,
        ),
    )
    assert result.order.index(2) < result.order.index(1)
    assert result.order.index(5) < result.order.index(4)
    assert result.footprint_decisions >= 2
    validation = validate_buffer_lifetimes(graph, result.order)
    assert validation.ok, validation.errors


def test_l0b_footprint_does_not_become_global_task_anchor() -> None:
    # L0B=10 has a counted footprint through L1=101.  If input-side L0B were
    # allowed to become the global task anchor, it would pull ALLOC 2 ahead of
    # the unrelated lower-id ALLOC 1.  L0C-only anchoring must leave that order
    # unchanged while still treating L0B as an ordinary single-live L0 buffer.
    nodes = [
        Node(0, "ALLOC", 10, 1, "L0B"),
        Node(1, "ALLOC", 100, 1, "L1"),
        Node(2, "ALLOC", 101, 1, "L1"),
        Node(3, "MOVE", pipe="MTE1", cycles=1, bufs=(10, 101)),
        Node(4, "USE", pipe="VECTOR", cycles=1, bufs=(100,)),
        Node(5, "FREE", 10, 1, "L0B"),
        Node(6, "FREE", 100, 1, "L1"),
        Node(7, "FREE", 101, 1, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [(0, 3), (2, 3), (3, 5), (3, 7), (1, 4), (4, 6)],
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
    assert result.order.index(1) < result.order.index(2)
    validation = validate_buffer_lifetimes(graph, result.order)
    assert validation.ok, validation.errors


def test_l0b_has_no_standalone_footprint_chaining_without_l0c_anchor() -> None:
    # Three independent input-side L0B tasks are ready. Task 0 and task 2 share
    # counted L1=100, while task 1 uses L1=101. Without an active L0C task,
    # finishing task 0 must not use its last footprint to jump from task 1 to
    # task 2; standalone cross-task chaining is reserved for L0C.
    nodes = [
        Node(0, "ALLOC", 10, 1, "L0B"),
        Node(1, "ALLOC", 11, 1, "L0B"),
        Node(2, "ALLOC", 12, 1, "L0B"),
        Node(3, "ALLOC", 100, 1, "L1"),
        Node(4, "ALLOC", 101, 1, "L1"),
        Node(5, "MOVE", pipe="MTE1", cycles=1, bufs=(10, 100)),
        Node(6, "FREE", 10, 1, "L0B"),
        Node(7, "MOVE", pipe="MTE1", cycles=1, bufs=(11, 101)),
        Node(8, "FREE", 11, 1, "L0B"),
        Node(9, "MOVE", pipe="MTE1", cycles=1, bufs=(12, 100)),
        Node(10, "FREE", 12, 1, "L0B"),
        Node(11, "FREE", 100, 1, "L1"),
        Node(12, "FREE", 101, 1, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [
            (0, 5), (3, 5), (5, 6),
            (1, 7), (4, 7), (7, 8),
            (2, 9), (3, 9), (9, 10),
            (5, 11), (9, 11), (7, 12),
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
    assert result.order.index(1) < result.order.index(2)
    assert result.footprint_decisions == 0
    validation = validate_buffer_lifetimes(graph, result.order)
    assert validation.ok, validation.errors
