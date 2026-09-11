from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from parser import load_case
from q1_scheduler import schedule_q1_baseline
from q2_allocator import allocate_q2_baseline
from q2_model import CACHE_CAPACITIES
from q2_reuse_scheduler import Q2ReuseScheduleConfig, schedule_q2_reuse_aware
from q2_unit_cache_oracle import solve_uniform_unit_cache_oracle

MATMUL_CASES = ("Matmul_Case0", "Matmul_Case1")
ALL_CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)

CONFIGS: tuple[tuple[str, Q2ReuseScheduleConfig], ...] = (
    (
        "direct_h16_r1",
        Q2ReuseScheduleConfig(
            hot_window=16,
            release_weight=1,
            probe_per_buffer=8,
            footprint_weight=0,
        ),
    ),
    (
        "footprint_m4",
        Q2ReuseScheduleConfig(
            hot_window=1,
            release_weight=0,
            probe_per_buffer=64,
            footprint_weight=1,
            footprint_min_buffers=4,
        ),
    ),
    (
        "footprint_m8",
        Q2ReuseScheduleConfig(
            hot_window=1,
            release_weight=0,
            probe_per_buffer=64,
            footprint_weight=1,
            footprint_min_buffers=8,
        ),
    ),
    (
        "footprint_hot_m4",
        Q2ReuseScheduleConfig(
            hot_window=16,
            release_weight=1,
            probe_per_buffer=64,
            footprint_weight=1,
            footprint_min_buffers=4,
        ),
    ),
)


def _read_baseline_summary(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return {row["case"]: row for row in csv.DictReader(fh)}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(path.read_text(encoding="utf-8"))


def _empty_experiment_row(case: str, name: str, config: Q2ReuseScheduleConfig, error: str) -> dict[str, object]:
    return {
        "case": case,
        "config": name,
        "hot_window": config.hot_window,
        "release_weight": config.release_weight,
        "footprint_weight": config.footprint_weight,
        "footprint_min_buffers": config.footprint_min_buffers,
        "affinity_decisions": None,
        "footprint_decisions": None,
        "q1_peak": None,
        "belady_spills": None,
        "belady_traffic": None,
        "strict_spills": None,
        "strict_traffic": None,
        "strict_matches_oracle": False,
        "schedule_seconds": None,
        "q2_seconds": None,
        "q2_valid": False,
        "error": error,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark experimental Q2-aware reuse scheduling")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--baseline-summary", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    baseline_summary = _read_baseline_summary(args.baseline_summary)
    grid_rows: list[dict[str, object]] = []
    aggregate: dict[str, dict[str, object]] = {
        name: {
            "traffic": 0,
            "peak": 0,
            "spills": 0,
            "footprint_decisions": 0,
            "valid_cases": 0,
            "failed": False,
        }
        for name, _ in CONFIGS
    }
    baseline_aggregate = {"traffic": 0, "peak": 0, "spills": 0}

    for case in MATMUL_CASES:
        graph = load_case(args.data_dir, case)
        baseline = schedule_q1_baseline(graph)
        baseline_oracle = solve_uniform_unit_cache_oracle(
            graph,
            baseline.order,
            memory_type="L1",
            capacity=CACHE_CAPACITIES["L1"],
        )
        summary = baseline_summary[case]
        strict_spills = int(summary["spill_count"])
        strict_traffic = int(summary["extra_traffic"])
        if (
            baseline_oracle.spill_count != strict_spills
            or baseline_oracle.extra_traffic != strict_traffic
        ):
            raise AssertionError(f"{case}: stored strict baseline no longer matches exact oracle")
        baseline_aggregate["traffic"] += baseline_oracle.extra_traffic
        baseline_aggregate["peak"] += baseline.evaluation.peak_residency or 0
        baseline_aggregate["spills"] += baseline_oracle.spill_count
        grid_rows.append(
            {
                "case": case,
                "config": "baseline",
                "hot_window": 0,
                "release_weight": 0,
                "footprint_weight": 0,
                "footprint_min_buffers": 0,
                "affinity_decisions": 0,
                "footprint_decisions": 0,
                "q1_peak": baseline.evaluation.peak_residency,
                "belady_spills": baseline_oracle.spill_count,
                "belady_traffic": baseline_oracle.extra_traffic,
                "strict_spills": strict_spills,
                "strict_traffic": strict_traffic,
                "strict_matches_oracle": True,
                "schedule_seconds": 0.0,
                "q2_seconds": float(summary["q2_seconds"]),
                "q2_valid": summary["valid"],
                "error": "",
            }
        )

        for name, config in CONFIGS:
            try:
                schedule_start = time.perf_counter()
                scheduled = schedule_q2_reuse_aware(graph, config)
                schedule_seconds = time.perf_counter() - schedule_start
                oracle = solve_uniform_unit_cache_oracle(
                    graph,
                    scheduled.order,
                    memory_type="L1",
                    capacity=CACHE_CAPACITIES["L1"],
                )
                q2_start = time.perf_counter()
                q2 = allocate_q2_baseline(graph, scheduled.order)
                q2_seconds = time.perf_counter() - q2_start
                q2.validation.require_ok()
                if (
                    q2.validation.spill_count != oracle.spill_count
                    or q2.validation.extra_traffic != oracle.extra_traffic
                ):
                    raise AssertionError(
                        f"strict allocator {q2.validation.spill_count}/{q2.validation.extra_traffic} "
                        f"!= oracle {oracle.spill_count}/{oracle.extra_traffic}"
                    )
            except Exception as exc:  # experiment failure is evidence, not a CI abort
                aggregate[name]["failed"] = True
                row = _empty_experiment_row(case, name, config, f"{type(exc).__name__}: {exc}")
                grid_rows.append(row)
                print(f"EXPERIMENT_REJECTED {case}/{name}: {row['error']}")
                continue

            aggregate[name]["traffic"] = int(aggregate[name]["traffic"]) + oracle.extra_traffic
            aggregate[name]["peak"] = int(aggregate[name]["peak"]) + (scheduled.evaluation.peak_residency or 0)
            aggregate[name]["spills"] = int(aggregate[name]["spills"]) + oracle.spill_count
            aggregate[name]["footprint_decisions"] = int(aggregate[name]["footprint_decisions"]) + scheduled.footprint_decisions
            aggregate[name]["valid_cases"] = int(aggregate[name]["valid_cases"]) + 1
            grid_rows.append(
                {
                    "case": case,
                    "config": name,
                    "hot_window": config.hot_window,
                    "release_weight": config.release_weight,
                    "footprint_weight": config.footprint_weight,
                    "footprint_min_buffers": config.footprint_min_buffers,
                    "affinity_decisions": scheduled.affinity_decisions,
                    "footprint_decisions": scheduled.footprint_decisions,
                    "q1_peak": scheduled.evaluation.peak_residency,
                    "belady_spills": oracle.spill_count,
                    "belady_traffic": oracle.extra_traffic,
                    "strict_spills": q2.validation.spill_count,
                    "strict_traffic": q2.validation.extra_traffic,
                    "strict_matches_oracle": True,
                    "schedule_seconds": round(schedule_seconds, 6),
                    "q2_seconds": round(q2_seconds, 6),
                    "q2_valid": q2.validation.ok,
                    "error": "",
                }
            )

    eligible = [
        (name, config)
        for name, config in CONFIGS
        if not bool(aggregate[name]["failed"])
        and int(aggregate[name]["valid_cases"]) == len(MATMUL_CASES)
    ]
    if not eligible:
        raise RuntimeError("all Q2-aware scheduler configurations were rejected")

    winner_name, winner_config = min(
        eligible,
        key=lambda item: (
            int(aggregate[item[0]]["traffic"]),
            int(aggregate[item[0]]["peak"]),
            -item[1].footprint_min_buffers,
            item[1].hot_window,
            item[1].release_weight,
            item[0],
        ),
    )
    selection = {
        "baseline_matmul": baseline_aggregate,
        "experiments": aggregate,
        "winner": winner_name,
        "winner_config": {
            "hot_window": winner_config.hot_window,
            "release_weight": winner_config.release_weight,
            "probe_per_buffer": winner_config.probe_per_buffer,
            "footprint_weight": winner_config.footprint_weight,
            "footprint_min_buffers": winner_config.footprint_min_buffers,
        },
        "winner_matmul": aggregate[winner_name],
        "matmul_traffic_delta": int(aggregate[winner_name]["traffic"]) - baseline_aggregate["traffic"],
        "matmul_spill_delta": int(aggregate[winner_name]["spills"]) - baseline_aggregate["spills"],
    }

    six_rows: list[dict[str, object]] = []
    for case in ALL_CASES:
        graph = load_case(args.data_dir, case)
        schedule_start = time.perf_counter()
        scheduled = schedule_q2_reuse_aware(graph, winner_config)
        schedule_seconds = time.perf_counter() - schedule_start
        q2_start = time.perf_counter()
        q2 = allocate_q2_baseline(graph, scheduled.order)
        q2_seconds = time.perf_counter() - q2_start
        q2.validation.require_ok()
        baseline = baseline_summary[case]
        baseline_traffic = int(baseline["extra_traffic"])
        baseline_spills = int(baseline["spill_count"])
        six_rows.append(
            {
                "case": case,
                "winner_config": winner_name,
                "q1_peak": scheduled.evaluation.peak_residency,
                "baseline_spills": baseline_spills,
                "reuse_spills": q2.validation.spill_count,
                "spill_delta": q2.validation.spill_count - baseline_spills,
                "baseline_traffic": baseline_traffic,
                "reuse_traffic": q2.validation.extra_traffic,
                "traffic_delta": q2.validation.extra_traffic - baseline_traffic,
                "traffic_ratio": round(q2.validation.extra_traffic / baseline_traffic, 6)
                if baseline_traffic
                else None,
                "affinity_decisions": scheduled.affinity_decisions,
                "footprint_decisions": scheduled.footprint_decisions,
                "schedule_seconds": round(schedule_seconds, 6),
                "q2_seconds": round(q2_seconds, 6),
                "q2_valid": q2.validation.ok,
            }
        )

    _write_csv(args.out_dir / "q2_reuse_grid.csv", grid_rows)
    _write_csv(args.out_dir / "q2_reuse_six_case.csv", six_rows)
    (args.out_dir / "q2_reuse_selection.json").write_text(
        json.dumps(selection, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(selection, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
