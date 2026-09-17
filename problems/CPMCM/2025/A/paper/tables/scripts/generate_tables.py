from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"
OUT = Path(__file__).resolve().parents[1] / "generated"
OUT.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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

    write_table(
        "case_scale.tex",
        ["Case", "Nodes", "Edges", "$|E|/|V|$"],
        [
            [
                esc(r["case"]),
                fint(r["nodes"]),
                fint(r["edges"]),
                f"{int(r['edges']) / int(r['nodes']):.3f}",
            ]
            for r in q1
        ],
        "lrrr",
    )

    q1_policy = read_csv(RESULTS / "q1_promoted" / "q1_policy_comparison.csv")
    write_table(
        "q1_policy_ablation.tex",
        ["Case", "Baseline", "Pressure", "Frontier", "Lookahead", "Best", "Winner"],
        [
            [
                esc(r["case"]),
                fint(r["baseline_peak"]),
                fint(r["pressure_peak"]),
                fint(r["frontier_peak"]),
                fint(r["lookahead_peak"]),
                fint(r["best_peak"]),
                esc(r["best_method"]),
            ]
            for r in q1_policy
        ],
        "lrrrrrl",
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

    q2_meta = read_json(RESULTS / "q2_optimized" / "q2_optimized_summary.json")
    write_table(
        "q2_stage_ablation.tex",
        ["Case", "Raw traffic", "Footprint", "Promoted", "Raw spills", "Promoted spills", "$w$"],
        [
            [
                esc(r["case"]),
                fint(r["raw_baseline_extra_traffic"]),
                fint(r["footprint_only_extra_traffic"]),
                fint(r["extra_traffic"]),
                fint(r["raw_baseline_spill_count"]),
                fint(r["spill_count"]),
                str(r["polish_window"]),
            ]
            for r in q2_meta["cases"]
        ],
        "lrrrrrr",
    )

    q3 = read_csv(
        RESULTS / "q3_formal_fixed_traffic" / "q3_formal_fixed_traffic_summary.csv"
    )
    write_table(
        "q3_summary.tex",
        ["Case", "Raw cycles", "Final cycles", r"Reduction (\%)", "Traffic"],
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

    write_table(
        "q3_dual_summary.tex",
        ["Case", "Official", "Safe", r"Safe gap (\%)", "SPILL", "Traffic"],
        [
            [
                esc(r["case"]),
                fint(r["final_official_cycles"]),
                fint(r["final_safe_cycles"]),
                fpct(100.0 * (int(r["final_safe_cycles"]) - int(r["final_official_cycles"])) / int(r["final_official_cycles"])),
                fint(r["spill_count"]),
                fint(r["extra_traffic"]),
            ]
            for r in q3
        ],
        "lrrrrr",
    )

    write_table(
        "q3_stage_details.tex",
        ["Case", "Raw", "Core", "Final", "Core gain", "Post gain", "Accepted rounds"],
        [
            [
                esc(r["case"]),
                fint(r["raw_official_cycles"]),
                fint(r["core_official_cycles"]),
                fint(r["final_official_cycles"]),
                fint(int(r["raw_official_cycles"]) - int(r["core_official_cycles"])),
                fint(int(r["core_official_cycles"]) - int(r["final_official_cycles"])),
                str(r["accepted_spill_batch_rounds"]),
            ]
            for r in q3
        ],
        "lrrrrrr",
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
            r"Q3 gain (\%)",
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
        ["Variant", r"Traffic increase (\%)", "Official cycles", r"Reduction (\%)"],
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
