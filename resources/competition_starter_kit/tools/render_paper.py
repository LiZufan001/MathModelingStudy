"""用一个 JSON 结果源渲染论文数字。

占位符：
  {{metrics.rmse}}
  {{metrics.rmse:.4f}}
  {{question}}

缺 key 或无法格式化时直接失败。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

TOKEN = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)(?::([^{}]+))?\s*\}\}")


def lookup(obj: Any, dotted: str) -> Any:
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(f"missing result key: {dotted}")
    return cur


def render_text(template: str, data: dict[str, Any]) -> str:
    def repl(m: re.Match[str]) -> str:
        key, fmt = m.group(1), m.group(2)
        value = lookup(data, key)
        if fmt is None:
            return str(value)
        try:
            return format(value, fmt.strip())
        except Exception as e:
            raise ValueError(f"cannot format {key}={value!r} with {fmt!r}") from e

    rendered = TOKEN.sub(repl, template)
    unresolved = TOKEN.findall(rendered)
    if unresolved:
        raise ValueError(f"unresolved placeholders remain: {unresolved}")
    return rendered


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("result_json")
    p.add_argument("template")
    p.add_argument("output")
    args = p.parse_args()

    data = json.loads(Path(args.result_json).read_text(encoding="utf-8"))
    template = Path(args.template).read_text(encoding="utf-8")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_text(template, data), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
