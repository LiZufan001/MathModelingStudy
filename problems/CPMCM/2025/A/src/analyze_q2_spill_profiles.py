from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from parser import load_case
from q2_model import copy_in_backed_buffers, spill_traffic_cost

CASES = (
    "Matmul_Case0",
    "Matmul_Case1",
    "FlashAttention_Case0",
    "FlashAttention_Case1",
    "Conv_Case0",
    "Conv_Case1",
)


def _read_spill_buf_ids(path: Path) -> list[int]:
    result: list[int] = []
    for line_num, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        left, sep, _right = line.partition(":")
        if not sep:
            raise ValueError(f"{path}:{line_num}: expected BufId:value")
        try:
            buf_id = int(float(left))
        except ValueError as exc:
            raise ValueError(f"{path}:{line_num}: invalid BufId {left!r}") from exc
        result.append(buf_id)
    return result


def _profile(graph, case: str, source: str, buf_ids: list[int]) -> dict[str, object]:
    counts = Counter(buf_ids)
    copy_in = copy_in_backed_buffers(graph)
    per_record_traffic = {buf_id: spill_traffic_cost(graph, buf_id) for buf_id in counts}

    by_type: Counter[str] = Counter()
    by_size: Counter[int] = Counter()
    copy_in_records = 0
    copy_in_traffic = 0
    noncopy_records = 0
    noncopy_traffic = 0
    total_traffic = 0

    for buf_id, count in counts.items():
        alloc = graph.alloc_node_for_buffer(buf_id)
        if alloc is None or alloc.size is None or alloc.memory_type is None:
            raise ValueError(f"{case}/{source}: unknown spill buffer {buf_id}")
        traffic = per_record_traffic[buf_id] * count
        total_traffic += traffic
        by_type[alloc.memory_type] += count
        by_size[alloc.size] += count
        if buf_id in copy_in:
            copy_in_records += count
            copy_in_traffic += traffic
        else:
            noncopy_records += count
            noncopy_traffic += traffic

    repeated_buffers = sum(1 for count in counts.values() if count > 1)
    repeated_records = sum(count - 1 for count in counts.values() if count > 1)
    top = sorted(
        counts.items(),
        key=lambda item: (-item[1], -per_record_traffic[item[0]], item[0]),
    )[:12]
    top_desc: list[str] = []
    for buf_id, count in top:
        alloc = graph.alloc_node_for_buffer(buf_id)
        assert alloc is not None and alloc.size is not None and alloc.memory_type is not None
        top_desc.append(
            f"{buf_id}x{count}[{alloc.memory_type},size={alloc.size},"
            f"copyin={buf_id in copy_in},traffic={per_record_traffic[buf_id]}]"
        )

    return {
        "case": case,
        "source": source,
        "records": len(buf_ids),
        "unique_buffers": len(counts),
        "buffers_spilled_gt1": repeated_buffers,
        "repeated_records": repeated_records,
        "repeat_fraction": round(repeated_records / len(buf_ids), 6) if buf_ids else 0.0,
        "max_spills_one_buffer": max(counts.values(), default=0),
        "conditional_pair_traffic": total_traffic,
        "copy_in_records": copy_in_records,
        "copy_in_traffic": copy_in_traffic,
        "noncopy_records": noncopy_records,
        "noncopy_traffic": noncopy_traffic,
        "records_by_type": dict(sorted(by_type.items())),
        "records_by_size": dict(sorted(by_size.items())),
        "top_repeated_buffers": "; ".join(top_desc),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Profile repeated Q2 spill victims under official traffic rules")
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--baseline-dir", type=Path, required=True)
    ap.add_argument("--external-dir", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--case", choices=CASES, action="append", dest="cases")
    args = ap.parse_args()

    selected = tuple(args.cases) if args.cases else CASES
    rows: list[dict[str, object]] = []
    for case in selected:
        graph = load_case(args.data_dir, case)
        ours_path = args.baseline_dir / case / f"{case}_spill.txt"
        rows.append(_profile(graph, case, "strict_baseline", _read_spill_buf_ids(ours_path)))
        if args.external_dir is not None:
            external_path = args.external_dir / f"{case}_spill.txt"
            rows.append(_profile(graph, case, "archived_invalid_reference", _read_spill_buf_ids(external_path)))

    fields = [
        "case",
        "source",
        "records",
        "unique_buffers",
        "buffers_spilled_gt1",
        "repeated_records",
        "repeat_fraction",
        "max_spills_one_buffer",
        "conditional_pair_traffic",
        "copy_in_records",
        "copy_in_traffic",
        "noncopy_records",
        "noncopy_traffic",
        "records_by_type",
        "records_by_size",
        "top_repeated_buffers",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    args.out.with_suffix(".json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.out.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
