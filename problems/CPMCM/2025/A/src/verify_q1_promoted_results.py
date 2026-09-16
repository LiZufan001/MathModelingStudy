from __future__ import annotations

import argparse
import csv
from pathlib import Path

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    by_case = {row["case"]: row for row in rows}
    if set(by_case) != set(CASES) or len(rows) != len(CASES):
        raise SystemExit(f"{path}: expected exactly six canonical cases, got {list(by_case)}")
    return by_case


def as_int(row: dict[str, str], key: str) -> int:
    return int(row[key])


def as_float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify published Q1 promoted results against a fresh policy comparison")
    ap.add_argument("--comparison", type=Path, required=True)
    ap.add_argument("--published", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    args = ap.parse_args()

    comparison = read_rows(args.comparison)
    published = read_rows(args.published)
    baseline = read_rows(args.baseline)

    for case in CASES:
        got = comparison[case]
        pub = published[case]
        base = baseline[case]

        checks = {
            "nodes": (as_int(pub, "nodes"), as_int(got, "nodes")),
            "edges": (as_int(pub, "edges"), as_int(got, "edges")),
            "baseline_peak_vs_comparison": (as_int(pub, "baseline_peak"), as_int(got, "baseline_peak")),
            "baseline_peak_vs_published_baseline": (as_int(pub, "baseline_peak"), as_int(base, "peak_residency")),
            "promoted_peak": (as_int(pub, "promoted_peak"), as_int(got, "best_peak")),
            "absolute_reduction": (
                as_int(pub, "absolute_reduction_vs_baseline"),
                as_int(got, "absolute_reduction_vs_baseline"),
            ),
        }
        for label, (actual, expected) in checks.items():
            if actual != expected:
                raise SystemExit(f"{case}: {label} mismatch: published={actual}, fresh={expected}")

        if pub["promoted_method"] != got["best_method"]:
            raise SystemExit(
                f"{case}: promoted_method mismatch: published={pub['promoted_method']}, fresh={got['best_method']}"
            )
        if pub["valid"].lower() != "true":
            raise SystemExit(f"{case}: published valid flag is not True")
        if as_int(pub, "promoted_peak") > as_int(pub, "baseline_peak"):
            raise SystemExit(f"{case}: promoted peak regressed above baseline")

        expected_pct = 100.0 * as_float(got, "relative_reduction_vs_baseline")
        actual_pct = as_float(pub, "improvement_vs_baseline_pct")
        if abs(actual_pct - expected_pct) > 5e-7:
            raise SystemExit(
                f"{case}: improvement pct mismatch: published={actual_pct}, fresh={expected_pct}"
            )

    print("Q1 promoted published results match fresh six-case policy comparison and baseline summary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
