from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from parser import load_case
from q2_model import Q2Solution, SpillRecord
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


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Strictly benchmark external Q2 submission-format solutions"
    )
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--solution-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    rows: list[dict[str, object]] = []
    all_valid = True
    for case in CASES:
        graph = load_case(args.data_dir, case)
        try:
            solution = load_external_solution(args.solution_dir, case)
            result = validate_q2_solution(graph, solution)
            row = {
                "case": case,
                "present": True,
                "valid": result.ok,
                "spill_count": result.spill_count,
                "extra_traffic": result.extra_traffic,
                "schedule_length": len(solution.schedule),
                "errors": " | ".join(result.errors),
            }
            all_valid = all_valid and result.ok
        except (FileNotFoundError, ValueError) as exc:
            row = {
                "case": case,
                "present": False if isinstance(exc, FileNotFoundError) else True,
                "valid": False,
                "spill_count": "",
                "extra_traffic": "",
                "schedule_length": "",
                "errors": str(exc),
            }
            all_valid = False
        rows.append(row)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "case",
        "present",
        "valid",
        "spill_count",
        "extra_traffic",
        "schedule_length",
        "errors",
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
    return 0 if all_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
