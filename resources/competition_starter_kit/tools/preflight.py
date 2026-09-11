"""冻结前检查。返回非 0 表示仍存在阻塞项。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PLACEHOLDERS = ("TODO", "TBD", "待填写", "待定")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config.json")
    args = p.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    config_path = Path(args.config)
    if not config_path.exists():
        errors.append(f"missing {config_path}; copy config.example.json to config.json")
        config = {}
    else:
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"invalid JSON in {config_path}: {e}")
            config = {}

    for key in ("contest", "year", "problem", "team", "results_dir", "experiment_log"):
        val = config.get(key)
        if val in (None, "") or (isinstance(val, str) and any(x in val for x in PLACEHOLDERS)):
            errors.append(f"config field not frozen: {key}={val!r}")

    evaluator = Path("core/evaluator.py")
    if not evaluator.exists():
        errors.append("missing core/evaluator.py")
    else:
        txt = evaluator.read_text(encoding="utf-8")
        if "NotImplementedError" in txt or "TODO:" in txt:
            errors.append("core/evaluator.py still contains TODO/NotImplementedError")

    if config:
        log_path = Path(config.get("experiment_log", "experiments/decisions.jsonl"))
        if not log_path.exists():
            warnings.append(f"no research decision log yet: {log_path}")

        results_dir = Path(config.get("results_dir", "results"))
        if not results_dir.exists():
            warnings.append(f"results directory does not exist yet: {results_dir}")
        else:
            finals = list(results_dir.glob("*final*.json"))
            if not finals:
                warnings.append("no *final*.json result found; do not freeze paper numbers yet")

    print("== PRE-FLIGHT ==")
    for w in warnings:
        print(f"[WARN] {w}")
    for e in errors:
        print(f"[FAIL] {e}")
    if errors:
        print(f"BLOCKED: {len(errors)} error(s), {len(warnings)} warning(s)")
        sys.exit(2)
    print(f"PASS: 0 errors, {len(warnings)} warning(s)")


if __name__ == "__main__":
    main()
