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


def _key(row: dict) -> tuple[str, str, str, int, int, int]:
    return (
        str(row["case"]),
        str(row["variant"]),
        str(row["sequence"]),
        int(row["extra_traffic"]),
        int(row["official_cycles"]),
        int(row["safe_cycles"]),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--formal-summary", type=Path, required=True)
    ap.add_argument("--frontier", type=Path, required=True)
    ap.add_argument("--reconcile-report", type=Path, required=True)
    args = ap.parse_args()

    formal = _read_csv(args.formal_summary)
    frontier = _read_csv(args.frontier)
    report = json.loads(args.reconcile_report.read_text(encoding="utf-8"))

    if len(formal) != 6:
        raise AssertionError(f"expected 6 formal fixed-traffic rows, got {len(formal)}")
    if not frontier:
        raise AssertionError("refined frontier is empty")
    if any(row.get("strict_valid", "").lower() != "true" for row in frontier):
        raise AssertionError("published refined frontier contains a non-strict-valid row")

    zero_rows = {
        row["case"]: row
        for row in frontier
        if row["variant"] == "zero_traffic" and row["sequence"] == "0"
    }
    if set(zero_rows) != {row["case"] for row in formal}:
        raise AssertionError("formal summary and refined zero-traffic case sets differ")

    for row in formal:
        published = zero_rows[row["case"]]
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
                f"published zero-traffic row drifted for {row['case']}: {actual} != {expected}"
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
