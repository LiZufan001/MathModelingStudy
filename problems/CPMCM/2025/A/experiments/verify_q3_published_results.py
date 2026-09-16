from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _dominates(a: dict[str, str], b: dict[str, str]) -> bool:
    a_t, a_c = int(a["extra_traffic"]), int(a["official_cycles"])
    b_t, b_c = int(b["extra_traffic"]), int(b["official_cycles"])
    return a_t <= b_t and a_c <= b_c and (a_t < b_t or a_c < b_c)


def _key(row: dict) -> tuple[str, str, str, int, int, float, int]:
    return (
        str(row["case"]),
        str(row["variant"]),
        str(row["sequence"]),
        int(row["extra_traffic"]),
        int(row["official_cycles"]),
        round(float(row["official_improvement_pct"]), 6),
        int(row["safe_cycles"]),
    )


def _csv_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise AssertionError(f"unexpected CSV boolean {value!r}")


def _assert_close(actual: float, expected: float, *, label: str) -> None:
    if abs(actual - expected) > 5e-7:
        raise AssertionError(f"{label}: {actual:.6f} != {expected:.6f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--formal-summary", type=Path, required=True)
    ap.add_argument("--formal-summary-json", type=Path, required=True)
    ap.add_argument("--frontier", type=Path, required=True)
    ap.add_argument("--reconcile-report", type=Path, required=True)
    args = ap.parse_args()

    formal = _read_csv(args.formal_summary)
    formal_json = json.loads(args.formal_summary_json.read_text(encoding="utf-8"))
    frontier = _read_csv(args.frontier)
    report = json.loads(args.reconcile_report.read_text(encoding="utf-8"))

    if len(formal) != 6:
        raise AssertionError(f"expected 6 formal fixed-traffic rows, got {len(formal)}")

    json_cases = formal_json.get("cases")
    if not isinstance(json_cases, list) or len(json_cases) != 6:
        raise AssertionError("formal JSON must contain exactly 6 case rows")
    json_by_case = {str(row["case"]): row for row in json_cases}
    csv_cases = {row["case"] for row in formal}
    if len(json_by_case) != 6 or set(json_by_case) != csv_cases:
        raise AssertionError("formal CSV and JSON case sets differ")

    int_fields = (
        "raw_official_cycles",
        "core_official_cycles",
        "final_official_cycles",
        "core_safe_cycles",
        "final_safe_cycles",
        "spill_count",
        "extra_traffic",
        "accepted_spill_batch_rounds",
        "spill_batch_round_count",
        "safe_overlap_errors",
    )
    bool_fields = ("spill_batch_saturated", "valid")
    for csv_row in formal:
        case = csv_row["case"]
        json_row = json_by_case[case]
        for field in int_fields:
            csv_value = int(csv_row[field])
            json_value = int(json_row[field])
            if csv_value != json_value:
                raise AssertionError(
                    f"formal CSV/JSON drift for {case} {field}: "
                    f"{csv_value} != {json_value}"
                )
        for field in bool_fields:
            csv_value = _csv_bool(csv_row[field])
            json_value = bool(json_row[field])
            if csv_value != json_value:
                raise AssertionError(
                    f"formal CSV/JSON drift for {case} {field}: "
                    f"{csv_value} != {json_value}"
                )

        raw_cycles = int(csv_row["raw_official_cycles"])
        core_cycles = int(csv_row["core_official_cycles"])
        final_cycles = int(csv_row["final_official_cycles"])
        expected_vs_core = core_cycles - final_cycles
        actual_vs_core = int(csv_row["improvement_vs_core_cycles"])
        if actual_vs_core != expected_vs_core:
            raise AssertionError(
                f"formal improvement_vs_core drift for {case}: "
                f"{actual_vs_core} != {expected_vs_core}"
            )
        expected_vs_raw_pct = round((raw_cycles - final_cycles) * 100.0 / raw_cycles, 6)
        _assert_close(
            float(csv_row["improvement_vs_raw_pct"]),
            expected_vs_raw_pct,
            label=f"formal improvement_vs_raw_pct drift for {case}",
        )

    if not frontier:
        raise AssertionError("refined frontier is empty")
    if any(row.get("strict_valid", "").lower() != "true" for row in frontier):
        raise AssertionError("published refined frontier contains a non-strict-valid row")

    zero_rows = {
        row["case"]: row
        for row in frontier
        if row["variant"] == "zero_traffic" and row["sequence"] == "0"
    }
    if set(zero_rows) != csv_cases:
        raise AssertionError("formal summary and refined zero-traffic case sets differ")

    for row in formal:
        case = row["case"]
        published = zero_rows[case]
        expected = (
            int(row["extra_traffic"]),
            int(row["final_official_cycles"]),
            int(row["final_safe_cycles"]),
        )
        actual = (
            int(published["extra_traffic"]),
            int(published["official_cycles"]),
            int(published["safe_cycles"]),
        )
        if actual != expected:
            raise AssertionError(
                f"published zero-traffic row drifted for {case}: {actual} != {expected}"
            )
        _assert_close(
            float(published["official_improvement_pct"]),
            float(row["improvement_vs_raw_pct"]),
            label=f"published zero-traffic improvement pct drift for {case}",
        )

    for case in sorted({row["case"] for row in frontier}):
        rows = [row for row in frontier if row["case"] == case]
        for row in rows:
            if any(other is not row and _dominates(other, row) for other in rows):
                raise AssertionError(f"published frontier contains dominated row: {_key(row)}")

    report_kept = {_key(row) for row in report["kept"]}
    published_kept = {_key(row) for row in frontier}
    if report_kept != published_kept:
        missing = sorted(published_kept - report_kept)
        extra = sorted(report_kept - published_kept)
        raise AssertionError(f"reconciliation report/CSV drift: missing={missing}, extra={extra}")

    print(
        json.dumps(
            {
                "formal_rows": len(formal),
                "formal_json_rows": len(json_cases),
                "frontier_rows": len(frontier),
                "cases": sorted(zero_rows),
                "dominated_removed": len(report.get("dominated_removed", [])),
                "ok": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
