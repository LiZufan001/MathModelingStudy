from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(SRC))

from parser import load_case
from probe_q3_single_switch_checkpoint import _read_solution, _write_solution
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_evaluator import evaluate_q3_solution


CASE = "Conv_Case1"
EXPECTED_OPERATOR = "fresh_rerank_cycle_filtered_critical_spill_batch"
REFERENCE_FORMAL_OFFICIAL = 3_767_326


def _spill_records(solution) -> tuple[tuple[int, int], ...]:
    return tuple((spill.buf_id, spill.new_offset) for spill in solution.spills)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Independently accept a saturated cycle-filtered Conv1 Problem3 artifact"
    )
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument(
        "--reference-official",
        type=int,
        default=REFERENCE_FORMAL_OFFICIAL,
        help="Current published Conv1 official-cycle ceiling that the candidate must beat",
    )
    args = ap.parse_args()

    summary_path = args.input_dir / "cycle-filtered-saturation.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"missing saturation summary: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    if summary.get("case") != CASE:
        raise AssertionError(f"unexpected case: {summary.get('case')!r}")
    if summary.get("operator") != EXPECTED_OPERATOR:
        raise AssertionError(f"unexpected operator: {summary.get('operator')!r}")
    if summary.get("saturated") is not True:
        raise AssertionError("candidate provenance is not saturated")
    if summary.get("stop_reason") != "no_improvement":
        raise AssertionError(f"unexpected saturation stop reason: {summary.get('stop_reason')!r}")
    if summary.get("valid") is not True:
        raise AssertionError("candidate provenance is not valid")
    if int(summary.get("safe_overlap_errors", -1)) != 0:
        raise AssertionError("candidate provenance reports residency-safe overlap errors")

    graph = load_case(args.data_dir, CASE)
    candidate_dir = args.input_dir / "Problem3"
    candidate = _read_solution(candidate_dir, CASE)

    # Rebuild the promoted Q2 solution from source, rather than trusting artifact metadata.
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()
    promoted_q2 = validate_q2_solution(graph, promoted.solution)
    promoted_q2.require_ok()

    candidate_q2 = validate_q2_solution(graph, candidate)
    candidate_q2.require_ok()
    candidate_official = evaluate_q3_solution(
        graph, candidate, reuse_mode="official_literal"
    )
    candidate_official.require_ok()
    candidate_safe = evaluate_q3_solution(
        graph, candidate, reuse_mode="residency_safe"
    )
    candidate_safe.require_ok()

    if candidate_official.total_cycles != int(summary["final_official_cycles"]):
        raise AssertionError("candidate official timing drifted from saturation summary")
    if candidate_safe.total_cycles != int(summary["final_safe_cycles"]):
        raise AssertionError("candidate safe timing drifted from saturation summary")
    if candidate_q2.spill_count != int(summary["spill_count"]):
        raise AssertionError("candidate spill count drifted from saturation summary")
    if candidate_q2.extra_traffic != int(summary["extra_traffic"]):
        raise AssertionError("candidate extra traffic drifted from saturation summary")
    if len(candidate_safe.physical_overlap_errors) != 0:
        raise AssertionError("candidate has residency-safe physical overlap errors")

    exact_spill_records_match = _spill_records(candidate) == _spill_records(promoted.solution)
    fixed_q2_metrics_match = (
        candidate_q2.spill_count == promoted_q2.spill_count
        and candidate_q2.extra_traffic == promoted_q2.extra_traffic
    )
    if not exact_spill_records_match:
        raise AssertionError("candidate changed exact promoted-Q2 SPILL records")
    if not fixed_q2_metrics_match:
        raise AssertionError("candidate changed promoted-Q2 spill count or extra traffic")
    if candidate_official.total_cycles >= args.reference_official:
        raise AssertionError(
            "candidate does not strictly improve the current formal Conv1 result: "
            f"{candidate_official.total_cycles} >= {args.reference_official}"
        )

    # Independently rerun one fresh-rerank neighborhood from the candidate.  Promotion
    # requires a real no-improvement round, not only a provenance flag produced by the
    # search workflow that generated the artifact.
    args.out_dir.mkdir(parents=True, exist_ok=True)
    recheck_dir = args.out_dir / "saturation-recheck"
    probe_script = EXP / "probe_q3_cycle_filtered_batch.py"
    max_switches = int(summary.get("max_switches", 16))
    command = [
        sys.executable,
        str(probe_script),
        "--data-dir",
        str(args.data_dir),
        "--case",
        CASE,
        "--input-dir",
        str(candidate_dir),
        "--out-dir",
        str(recheck_dir),
        "--expected-official",
        str(candidate_official.total_cycles),
        "--max-switches",
        str(max_switches),
    ]
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    (recheck_dir / "acceptance-stdout.txt").parent.mkdir(parents=True, exist_ok=True)
    (recheck_dir / "acceptance-stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (recheck_dir / "acceptance-stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            "independent saturation recheck failed with "
            f"{completed.returncode}: {completed.stderr[-2000:]}"
        )

    recheck_payload = json.loads(
        (recheck_dir / "cycle-filtered-batch.json").read_text(encoding="utf-8")
    )
    recheck_baseline = recheck_payload["baseline"]
    recheck_result = recheck_payload["result"]
    if int(recheck_baseline["official_cycles"]) != candidate_official.total_cycles:
        raise AssertionError("saturation recheck started from the wrong official timing")
    if int(recheck_baseline["spill_count"]) != candidate_q2.spill_count:
        raise AssertionError("saturation recheck started from the wrong spill count")
    if int(recheck_baseline["extra_traffic"]) != candidate_q2.extra_traffic:
        raise AssertionError("saturation recheck started from the wrong extra traffic")
    if recheck_result.get("improved") is not False:
        raise AssertionError(
            "candidate is not independently saturated in the cycle-filtered neighborhood"
        )
    if int(recheck_result["official_cycles"]) != candidate_official.total_cycles:
        raise AssertionError("no-improvement recheck changed official cycles")
    if recheck_result.get("valid") is not True:
        raise AssertionError("saturation recheck result is not valid")
    if int(recheck_result.get("safe_overlap_errors", -1)) != 0:
        raise AssertionError("saturation recheck reports residency-safe overlap errors")

    accepted_dir = args.out_dir / "Problem3"
    _write_solution(accepted_dir, CASE, candidate)
    output_paths = {
        "schedule": accepted_dir / f"{CASE}_schedule.txt",
        "memory": accepted_dir / f"{CASE}_memory.txt",
        "spill": accepted_dir / f"{CASE}_spill.txt",
    }

    evidence = {
        "case": CASE,
        "accepted": True,
        "route": "cycle_filtered_artifact->fresh_promoted_q2_rebuild->dual_evaluator->independent_no_improvement_recheck",
        "source_provenance": {
            "operator": summary["operator"],
            "saturated": summary["saturated"],
            "stop_reason": summary["stop_reason"],
            "round_count": summary["round_count"],
            "accepted_rounds": summary["accepted_rounds"],
            "max_switches": max_switches,
        },
        "promoted_q2": {
            "spill_count": promoted_q2.spill_count,
            "extra_traffic": promoted_q2.extra_traffic,
        },
        "candidate": {
            "official_cycles": candidate_official.total_cycles,
            "safe_cycles": candidate_safe.total_cycles,
            "reference_official_cycles": args.reference_official,
            "improvement_vs_reference_cycles": args.reference_official
            - candidate_official.total_cycles,
            "spill_count": candidate_q2.spill_count,
            "extra_traffic": candidate_q2.extra_traffic,
            "safe_overlap_errors": len(candidate_safe.physical_overlap_errors),
            "exact_spill_records_match": exact_spill_records_match,
            "fixed_q2_metrics_match": fixed_q2_metrics_match,
        },
        "independent_saturation_recheck": {
            "operator": recheck_payload["operator"],
            "improved": recheck_result["improved"],
            "official_cycles": recheck_result["official_cycles"],
            "safe_cycles": recheck_result["safe_cycles"],
            "valid": recheck_result["valid"],
            "safe_overlap_errors": recheck_result["safe_overlap_errors"],
        },
        "outputs": {
            name: {
                "path": str(path.relative_to(args.out_dir)),
                "sha256": _sha256(path),
            }
            for name, path in output_paths.items()
        },
    }
    evidence_path = args.out_dir / "q3-conv1-cycle-filtered-acceptance.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
