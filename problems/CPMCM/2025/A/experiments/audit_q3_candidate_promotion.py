from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from benchmark_q3_spill_switch_batch_snapshot import _load_solution
from parser import load_case
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution
from q3_official_optimizer import optimize_q3_official_zero_traffic


def _spill_records(solution) -> tuple[tuple[int, int], ...]:
    return tuple((spill.buf_id, spill.new_offset) for spill in solution.spills)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--official-rounds", type=int, default=2)
    args = ap.parse_args()

    candidate_payload, candidate = _load_solution(args.candidate)
    graph = load_case(args.data_dir, candidate_payload["case"])

    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()
    promoted_solution = promoted.solution
    promoted_q2 = validate_q2_solution(graph, promoted_solution)
    promoted_q2.require_ok()

    formal = optimize_q3_official_zero_traffic(
        graph,
        promoted_solution,
        max_rounds=args.official_rounds,
    )

    candidate_q2 = validate_q2_solution(graph, candidate)
    candidate_q2.require_ok()
    candidate_official = evaluate_q3_solution(graph, candidate, reuse_mode="official_literal")
    candidate_official.require_ok()
    candidate_safe = evaluate_q3_solution(graph, candidate, reuse_mode="residency_safe")
    candidate_safe.require_ok()

    if candidate_official.total_cycles != int(candidate_payload["official_cycles"]):
        raise AssertionError("candidate snapshot official timing drifted")
    if candidate_safe.total_cycles != int(candidate_payload["safe_cycles"]):
        raise AssertionError("candidate snapshot safe timing drifted")
    if candidate_q2.spill_count != int(candidate_payload["spill_count"]):
        raise AssertionError("candidate snapshot spill count drifted")
    if candidate_q2.extra_traffic != int(candidate_payload["extra_traffic"]):
        raise AssertionError("candidate snapshot extra traffic drifted")

    exact_spill_records_match = _spill_records(candidate) == _spill_records(promoted_solution)
    spill_buffer_order_match = tuple(spill.buf_id for spill in candidate.spills) == tuple(
        spill.buf_id for spill in promoted_solution.spills
    )
    fixed_q2_metrics_match = (
        candidate_q2.spill_count == promoted_q2.spill_count
        and candidate_q2.extra_traffic == promoted_q2.extra_traffic
    )

    promotion_ready = (
        exact_spill_records_match
        and fixed_q2_metrics_match
        and candidate_safe.ok
        and candidate_official.ok
        and candidate_official.total_cycles < formal.official_timing.total_cycles
    )

    payload = {
        "case": candidate_payload["case"],
        "promoted_q2_spill_count": promoted_q2.spill_count,
        "promoted_q2_extra_traffic": promoted_q2.extra_traffic,
        "formal_official_cycles": formal.official_timing.total_cycles,
        "formal_safe_cycles": formal.safe_timing.total_cycles,
        "candidate_official_cycles": candidate_official.total_cycles,
        "candidate_safe_cycles": candidate_safe.total_cycles,
        "candidate_spill_count": candidate_q2.spill_count,
        "candidate_extra_traffic": candidate_q2.extra_traffic,
        "official_improvement_vs_formal_cycles": (
            formal.official_timing.total_cycles - candidate_official.total_cycles
        ),
        "spill_buffer_order_match": spill_buffer_order_match,
        "exact_spill_records_match": exact_spill_records_match,
        "fixed_q2_metrics_match": fixed_q2_metrics_match,
        "safe_overlap_errors": len(candidate_safe.physical_overlap_errors),
        "promotion_ready": promotion_ready,
        "candidate_provenance": candidate_payload.get("provenance"),
    }

    if not exact_spill_records_match:
        raise AssertionError("candidate changed promoted-Q2 spill records")
    if not fixed_q2_metrics_match:
        raise AssertionError("candidate changed promoted-Q2 spill count or extra traffic")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
