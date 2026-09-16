from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from model import ComputeGraph, Node
from q2_unit_cache_oracle import solve_uniform_unit_cache_oracle


def test_uniform_unit_cache_oracle_uses_farthest_future_page() -> None:
    # Two L1 slots, three equal COPY_IN-backed pages.  At ALLOC(page2), page0 is
    # needed before page1, so Belady must spill page1.  Later reload/free events
    # force two additional evictions.  Total optimum = 3 spills.
    nodes = [
        Node(0, "ALLOC", 0, 1, "L1"),
        Node(1, "COPY_IN", pipe="MTE2", cycles=1, bufs=(0,)),
        Node(2, "ALLOC", 1, 1, "L1"),
        Node(3, "COPY_IN", pipe="MTE2", cycles=1, bufs=(1,)),
        Node(4, "ALLOC", 2, 1, "L1"),
        Node(5, "COPY_IN", pipe="MTE2", cycles=1, bufs=(2,)),
        Node(6, "USE", pipe="VECTOR", cycles=1, bufs=(0,)),
        Node(7, "USE", pipe="VECTOR", cycles=1, bufs=(1,)),
        Node(8, "USE", pipe="VECTOR", cycles=1, bufs=(2,)),
        Node(9, "FREE", 0, 1, "L1"),
        Node(10, "FREE", 1, 1, "L1"),
        Node(11, "FREE", 2, 1, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [
            (0, 1), (1, 6), (6, 9),
            (2, 3), (3, 7), (7, 10),
            (4, 5), (5, 8), (8, 11),
        ],
    )
    result = solve_uniform_unit_cache_oracle(
        graph,
        tuple(range(12)),
        memory_type="L1",
        capacity=2,
    )
    assert result.page_size == 1
    assert result.slots == 2
    assert result.traffic_per_spill == 1
    assert result.spill_count == 3
    assert result.extra_traffic == 3


def test_uniform_unit_cache_oracle_handles_atomic_required_set() -> None:
    # Three equal pages, capacity two. Page0 and page1 must be simultaneously
    # resident for node6; page2 may be evicted but neither required page may be.
    nodes = [
        Node(0, "ALLOC", 0, 1, "L1"),
        Node(1, "COPY_IN", pipe="MTE2", cycles=1, bufs=(0,)),
        Node(2, "ALLOC", 1, 1, "L1"),
        Node(3, "COPY_IN", pipe="MTE2", cycles=1, bufs=(1,)),
        Node(4, "ALLOC", 2, 1, "L1"),
        Node(5, "COPY_IN", pipe="MTE2", cycles=1, bufs=(2,)),
        Node(6, "PAIR", pipe="VECTOR", cycles=1, bufs=(0, 1)),
        Node(7, "FREE", 0, 1, "L1"),
        Node(8, "FREE", 1, 1, "L1"),
        Node(9, "FREE", 2, 1, "L1"),
    ]
    graph = ComputeGraph.from_edges(
        nodes,
        [
            (0, 1), (1, 6), (6, 7),
            (2, 3), (3, 6), (6, 8),
            (4, 5), (5, 9),
        ],
    )
    result = solve_uniform_unit_cache_oracle(
        graph,
        tuple(range(10)),
        memory_type="L1",
        capacity=2,
    )
    assert result.spill_count >= 1
