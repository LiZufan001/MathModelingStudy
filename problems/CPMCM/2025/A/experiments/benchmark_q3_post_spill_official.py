from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from benchmark_q3_spill_switch_batch_snapshot import _load_solution, _serialize_solution
from parser import load_case
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution
from q3_official_optimizer import optimize_q3_official_zero_traffic


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--solution", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--solution-out", type=Path, required=True)
    ap.add_argument("--recolor-rounds", type=int, default=6)
    args = ap.parse_args()

    source_payload, source = _load_solution(args.solution)
    graph = load_case(args.data_dir, source_payload["case"])

    t0 = time.perf_counter()
    source_q2 = validate_q2_solution(graph, source)
    source_q2.require_ok()
    source_official = evaluate_q3_solution(graph, source, reuse_mode="official_literal")
    source_official.require_ok()
    source_safe = evaluate_q3_solution(graph, source, reuse_mode="residency_safe")
    source_safe.require_ok()
    if source_official.total_cycles != int(source_payload["official_cycles"]):
        raise AssertionError("post-spill source official timing drifted")
    if source_safe.total_cycles != int(source_payload["safe_cycles"]):
        raise AssertionError("post-spill source safe timing drifted")
    if source_q2.spill_count != int(source_payload["spill_count"]):
        raise AssertionError("post-spill source spill count drifted")
    if source_q2.extra_traffic != int(source_payload["extra_traffic"]):
        raise AssertionError("post-spill source extra traffic drifted")
    source_spills = tuple((spill.buf_id, spill.new_offset) for spill in source.spills)
    t1 = time.perf_counter()

    result = optimize_q3_official_zero_traffic(
        graph,
        source,
        max_rounds=2,
        recolor_max_rounds=args.recolor_rounds,
        recolor_max_targets=6,
        recolor_max_starts=12,
    )
    t2 = time.perf_counter()

    final_q2 = validate_q2_solution(graph, result.solution)
    final_q2.require_ok()
    final_spills = tuple((spill.buf_id, spill.new_offset) for spill in result.solution.spills)
    if final_spills != source_spills:
        raise AssertionError("post-spill official optimizer changed exact SPILL records")
    if final_q2.spill_count != source_q2.spill_count:
        raise AssertionError("post-spill official optimizer changed spill count")
    if final_q2.extra_traffic != source_q2.extra_traffic:
        raise AssertionError("post-spill official optimizer changed extra traffic")
    if result.official_timing.total_cycles > source_official.total_cycles:
        raise AssertionError("post-spill official optimizer regressed official cycles")

    snapshot = _serialize_solution(
        source_payload["case"],
        result.solution,
        result.official_timing,
        result.safe_timing,
        final_q2,
        {
            "route": "post_spill_official_probe",
            "source_official_cycles": source_official.total_cycles,
            "source_safe_cycles": source_safe.total_cycles,
            "recolor_rounds": args.recolor_rounds,
            "parent_provenance": source_payload.get("provenance"),
        },
    )
    args.solution_out.parent.mkdir(parents=True, exist_ok=True)
    args.solution_out.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    payload = {
        "case": source_payload["case"],
        "source_official_cycles": source_official.total_cycles,
        "source_safe_cycles": source_safe.total_cycles,
        "recolor_round_limit": args.recolor_rounds,
        "final_official_cycles": result.official_timing.total_cycles,
        "final_safe_cycles": result.safe_timing.total_cycles,
        "improvement_cycles": source_official.total_cycles - result.official_timing.total_cycles,
        "spill_count": final_q2.spill_count,
        "extra_traffic": final_q2.extra_traffic,
        "safe_overlap_errors": len(result.safe_timing.physical_overlap_errors),
        "valid": result.official_timing.ok and result.safe_timing.ok,
        "source_validation_seconds": round(t1 - t0, 6),
        "optimizer_seconds": round(t2 - t1, 6),
        "total_seconds": round(t2 - t0, 6),
        "steps": [
            {
                "round": step.round_index,
                "transformation": step.transformation,
                "detail": step.detail,
                "official_before": step.official_before,
                "official_after": step.official_after,
                "safe_before": step.safe_before,
                "safe_after": step.safe_after,
                "accepted": step.accepted,
                "error": step.error,
            }
            for step in result.steps
        ],
        "solution_snapshot_written": str(args.solution_out),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
