from __future__ import annotations

import sys

import benchmark_q3_conv_local_recolor as benchmark

VALID_CASES = ("Conv_Case0", "Conv_Case1")


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


def main() -> int:
    case = _pop_case(sys.argv)
    benchmark.CASES = (case,)
    return benchmark.main()


if __name__ == "__main__":
    raise SystemExit(main())
