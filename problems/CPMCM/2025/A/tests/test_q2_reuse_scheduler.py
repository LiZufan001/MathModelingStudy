from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_reuse_scheduler import Q2ReuseScheduleConfig, schedule_q2_reuse_aware
from validators import validate_buffer_lifetimes


def test_reuse_scheduler_clusters_ready_operations_that_share_a_hot_buffer() -> None:
    # Both L1 buffers must be allocated before any USE node becomes ready.  The
    # baseline id order would alternate A/B as 2,3,4,5.  Reuse awareness should
    # keep A hot and choose node 4 after node 2, then FREE A immediately.
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
