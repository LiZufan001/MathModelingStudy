from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"
OUT = Path(__file__).resolve().parents[1] / "generated"
OUT.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def esc(s: str) -> str:
    return s.replace("_", r"\_").replace("%", r"\%")


def write_table(name: str, headers: list[str], rows: list[list[str]], align: str):
    lines = [rf"\begin{{tabular}}{{{align}}}", r"\toprule"]
    lines.append(" & ".join(headers) + r" \\")
    lines.append(r"\midrule")
    for row in rows:
        lines.append(" & ".join(row) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (OUT / name).write_text("\n".join(lines), encoding="utf-8")


def main():
    q1 = read_csv(RESULTS / "q1_baseline" / "q1_baseline_summary.csv")
    write_table(
        "q1_summary.tex",
        ["Case", "Nodes", "Edges", "Peak residency"],
        [[esc(r["case"]), r["nodes"], r["edges"], r["peak_residency"]] for r in q1],
        "lrrr",
    )

    q2 = read_csv(RESULTS / "q2_optimized" / "q2_optimized_summary.csv")
    write_table(
        "q2_summary.tex",
        ["Case", "SPILL count", "Extra traffic", "Q1 peak"],
        [[esc(r["case"]), r["spill_count"], r["extra_traffic"], r["q1_peak"]] for r in q2],
        "lrrr",
    )

    q3 = read_csv(RESULTS / "q3_formal_fixed_traffic" / "q3_formal_fixed_traffic_summary.csv")
    write_table(
        "q3_summary.tex",
        ["Case", "Raw cycles", "Final cycles", "Reduction (\%)", "Traffic"],
        [
            [
                esc(r["case"]),
                r["raw_official_cycles"],
                r["final_official_cycles"],
                r["improvement_vs_raw_pct"],
                r["extra_traffic"],
            ]
            for r in q3
        ],
        "lrrrr",
    )
    print(f"generated tables in {OUT}")


if __name__ == "__main__":
    main()
