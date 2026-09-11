from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

MEMORY_TYPES = {"L1", "UB", "L0A", "L0B", "L0C"}
L0_TYPES = {"L0A", "L0B", "L0C"}
Q1_COUNTED_TYPES = {"L1", "UB"}


@dataclass(frozen=True, slots=True)
class Node:
    id: int
    op: str
    buf_id: int | None = None
    size: int | None = None
    memory_type: str | None = None
    pipe: str | None = None
    cycles: int | None = None
    bufs: tuple[int, ...] = ()

    @property
    def is_alloc(self) -> bool:
        return self.op == "ALLOC"

    @property
    def is_free(self) -> bool:
        return self.op == "FREE"

    @property
    def is_memory_event(self) -> bool:
        return self.is_alloc or self.is_free


@dataclass(slots=True)
class ComputeGraph:
    nodes: dict[int, Node]
    successors: dict[int, list[int]]
    predecessors: dict[int, list[int]]
    edge_count: int
    _alloc_by_buf: dict[int, int] = field(default_factory=dict)
    _free_by_buf: dict[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for node_id in self.nodes:
            self.successors.setdefault(node_id, [])
            self.predecessors.setdefault(node_id, [])

        for node in self.nodes.values():
            if node.is_alloc:
                if node.buf_id is None:
                    raise ValueError(f"ALLOC node {node.id} has no BufId")
                if node.buf_id in self._alloc_by_buf:
                    raise ValueError(f"duplicate ALLOC for buffer {node.buf_id}")
                self._alloc_by_buf[node.buf_id] = node.id
            elif node.is_free:
                if node.buf_id is None:
                    raise ValueError(f"FREE node {node.id} has no BufId")
                if node.buf_id in self._free_by_buf:
                    raise ValueError(f"duplicate FREE for buffer {node.buf_id}")
                self._free_by_buf[node.buf_id] = node.id

        # Static integrity check: whenever both ends of a buffer lifetime are present,
        # they must describe exactly the same physical buffer. A mismatch here would
        # make every later residency calculation ambiguous, so fail at graph build time.
        for buf_id in self._alloc_by_buf.keys() & self._free_by_buf.keys():
            alloc = self.nodes[self._alloc_by_buf[buf_id]]
            free = self.nodes[self._free_by_buf[buf_id]]
            if alloc.size != free.size or alloc.memory_type != free.memory_type:
                raise ValueError(
                    f"buffer {buf_id} ALLOC/FREE metadata mismatch: "
                    f"ALLOC(size={alloc.size}, type={alloc.memory_type}) vs "
                    f"FREE(size={free.size}, type={free.memory_type})"
                )

    @classmethod
    def from_edges(cls, nodes: Iterable[Node], edges: Iterable[tuple[int, int]]) -> "ComputeGraph":
        node_list = list(nodes)
        node_map = {node.id: node for node in node_list}
        if len(node_map) != len(node_list):
            raise ValueError("duplicate node ids")

        succ = {node_id: [] for node_id in node_map}
        pred = {node_id: [] for node_id in node_map}
        count = 0
        seen: set[tuple[int, int]] = set()
        for u, v in edges:
            if u not in node_map or v not in node_map:
                raise ValueError(f"edge ({u}, {v}) references unknown node")
            if u == v:
                raise ValueError(f"self-loop at node {u}")
            if (u, v) in seen:
                continue
            seen.add((u, v))
            succ[u].append(v)
            pred[v].append(u)
            count += 1
        return cls(node_map, succ, pred, count)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    def indegrees(self) -> dict[int, int]:
        return {node_id: len(self.predecessors[node_id]) for node_id in self.nodes}

    def alloc_node_for_buffer(self, buf_id: int) -> Node | None:
        node_id = self._alloc_by_buf.get(buf_id)
        return None if node_id is None else self.nodes[node_id]

    def free_node_for_buffer(self, buf_id: int) -> Node | None:
        node_id = self._free_by_buf.get(buf_id)
        return None if node_id is None else self.nodes[node_id]
