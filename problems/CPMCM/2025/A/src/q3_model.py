from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from model import Node

ReuseMode = Literal["official_literal", "residency_safe"]


@dataclass(frozen=True, slots=True)
class Q3TimingResult:
    ok: bool
    errors: tuple[str, ...]
    reuse_mode: ReuseMode
    total_cycles: int
    start_times: dict[int, int]
    finish_times: dict[int, int]
    critical_path: tuple[int, ...]
    pipe_busy_cycles: dict[str, int]
    pipe_utilization: dict[str, float]
    original_edge_count: int
    spill_edge_count: int
    reuse_edge_count: int
    pipe_edge_count: int
    physical_overlap_errors: tuple[str, ...]

    def require_ok(self) -> None:
        if not self.ok:
            raise ValueError("; ".join(self.errors))


@dataclass(frozen=True, slots=True)
class Q3DualTimingResult:
    official_literal: Q3TimingResult
    residency_safe: Q3TimingResult


@dataclass(frozen=True, slots=True)
class ResidencyEpoch:
    buf_id: int
    memory_type: str
    start: int
    end: int
    acquire_node: int
    release_node: int


def node_cycles(node: Node) -> int:
    if node.is_memory_event:
        return 0
    if node.cycles is None:
        raise ValueError(f"node {node.id} ({node.op}) has no Cycles")
    if node.cycles < 0:
        raise ValueError(f"node {node.id} ({node.op}) has negative Cycles {node.cycles}")
    return node.cycles
