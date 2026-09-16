#!/usr/bin/env python3
"""Extract authoritative rule excerpts from the original 2025 A DOCX.

This is intentionally a provenance/debugging helper rather than part of the
optimizer.  It reads WordprocessingML directly so Office Math text and image
relationships around SPILL/Q2 paragraphs can be inspected in CI without
relying on secondary write-ups.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}

W_T = f"{{{NS['w']}}}t"
M_T = f"{{{NS['m']}}}t"
R_EMBED = f"{{{NS['r']}}}embed"


def _paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []
    for elem in paragraph.iter():
        if elem.tag in {W_T, M_T} and elem.text:
            parts.append(elem.text)
    return "".join(parts).strip()


def _paragraph_images(paragraph: ET.Element, rels: dict[str, str]) -> list[str]:
    images: list[str] = []
    for blip in paragraph.findall(".//a:blip", NS):
        rid = blip.attrib.get(R_EMBED)
        if rid and rid in rels:
            images.append(rels[rid])
    return images


def extract_records(docx: Path) -> list[dict[str, object]]:
    with zipfile.ZipFile(docx) as zf:
        document = ET.fromstring(zf.read("word/document.xml"))
        rels_root = ET.fromstring(zf.read("word/_rels/document.xml.rels"))
        rels = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_root.findall("pr:Relationship", NS)
            if rel.attrib.get("Id") and rel.attrib.get("Target")
        }

        records: list[dict[str, object]] = []
        for index, paragraph in enumerate(document.findall(".//w:p", NS)):
            text = _paragraph_text(paragraph)
            images = _paragraph_images(paragraph, rels)
            has_math = bool(
                paragraph.find(".//m:oMath", NS) is not None
                or paragraph.find(".//m:oMathPara", NS) is not None
            )
            if text or images or has_math:
                records.append(
                    {
                        "xml_paragraph_index": index,
                        "text": text,
                        "images": images,
                        "has_math": has_math,
                    }
                )
        return records


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", type=Path, required=True)
    ap.add_argument(
        "--keywords",
        nargs="*",
        default=[
            "SPILL",
            "问题2",
            "问题 2",
            "Cycles",
            "memory.txt",
            "spill.txt",
            "MTE2",
            "MTE3",
            "地址",
            "编号",
        ],
    )
    ap.add_argument("--window", type=int, default=4)
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()

    records = extract_records(args.docx)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(records, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    patterns = [re.compile(re.escape(keyword), re.IGNORECASE) for keyword in args.keywords]
    hits = [
        i
        for i, record in enumerate(records)
        if any(pattern.search(str(record["text"])) for pattern in patterns)
    ]

    selected: set[int] = set()
    for hit in hits:
        lo = max(0, hit - args.window)
        hi = min(len(records), hit + args.window + 1)
        selected.update(range(lo, hi))

    print(f"records={len(records)} keyword_hits={len(hits)} selected={len(selected)}")
    previous = None
    for i in sorted(selected):
        if previous is not None and i != previous + 1:
            print("---")
        record = records[i]
        print(
            f"[{i:04d}] xml={record['xml_paragraph_index']} "
            f"math={record['has_math']} images={record['images']}"
        )
        print(record["text"])
        previous = i
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
