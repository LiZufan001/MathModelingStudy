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

from model import ComputeGraph
from parser import load_case
from probe_q3_single_switch_checkpoint import _read_solution, _write_solution
from q2_validator import validate_q2_solution
from q3_critical_spill_switch import search_q3_critical_spill_switch_bubbles
from q3_evaluator import evaluate_q3_solution


def main() -> int:
    ap = argparse.ArgumentParser(description="Checkpointed single-switch saturation search")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--max-switches", type=int, default=4)
    ap.add_argument("--max-rounds", type=int, default=12)
    ap.add_argument("--expected-official", type=int)
    args = ap.parse_args()
    if args.max_switches <= 0 or args.max_rounds <= 0:
        raise ValueError("max-switches and max-rounds must be positive")

    graph: ComputeGraph = load_case(args.data_dir, args.case)
    current = _read_solution(args.input_dir, args.case)
    q2 = validate_q2_solution(graph, current)
    q2.require_ok()
    base_spills = current.spills
    base_traffic = q2.extra_traffic
    base_count = q2.spill_count
    official = evaluate_q3_solution(graph, current, reuse_mode="official_literal")
    official.require_ok()
    safe = evaluate_q3_solution(graph, current, reuse_mode="residency_safe")
    safe.require_ok()
    if args.expected_official is not None and official.total_cycles != args.expected_official:
        raise AssertionError(
            f"input official timing drifted: {official.total_cycles} != {args.expected_official}"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    initial_official = official.total_cycles
    history: list[dict[str, object]] = []
    saturated = False
    t0 = time.perf_counter()

    for round_no in range(1, args.max_rounds + 1):
        rt0 = time.perf_counter()
        result = search_q3_critical_spill_switch_bubbles(
            graph,
            current,
            max_switches=args.max_switches,
            baseline_official=official,
            baseline_safe=safe,
        )
        next_q2 = validate_q2_solution(graph, result.best_solution)
        next_q2.require_ok()
        if result.best_solution.spills != base_spills:
            raise AssertionError("single-switch saturation changed exact SPILL records")
        if next_q2.extra_traffic != base_traffic or next_q2.spill_count != base_count:
            raise AssertionError("single-switch saturation changed Q2 metrics")
        result.best_official.require_ok()
        result.best_safe.require_ok()

        round_dir = args.out_dir / f"round-{round_no:02d}"
        _write_solution(round_dir / "next", args.case, result.best_solution)
        record = {
            "round": round_no,
            "baseline_official_cycles": official.total_cycles,
            "baseline_safe_cycles": safe.total_cycles,
            "improved": result.improved,
            "best_move": None
            if result.best_move is None
            else {"spill_index": result.best_move[0], "mode": result.best_move[1]},
            "official_cycles": result.best_official.total_cycles,
            "safe_cycles": result.best_safe.total_cycles,
            "improvement_cycles": official.total_cycles - result.best_official.total_cycles,
            "candidate_count": len(result.candidates),
            "trial_count": len(result.trials),
            "seconds": round(time.perf_counter() - rt0, 6),
        }
        (round_dir / "round.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        history.append(record)

        current = result.best_solution
        official = result.best_official
        safe = result.best_safe
        if not result.improved:
            saturated = True
            break

    final_dir = args.out_dir / "Problem3"
    _write_solution(final_dir, args.case, current)
    payload = {
        "case": args.case,
        "operator": "checkpointed_critical_spill_single_switch_bubble",
        "max_switches": args.max_switches,
        "max_rounds": args.max_rounds,
        "initial_official_cycles": initial_official,
        "final_official_cycles": official.total_cycles,
        "final_safe_cycles": safe.total_cycles,
        "improvement_cycles": initial_official - official.total_cycles,
        "spill_count": base_count,
        "extra_traffic": base_traffic,
        "safe_overlap_errors": len(safe.physical_overlap_errors),
        "valid": official.ok and safe.ok,
        "saturated": saturated,
        "round_count": len(history),
        "accepted_rounds": sum(1 for r in history if r["improved"]),
        "rounds": history,
        "seconds": round(time.perf_counter() - t0, 6),
    }
    (args.out_dir / "single-switch-saturation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
