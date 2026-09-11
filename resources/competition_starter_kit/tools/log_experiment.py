"""记录真正影响研究路线的实验与判断。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--log", default="experiments/decisions.jsonl")
    p.add_argument("--question", required=True)
    p.add_argument("--observation", required=True)
    p.add_argument("--judgment", required=True)
    p.add_argument("--change", required=True, help="本次模型/数据/验证具体改了什么")
    p.add_argument("--result", required=True)
    p.add_argument("--interpretation", required=True)
    p.add_argument("--next-decision", required=True)
    p.add_argument("--status", choices=["keep", "reject", "investigate"], default="investigate")
    p.add_argument("--seed", type=int)
    p.add_argument("--artifact", default="")
    args = p.parse_args()

    record = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "question": args.question,
        "observation": args.observation,
        "judgment": args.judgment,
        "change": args.change,
        "result": args.result,
        "interpretation": args.interpretation,
        "next_decision": args.next_decision,
        "status": args.status,
        "seed": args.seed,
        "artifact": args.artifact,
        "git_commit": git_commit(),
    }

    path = Path(args.log)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
    print(path)


if __name__ == "__main__":
    main()
