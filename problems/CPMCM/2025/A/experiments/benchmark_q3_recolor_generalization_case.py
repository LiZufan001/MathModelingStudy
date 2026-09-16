from __future__ import annotations

import csv
import sys
from pathlib import Path

import benchmark_q3_conv_local_recolor as benchmark

VALID_CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)

TRIAL_FIELDS = (
    "case",
    "round",
    "buf_id",
    "old_offset",
    "new_offset",
    "q2_valid",
    "safe_valid",
    "official_cycles",
    "safe_cycles",
    "official_reuse_edges",
    "error",
)


def _pop_case(argv: list[str]) -> str:
    try:
        index = argv.index("--case")
    except ValueError as exc:
        raise SystemExit("--case is required") from exc
    if index + 1 >= len(argv):
        raise SystemExit("--case requires a value")
    case = argv[index + 1]
    if case not in VALID_CASES:
        raise SystemExit(f"unsupported --case {case!r}; choose one of {VALID_CASES}")
    del argv[index : index + 2]
    return case


def _empty_safe_write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Preserve an explicit zero-trial result instead of failing on rows[0]."""

    if rows:
        fieldnames = list(rows[0])
    elif path.name == "conv_local_recolor_trials.csv":
        fieldnames = list(TRIAL_FIELDS)
    else:
        raise ValueError(f"unexpected empty CSV payload for {path}")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    case = _pop_case(sys.argv)
    benchmark.CASES = (case,)
    benchmark._write_csv = _empty_safe_write_csv
    return benchmark.main()


if __name__ == "__main__":
    raise SystemExit(main())
