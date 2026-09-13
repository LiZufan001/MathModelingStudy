from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FIELDS = (
    "case",
    "variant",
    "sequence",
    "extra_traffic",
    "traffic_delta",
    "traffic_delta_pct",
    "official_cycles",
    "official_improvement_pct",
    "safe_cycles",
    "strict_valid",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _reference_raw_cycles(path: Path) -> dict[str, int]:
    rows = _read_csv(path)
    return {row["case"]: int(row["baseline_official_cycles"]) for row in rows}


def _fixed_row(payload: dict, raw_cycles: int) -> dict[str, str]:
    final = payload["final"]
    traffic = int(final["extra_traffic"])
    official = int(final["official_cycles"])
    safe = int(final["safe_cycles"])
    improvement = (raw_cycles - official) / raw_cycles * 100.0
    return {
        "case": payload["case"],
        "variant": "zero_traffic",
        "sequence": "0",
        "extra_traffic": str(traffic),
        "traffic_delta": "0",
        "traffic_delta_pct": "0.0",
        "official_cycles": str(official),
        "official_improvement_pct": f"{improvement:.6f}",
        "safe_cycles": str(safe),
        "strict_valid": "True",
    }


def _dominates(a: dict[str, str], b: dict[str, str]) -> bool:
    a_t, a_c = int(a["extra_traffic"]), int(a["official_cycles"])
    b_t, b_c = int(b["extra_traffic"]), int(b["official_cycles"])
    return a_t <= b_t and a_c <= b_c and (a_t < b_t or a_c < b_c)


def _pareto(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    kept: list[dict[str, str]] = []
    dominated: list[dict[str, str]] = []
    for row in rows:
        if row.get("strict_valid", "True").lower() != "true":
            continue
        if any(other is not row and _dominates(other, row) for other in rows):
            dominated.append(row)
        else:
            kept.append(row)
    kept.sort(key=lambda row: (row["case"], int(row["extra_traffic"]), int(row["official_cycles"])))
    dominated.sort(key=lambda row: (row["case"], int(row["extra_traffic"]), int(row["official_cycles"])))
    return kept, dominated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontier", type=Path, required=True)
    ap.add_argument("--baseline-summary", type=Path, required=True)
    ap.add_argument("--fixed-json", type=Path, action="append", default=[], required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    old_rows = _read_csv(args.frontier)
    raw_cycles = _reference_raw_cycles(args.baseline_summary)
    fixed_payloads = [json.loads(path.read_text(encoding="utf-8")) for path in args.fixed_json]
    fixed_cases = {payload["case"] for payload in fixed_payloads}

    candidates = [
        {field: row[field] for field in FIELDS}
        for row in old_rows
        if not (row["case"] in fixed_cases and row["variant"] == "zero_traffic")
    ]
    for payload in fixed_payloads:
        case = payload["case"]
        if case not in raw_cycles:
            raise KeyError(f"missing raw official baseline for {case}")
        if not payload["final"].get("valid", False):
            raise AssertionError(f"fixed-traffic evidence for {case} is not valid")
        if int(payload["final"].get("safe_overlap_errors", 1)) != 0:
            raise AssertionError(f"fixed-traffic evidence for {case} has safe overlap errors")
        candidates.append(_fixed_row(payload, raw_cycles[case]))

    kept: list[dict[str, str]] = []
    dominated: list[dict[str, str]] = []
    for case in sorted({row["case"] for row in candidates}):
        case_rows = [row for row in candidates if row["case"] == case]
        case_kept, case_dominated = _pareto(case_rows)
        kept.extend(case_kept)
        dominated.extend(case_dominated)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(kept)

    report = {
        "fixed_cases": sorted(fixed_cases),
        "kept": kept,
        "dominated_removed": dominated,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
