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

from parser import load_case
from q2_promoted import solve_q2_promoted
from q2_validator import validate_q2_solution
from q3_official_optimizer import optimize_q3_official_zero_traffic
from q3_paired_epoch_recolor import search_q3_paired_epoch_recolor


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--case", default="Conv_Case0")
    ap.add_argument("--recolor-rounds", type=int, default=24)
    ap.add_argument("--targets", type=int, default=6)
    ap.add_argument("--initial-starts", type=int, default=24)
    ap.add_argument("--spill-starts", type=int, default=8)
    args = ap.parse_args()

    graph = load_case(args.data_dir, args.case)
    promoted = solve_q2_promoted(graph)
    promoted.allocation.validation.require_ok()

    t0 = time.perf_counter()
    saturated = optimize_q3_official_zero_traffic(
        graph,
        promoted.allocation.solution,
        max_rounds=2,
        recolor_max_rounds=args.recolor_rounds,
        recolor_max_targets=6,
        recolor_max_starts=12,
    )
    t1 = time.perf_counter()
    paired = search_q3_paired_epoch_recolor(
        graph,
        saturated.solution,
        max_targets=args.targets,
        max_initial_starts=args.initial_starts,
        max_spill_starts=args.spill_starts,
        baseline_official=saturated.official_timing,
        baseline_safe=saturated.safe_timing,
    )
    t2 = time.perf_counter()

    q2 = validate_q2_solution(graph, paired.best_solution)
    q2.require_ok()
    move = paired.best_move
    payload = {
        "case": args.case,
        "saturated_official_cycles": saturated.official_timing.total_cycles,
        "paired_official_cycles": paired.best_official.total_cycles,
        "paired_improvement_cycles": saturated.official_timing.total_cycles - paired.best_official.total_cycles,
        "saturated_safe_cycles": saturated.safe_timing.total_cycles,
        "paired_safe_cycles": paired.best_safe.total_cycles,
        "improved": paired.improved,
        "target_buffers": paired.target_buffers,
        "paired_start_count": paired.paired_start_count,
        "competitive_start_count": paired.competitive_start_count,
        "strict_replay_count": paired.strict_replay_count,
        "spill_count": q2.spill_count,
        "extra_traffic": q2.extra_traffic,
        "safe_overlap_errors": len(paired.best_safe.physical_overlap_errors),
        "valid": paired.best_safe.ok and paired.best_official.ok,
        "saturation_seconds": round(t1 - t0, 6),
        "paired_search_seconds": round(t2 - t1, 6),
        "total_seconds": round(t2 - t0, 6),
        "best_move": None if move is None else {
            "target_buf": move.target_buf,
            "old_initial_offset": move.old_initial_offset,
            "new_initial_offset": move.new_initial_offset,
            "spill_index": move.spill_index,
            "spill_buf": move.spill_buf,
            "old_spill_offset": move.old_spill_offset,
            "new_spill_offset": move.new_spill_offset,
        },
        "trials": [
            {
                "target_buf": t.target_buf,
                "new_initial_offset": t.new_initial_offset,
                "blocker_spill_index": t.blocker_spill_index,
                "new_spill_offset": t.new_spill_offset,
                "fast_official_cycles": t.fast_official_cycles,
                "q2_valid": t.q2_valid,
                "safe_valid": t.safe_valid,
                "official_cycles": t.official_cycles,
                "safe_cycles": t.safe_cycles,
                "error": t.error,
            }
            for t in paired.trials
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "trials"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
