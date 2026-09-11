from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from parser import load_case
from q2_model import CACHE_CAPACITIES, Q2Solution, SpillRecord, spill_traffic_cost
from q2_validator import validate_q2_solution

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)


def _parse_integral_token(token: str, *, context: str) -> int:
    """Accept integer text and integer-valued decimal text such as ``256.0``.

    Some preserved competition outputs were written by pandas/numpy and use
    ``BufId:Offset`` lines like ``9.0:256.0``.  The official fields are still
    integral; silently rounding a non-integral value would corrupt evidence, so
    decimals are accepted only when they represent an exact integer.
    """

    try:
        value = Decimal(token.strip())
    except InvalidOperation as exc:
        raise ValueError(f"{context}: invalid numeric token {token!r}") from exc
    if not value.is_finite() or value != value.to_integral_value():
        raise ValueError(f"{context}: expected integral value, got {token!r}")
    return int(value)


def _read_schedule(path: Path) -> tuple[int, ...]:
    schedule: list[int] = []
    for line_num, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        schedule.append(_parse_integral_token(line, context=f"{path}:{line_num}"))
    return tuple(schedule)


def _read_mapping(path: Path) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for line_num, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            left, right = line.split(":", 1)
        except ValueError as exc:
            raise ValueError(f"{path}:{line_num}: expected 'BufId:Offset', got {raw!r}") from exc
        key = _parse_integral_token(left, context=f"{path}:{line_num}:BufId")
        value = _parse_integral_token(right, context=f"{path}:{line_num}:Offset")
        if key in mapping:
            raise ValueError(f"{path}:{line_num}: duplicate BufId {key}")
        mapping[key] = value
    return mapping


def _read_spills(path: Path) -> tuple[SpillRecord, ...]:
    spills: list[SpillRecord] = []
    for line_num, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            left, right = line.split(":", 1)
        except ValueError as exc:
            raise ValueError(f"{path}:{line_num}: expected 'BufId:NewOffset', got {raw!r}") from exc
        spills.append(
            SpillRecord(
                _parse_integral_token(left, context=f"{path}:{line_num}:BufId"),
                _parse_integral_token(right, context=f"{path}:{line_num}:NewOffset"),
            )
        )
    return tuple(spills)


def load_external_solution(directory: Path, case: str) -> Q2Solution:
    return Q2Solution(
        schedule=_read_schedule(directory / f"{case}_schedule.txt"),
        initial_offsets=_read_mapping(directory / f"{case}_memory.txt"),
        spills=_read_spills(directory / f"{case}_spill.txt"),
    )


def _independent_spill_metrics(graph, spills: tuple[SpillRecord, ...]) -> tuple[int, int]:
    """Recompute official traffic from spill rows without trusting external scores.

    This deliberately does *not* establish schedule feasibility.  It is a
    secondary benchmark for preserved outputs whose schedule syntax may be
    non-official.  Each spill target and reload offset is still checked against
    the authoritative buffer metadata and cache capacity before its traffic is
    counted.
    """

    extra_traffic = 0
    for index, spill in enumerate(spills):
        alloc = graph.alloc_node_for_buffer(spill.buf_id)
        if alloc is None or alloc.size is None or alloc.memory_type is None:
            raise ValueError(f"spill[{index}] references unknown buffer {spill.buf_id}")
        capacity = CACHE_CAPACITIES.get(alloc.memory_type)
        if capacity is None:
            raise ValueError(
                f"spill[{index}] buffer {spill.buf_id} has unsupported pool {alloc.memory_type!r}"
            )
        if spill.new_offset < 0 or spill.new_offset + alloc.size > capacity:
            raise ValueError(
                f"spill[{index}] buffer {spill.buf_id} reload range "
                f"[{spill.new_offset},{spill.new_offset + alloc.size}) exceeds "
                f"{alloc.memory_type} capacity {capacity}"
            )
        extra_traffic += spill_traffic_cost(graph, spill.buf_id)
    return len(spills), extra_traffic


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Benchmark external Q2 outputs with strict feasibility replay plus an "
            "independent spill-file traffic recomputation"
        )
    )
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--solution-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    rows: list[dict[str, object]] = []
    all_metric_rows_ok = True
    for case in CASES:
        graph = load_case(args.data_dir, case)
        schedule_path = args.solution_dir / f"{case}_schedule.txt"
        memory_path = args.solution_dir / f"{case}_memory.txt"
        spill_path = args.solution_dir / f"{case}_spill.txt"
        present = all(path.exists() for path in (schedule_path, memory_path, spill_path))

        metric_ok = False
        spill_count: int | str = ""
        extra_traffic: int | str = ""
        metric_errors = ""
        try:
            spills = _read_spills(spill_path)
            spill_count, extra_traffic = _independent_spill_metrics(graph, spills)
            metric_ok = True
        except (FileNotFoundError, ValueError) as exc:
            metric_errors = str(exc)
            all_metric_rows_ok = False

        strict_valid = False
        schedule_length: int | str = ""
        strict_errors = ""
        try:
            solution = load_external_solution(args.solution_dir, case)
            schedule_length = len(solution.schedule)
            result = validate_q2_solution(graph, solution)
            strict_valid = result.ok
            strict_errors = " | ".join(result.errors)
        except (FileNotFoundError, ValueError) as exc:
            strict_errors = str(exc)

        rows.append(
            {
                "case": case,
                "present": present,
                "strict_valid": strict_valid,
                "metric_ok": metric_ok,
                "spill_count": spill_count,
                "extra_traffic": extra_traffic,
                "schedule_length": schedule_length,
                "strict_errors": strict_errors,
                "metric_errors": metric_errors,
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "case",
        "present",
        "strict_valid",
        "metric_ok",
        "spill_count",
        "extra_traffic",
        "schedule_length",
        "strict_errors",
        "metric_errors",
    ]
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    args.out.with_suffix(".json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.out.read_text(encoding="utf-8"))
    return 0 if all_metric_rows_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
