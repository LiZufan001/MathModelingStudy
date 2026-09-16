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
    return (
        s.replace("\\", r"\textbackslash{}")
        .replace("_", r"\_")
        .replace("%", r"\%")
        .replace(">", r"$>$")
    )


def fint(value: str | int) -> str:
    return f"{int(value):,}"


def fpct(value: str | float, digits: int = 3) -> str:
    return f"{float(value):.{digits}f}"


def write_table(name: str, headers: list[str], rows: list[list[str]], align: str):
    lines = [rf"\begin{{tabular}}{{{align}}}", r"\toprule"]
    lines.append(" & ".join(headers) + r" \\")
    lines.append(r"\midrule")
    for row in rows:
        lines.append(" & ".join(row) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (OUT / name).write_text("\n".join(lines), encoding="utf-8")


def main():
    q1 = read_csv(RESULTS / "q1_promoted" / "q1_promoted_summary.csv")
    write_table(
        "q1_summary.tex",
        ["Case", "Nodes", "Edges", "Baseline peak", "Promoted peak", "Method"],
        [
            [
                esc(r["case"]),
                fint(r["nodes"]),
                fint(r["edges"]),
                fint(r["baseline_peak"]),
                fint(r["promoted_peak"]),
                esc(r["promoted_method"]),
            ]
            for r in q1
        ],
        "lrrrrl",
    )

    q2 = read_csv(RESULTS / "q2_optimized" / "q2_optimized_summary.csv")
    write_table(
        "q2_summary.tex",
        ["Case", "SPILL count", "Extra traffic", "Q1 peak"],
        [
            [esc(r["case"]), fint(r["spill_count"]), fint(r["extra_traffic"]), fint(r["q1_peak"])]
            for r in q2
        ],
        "lrrr",
    )

    q3 = read_csv(
        RESULTS / "q3_formal_fixed_traffic" / "q3_formal_fixed_traffic_summary.csv"
    )
    write_table(
        "q3_summary.tex",
        ["Case", "Raw cycles", "Final cycles", "Reduction (\%)", "Traffic"],
        [
            [
                esc(r["case"]),
                fint(r["raw_official_cycles"]),
                fint(r["final_official_cycles"]),
                fpct(r["improvement_vs_raw_pct"]),
                fint(r["extra_traffic"]),
            ]
            for r in q3
        ],
        "lrrrr",
    )

    q1_by = {r["case"]: r for r in q1}
    q2_by = {r["case"]: r for r in q2}
    q3_by = {r["case"]: r for r in q3}
    cases = [r["case"] for r in q1]
    write_table(
        "key_results.tex",
        [
            "Case",
            "Nodes",
            "Q1 peak",
            "Q2 SPILL",
            "Q2 traffic",
            "Q3 cycles",
            "Q3 gain (\%)",
        ],
        [
            [
                esc(case),
                fint(q1_by[case]["nodes"]),
                fint(q1_by[case]["promoted_peak"]),
                fint(q2_by[case]["spill_count"]),
                fint(q2_by[case]["extra_traffic"]),
                fint(q3_by[case]["final_official_cycles"]),
                fpct(q3_by[case]["improvement_vs_raw_pct"]),
            ]
            for case in cases
        ],
        "lrrrrrr",
    )

    frontier = read_csv(RESULTS / "q3_pareto" / "q3_refined_official_frontier.csv")
    fa1 = [r for r in frontier if r["case"] == "FlashAttention_Case1"]
    fa1.sort(key=lambda r: float(r["traffic_delta_pct"]))
    write_table(
        "q3_fa1_tradeoff.tex",
        ["Variant", "Traffic increase (\%)", "Official cycles", "Reduction (\%)"],
        [
            [
                "fixed traffic" if r["variant"] == "zero_traffic" else esc(r["sequence"]),
                fpct(r["traffic_delta_pct"]),
                fint(r["official_cycles"]),
                fpct(r["official_improvement_pct"]),
            ]
            for r in fa1
        ],
        "lrrr",
    )

    print(f"generated tables in {OUT}")


if __name__ == "__main__":
    main()
