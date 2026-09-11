from __future__ import annotations

import csv
from pathlib import Path

from model import ComputeGraph, MEMORY_TYPES, Node

NODE_COLUMNS = {"Id", "Op", "BufId", "Size", "Type", "Pipe", "Cycles", "Bufs"}
EDGE_COLUMNS = {"StartNodeId", "EndNodeId"}


def _none_if_blank(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _optional_int(value: str | None, field: str, row_num: int) -> int | None:
    value = _none_if_blank(value)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"row {row_num}: {field} must be integer, got {value!r}") from exc


def _parse_bufs(value: str | None, row_num: int) -> tuple[int, ...]:
    value = _none_if_blank(value)
    if value is None:
        return ()
    try:
        return tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise ValueError(f"row {row_num}: invalid Bufs field {value!r}") from exc


def load_nodes_csv(path: str | Path) -> list[Node]:
    path = Path(path)
    nodes: list[Node] = []
    seen_ids: set[int] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or not NODE_COLUMNS.issubset(reader.fieldnames):
            raise ValueError(f"{path}: unexpected node columns {reader.fieldnames}")
        for row_num, row in enumerate(reader, start=2):
            node_id = _optional_int(row.get("Id"), "Id", row_num)
            if node_id is None:
                raise ValueError(f"row {row_num}: Id is required")
            if node_id in seen_ids:
                raise ValueError(f"row {row_num}: duplicate node Id {node_id}")
            seen_ids.add(node_id)

            op = (_none_if_blank(row.get("Op")) or "").upper()
            if not op:
                raise ValueError(f"row {row_num}: Op is required")
            buf_id = _optional_int(row.get("BufId"), "BufId", row_num)
            size = _optional_int(row.get("Size"), "Size", row_num)
            mem_type = _none_if_blank(row.get("Type"))
            pipe = _none_if_blank(row.get("Pipe"))
            cycles = _optional_int(row.get("Cycles"), "Cycles", row_num)
            bufs = _parse_bufs(row.get("Bufs"), row_num)

            if op in {"ALLOC", "FREE"}:
                if buf_id is None or size is None or mem_type is None:
                    raise ValueError(f"row {row_num}: {op} requires BufId, Size and Type")
                if size < 0:
                    raise ValueError(f"row {row_num}: Size must be non-negative")
                if mem_type not in MEMORY_TYPES:
                    raise ValueError(f"row {row_num}: unknown memory Type {mem_type!r}")
            else:
                if cycles is not None and cycles < 0:
                    raise ValueError(f"row {row_num}: Cycles must be non-negative")

            nodes.append(Node(node_id, op, buf_id, size, mem_type, pipe, cycles, bufs))
    return nodes


def load_edges_csv(path: str | Path) -> list[tuple[int, int]]:
    path = Path(path)
    edges: list[tuple[int, int]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or not EDGE_COLUMNS.issubset(reader.fieldnames):
            raise ValueError(f"{path}: unexpected edge columns {reader.fieldnames}")
        for row_num, row in enumerate(reader, start=2):
            u = _optional_int(row.get("StartNodeId"), "StartNodeId", row_num)
            v = _optional_int(row.get("EndNodeId"), "EndNodeId", row_num)
            if u is None or v is None:
                raise ValueError(f"row {row_num}: both edge endpoints are required")
            edges.append((u, v))
    return edges


def load_graph(nodes_path: str | Path, edges_path: str | Path) -> ComputeGraph:
    return ComputeGraph.from_edges(load_nodes_csv(nodes_path), load_edges_csv(edges_path))


def load_case(data_dir: str | Path, case_name: str) -> ComputeGraph:
    data_dir = Path(data_dir)
    return load_graph(data_dir / f"{case_name}_Nodes.csv", data_dir / f"{case_name}_Edges.csv")
