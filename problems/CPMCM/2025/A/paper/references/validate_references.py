from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BIB = ROOT / "references.bib"
MAP = ROOT / "REFERENCE_MAP.md"

REQUIRED_KEYS = {
    "graham1969multiprocessing",
    "hu1961parallel",
    "kelley1961critical",
    "belady1966replacement",
    "sethi1975register",
    "chaitin1981coloring",
    "chow1990priority",
    "poletto1999linear",
    "wilson1995dynamic",
    "topcuoglu2002heft",
    "pisarchyk2020memory",
    "ehrgott2005multicriteria",
}

REQUIRED_DOI = {
    "graham1969multiprocessing": "10.1137/0117039",
    "hu1961parallel": "10.1287/opre.9.6.841",
    "kelley1961critical": "10.1287/opre.9.3.296",
    "belady1966replacement": "10.1147/SJ.52.0078",
    "sethi1975register": "10.1137/0204020",
    "chaitin1981coloring": "10.1016/0096-0551(81)90048-5",
    "chow1990priority": "10.1145/88616.88621",
    "poletto1999linear": "10.1145/330249.330250",
    "wilson1995dynamic": "10.1007/3-540-60368-9_19",
    "topcuoglu2002heft": "10.1109/71.993206",
    "ehrgott2005multicriteria": "10.1007/3-540-27659-9",
}


def extract_entries(text: str) -> dict[str, str]:
    starts = list(re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,", text))
    entries: dict[str, str] = {}
    for i, match in enumerate(starts):
        key = match.group(1)
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        if key in entries:
            raise SystemExit(f"duplicate BibTeX key: {key}")
        entries[key] = text[match.start():end]
    return entries


def main() -> int:
    bib_text = BIB.read_text(encoding="utf-8")
    map_text = MAP.read_text(encoding="utf-8")
    entries = extract_entries(bib_text)

    missing = sorted(REQUIRED_KEYS - entries.keys())
    if missing:
        raise SystemExit(f"missing required bibliography keys: {missing}")

    unexpected_placeholders = [
        token for token in ("TODO", "TBD", "example.com", "doi.org/XXX") if token in bib_text
    ]
    if unexpected_placeholders:
        raise SystemExit(f"bibliography contains placeholders: {unexpected_placeholders}")

    for key, doi in REQUIRED_DOI.items():
        entry = entries[key].lower()
        if doi.lower() not in entry:
            raise SystemExit(f"{key}: expected DOI {doi} not found")

    arxiv_entry = entries["pisarchyk2020memory"]
    if "2001.03288" not in arxiv_entry or "arXiv" not in arxiv_entry:
        raise SystemExit("pisarchyk2020memory: arXiv identifier metadata incomplete")

    for key in REQUIRED_KEYS:
        if f"`{key}`" not in map_text:
            raise SystemExit(f"REFERENCE_MAP.md does not document {key}")

    print(
        f"reference metadata OK: {len(entries)} BibTeX entries, "
        f"{len(REQUIRED_DOI)} DOI-locked entries, 1 arXiv entry"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
