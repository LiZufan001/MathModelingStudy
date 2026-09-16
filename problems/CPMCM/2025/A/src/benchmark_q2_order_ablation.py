from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path

from model import Q1_COUNTED_TYPES
from parser import load_case
from q1_scheduler import schedule_q1_baseline
from q2_allocator import allocate_q2_baseline
from q2_validator import validate_q2_solution
from validators import validate_topological_order

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)

SPILL_MARKER = re.compile(r"^spill_(?:L1|UB)_\d+$", re.IGNORECASE)


def _read_strict_numeric_schedule(path: Path) -> tuple[int, ...]:
    order: list[int] = []
    for line_num, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        token = raw.strip()
        if not token:
            continue
        try:
            value = int(token)
        except ValueError as exc:
            raise ValueError(f"{path}:{line_num}: expected numeric node id, got {token!r}") from exc
        order.append(value)
    return tuple(order)


def _read_q2_original_node_order(path: Path) -> tuple[int, ...]:
    """Remove only the archived team's explicit internal spill markers.

    This is an ablation aid, not a conversion of their solution into an official
    Q2 submission. Any unknown non-numeric token is rejected rather than guessed.
    The remaining original-node order is independently validated before use.
    """

    order: list[int] = []
    for line_num, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        token = raw.strip()
        if not token:
            continue
        if SPILL_MARKER.fullmatch(token):
            continue
        try:
            value = int(token)
        except ValueError as exc:
            raise ValueError(
                f"{path}:{line_num}: unknown non-numeric token {token!r}; "
                "only spill_L1_n / spill_UB_n markers may be filtered"
            ) from exc
        order.append(value)
    return tuple(order)


def _q1_peak_only(graph, order: tuple[int, ...]) -> int:
    """Compute the official Q1 L1+UB residency metric for a topological order.

    Deliberately do not impose the baseline scheduler's extra one-live-L0
    restriction here. Q2 physical feasibility is checked by the allocator and
    independent Q2 replay, which use the actual per-pool capacities and offsets.
    """

    resident = 0
    peak = 0
    for node_id in order:
        node = graph.nodes[node_id]
        if node.memory_type not in Q1_COUNTED_TYPES or node.size is None:
            continue
        if node.is_alloc:
            resident += node.size
            peak = max(peak, resident)
        elif node.is_free:
            resident -= node.size
    if resident != 0:
        raise ValueError(f"non-zero final Q1 L1+UB residency {resident}")
    return peak


def _run_order(graph, case: str, source: str, order: tuple[int, ...]) -> dict[str, object]:
    topo = validate_topological_order(graph, order)
    if not topo.ok:
        return {
            "case": case,
            "order_source": source,
            "order_valid": False,
            "q1_peak": "",
            "spill_count": "",
            "extra_traffic": "",
            "q2_seconds": "",
            "q2_valid": False,
            "errors": " | ".join(topo.errors),
        }

    q1_peak = _q1_peak_only(graph, order)
    start = time.perf_counter()
    try:
        q2 = allocate_q2_baseline(graph, order)
        elapsed = time.perf_counter() - start
        replay = validate_q2_solution(graph, q2.solution)
        replay.require_ok()
        return {
            "case": case,
            "order_source": source,
            "order_valid": True,
            "q1_peak": q1_peak,
            "spill_count": replay.spill_count,
            "extra_traffic": replay.extra_traffic,
            "q2_seconds": round(elapsed, 6),
            "q2_valid": replay.ok,
            "errors": "",
        }
    except (ValueError, AssertionError) as exc:
        elapsed = time.perf_counter() - start
        return {
            "case": case,
            "order_source": source,
            "order_valid": True,
            "q1_peak": q1_peak,
            "spill_count": "",
            "extra_traffic": "",
            "q2_seconds": round(elapsed, 6),
            "q2_valid": False,
            "errors": str(exc),
        }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Hold the strict Q2 allocator fixed and ablate only the original-node order"
    )
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--external-q1-dir", type=Path, required=True)
    ap.add_argument("--external-q2-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--case", choices=CASES, action="append", dest="cases")
    args = ap.parse_args()

    selected = tuple(args.cases) if args.cases else CASES
    rows: list[dict[str, object]] = []
    own_baseline_valid = True

    for case in selected:
        graph = load_case(args.data_dir, case)
        own = schedule_q1_baseline(graph)
        sources = (
            ("ours_q1", tuple(own.order)),
            (
                "archived_q1",
                _read_strict_numeric_schedule(args.external_q1_dir / f"Q1_{case}_schedule.txt"),
            ),
            (
                "archived_q2_original_nodes",
                _read_q2_original_node_order(args.external_q2_dir / f"{case}_schedule.txt"),
            ),
        )
        for source, order in sources:
            row = _run_order(graph, case, source, order)
            rows.append(row)
            if source == "ours_q1" and not (row["order_valid"] and row["q2_valid"]):
                own_baseline_valid = False

    fields = [
        "case",
        "order_source",
        "order_valid",
        "q1_peak",
        "spill_count",
        "extra_traffic",
        "q2_seconds",
        "q2_valid",
        "errors",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    args.out.with_suffix(".json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.out.read_text(encoding="utf-8"))
    return 0 if own_baseline_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
