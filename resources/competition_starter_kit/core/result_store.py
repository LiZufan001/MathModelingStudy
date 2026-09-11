"""稳定实验结果的唯一落盘入口。仅使用 Python 标准库。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
from typing import Any


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return None


def build_result(
    *,
    question: str,
    method: str,
    metrics: dict[str, Any],
    params: dict[str, Any] | None = None,
    notes: str = "",
    artifacts: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not question.strip():
        raise ValueError("question must be non-empty")
    if not method.strip():
        raise ValueError("method must be non-empty")
    if not isinstance(metrics, dict) or not metrics:
        raise ValueError("metrics must be a non-empty dict")

    return {
        "schema_version": 1,
        "question": question,
        "method": method,
        "metrics": metrics,
        "params": params or {},
        "notes": notes,
        "artifacts": artifacts or {},
        "provenance": {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit(),
            "python": platform.python_version(),
        },
    }


def atomic_write_json(path: str | Path, obj: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path


def save_result(path: str | Path, **kwargs: Any) -> Path:
    return atomic_write_json(path, build_result(**kwargs))
