from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"
OUT = Path(__file__).resolve().parents[1] / "generated"
OUT.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(fig, stem: str):
    fig.tight_layout()
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def short_case(name: str) -> str:
    return (
        name.replace("FlashAttention", "FA")
        .replace("Matmul", "MM")
        .replace("Conv", "Conv")
        .replace("_Case", "-")
    )


def annotate_bars(ax, bars, values, fmt="{:.2f}"):
    for bar, value in zip(bars, values):
        ax.annotate(
            fmt.format(value),
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )


def q1_peak_residency():
    rows = read_csv(RESULTS / "q1_promoted" / "q1_promoted_summary.csv")
    labels = [short_case(r["case"]) for r in rows]
    values = [int(r["promoted_peak"]) for r in rows]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    bars = ax.bar(labels, values)
    ax.set_ylabel("Peak residency")
    ax.set_title("Q1 promoted peak L1+UB residency across Appendix-E cases")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    annotate_bars(ax, bars, values, fmt="{:,.0f}")
    save(fig, "q1_peak_residency")


def q1_policy_ablation():
    rows = read_csv(RESULTS / "q1_promoted" / "q1_policy_comparison.csv")
    labels = [short_case(r["case"]) for r in rows]
    strategies = [
        ("Baseline", "baseline_peak"),
        ("Pressure", "pressure_peak"),
        ("Frontier", "frontier_peak"),
        ("Lookahead", "lookahead_peak"),
    ]
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for label, key in strategies:
        ratios = [int(r[key]) / int(r["baseline_peak"]) for r in rows]
        ax.plot(labels, ratios, marker="o", label=label)
    ax.axhline(1.0, linewidth=1.0, linestyle="--")
    ax.set_ylabel("Peak residency / baseline")
    ax.set_title("Q1 policy ablation: no single heuristic dominates all cases")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    save(fig, "q1_policy_ablation")


def q2_spill_and_traffic():
    rows = read_csv(RESULTS / "q2_optimized" / "q2_optimized_summary.csv")
    labels = [short_case(r["case"]) for r in rows]

    spill = [int(r["spill_count"]) for r in rows]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    bars = ax.bar(labels, spill)
    ax.set_ylabel("SPILL count")
    ax.set_title("Q2 promoted SPILL count")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    annotate_bars(ax, bars, spill, fmt="{:,.0f}")
    save(fig, "q2_spill_count")

    traffic = [int(r["extra_traffic"]) for r in rows]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    bars = ax.bar(labels, traffic)
    ax.set_ylabel("Extra traffic")
    ax.set_title("Q2 promoted extra DDR traffic")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    annotate_bars(ax, bars, traffic, fmt="{:,.0f}")
    save(fig, "q2_extra_traffic")


def q2_stage_ablation():
    meta = read_json(RESULTS / "q2_optimized" / "q2_optimized_summary.json")
    rows = meta["cases"]
    labels = [short_case(r["case"]) for r in rows]
    raw = [float(r["raw_baseline_extra_traffic"]) for r in rows]
    footprint = [100.0 * (base - float(r["footprint_only_extra_traffic"])) / base for r, base in zip(rows, raw)]
    promoted = [100.0 * (base - float(r["extra_traffic"])) / base for r, base in zip(rows, raw)]

    x = list(range(len(labels)))
    width = 0.34
    fig, ax = plt.subplots(figsize=(8.0, 4.7))
    ax.bar([i - width / 2 for i in x], footprint, width, label="Footprint only")
    ax.bar([i + width / 2 for i in x], promoted, width, label="Promoted")
    ax.set_ylabel("Extra-traffic reduction vs raw baseline (%)")
    ax.set_title("Q2 stage ablation across Appendix-E cases")
    ax.set_xticks(x, labels, rotation=25)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    save(fig, "q2_stage_ablation")


def q3_improvement():
    rows = read_csv(
        RESULTS / "q3_formal_fixed_traffic" / "q3_formal_fixed_traffic_summary.csv"
    )
    labels = [short_case(r["case"]) for r in rows]
    raw = [int(r["raw_official_cycles"]) for r in rows]
    final = [int(r["final_official_cycles"]) for r in rows]
    pct = [100.0 * (a - b) / a for a, b in zip(raw, final)]

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    bars = ax.bar(labels, pct)
    ax.set_ylabel("Official-cycle reduction (%)")
    ax.set_title("Q3 fixed-traffic improvement over promoted Q2")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    annotate_bars(ax, bars, pct, fmt="{:.2f}%")
    save(fig, "q3_official_improvement_pct")


def q3_stage_contribution():
    rows = read_csv(
        RESULTS / "q3_formal_fixed_traffic" / "q3_formal_fixed_traffic_summary.csv"
    )
    labels = [short_case(r["case"]) for r in rows]
    raw = [int(r["raw_official_cycles"]) for r in rows]
    core = [int(r["core_official_cycles"]) for r in rows]
    final = [int(r["final_official_cycles"]) for r in rows]

    core_pct = [100.0 * (a - b) / a for a, b in zip(raw, core)]
    post_pct = [100.0 * (b - c) / a for a, b, c in zip(raw, core, final)]
    total_pct = [x + y for x, y in zip(core_pct, post_pct)]

    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    ax.bar(labels, core_pct, label="Formal zero-traffic core")
    ax.bar(labels, post_pct, bottom=core_pct, label="Critical-SPILL post-pass")
    ax.set_ylabel("Official-cycle reduction vs promoted Q2 (%)")
    ax.set_title("Q3 contribution by optimization stage (fixed traffic)")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    for i, total in enumerate(total_pct):
        ax.annotate(
            f"{total:.2f}%",
            xy=(i, total),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    save(fig, "q3_stage_contribution")


def q3_raw_vs_final():
    rows = read_csv(
        RESULTS / "q3_formal_fixed_traffic" / "q3_formal_fixed_traffic_summary.csv"
    )
    labels = [short_case(r["case"]) for r in rows]
    raw = [int(r["raw_official_cycles"]) for r in rows]
    final = [int(r["final_official_cycles"]) for r in rows]
    pct = [100.0 * (a - b) / a for a, b in zip(raw, final)]

    x = list(range(len(labels)))
    width = 0.36
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    raw_bars = ax.bar([i - width / 2 for i in x], raw, width, label="Promoted Q2")
    final_bars = ax.bar([i + width / 2 for i in x], final, width, label="Final Q3")
    ax.set_yscale("log")
    ax.set_ylabel("Official cycles (log scale)")
    ax.set_title("Q3 official cycles before and after fixed-traffic optimization")
    ax.set_xticks(x, labels, rotation=25)
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    for i, (a, b, p) in enumerate(zip(raw, final, pct)):
        ax.annotate(
            f"-{p:.2f}%",
            xy=(i, max(a, b)),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    _ = raw_bars, final_bars
    save(fig, "q3_raw_vs_final_cycles")


def q3_pareto_overview():
    rows = read_csv(RESULTS / "q3_pareto" / "q3_refined_official_frontier.csv")
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for case in sorted({r["case"] for r in rows}):
        pts = [r for r in rows if r["case"] == case]
        xs = [int(r["extra_traffic"]) for r in pts]
        ys = [int(r["official_cycles"]) for r in pts]
        ax.plot(xs, ys, marker="o", label=short_case(case))
    ax.set_xlabel("Extra traffic")
    ax.set_ylabel("Official cycles")
    ax.set_title("Q3 refined Traffic-Cycles frontier (diagnostic overview)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    save(fig, "q3_refined_pareto")


def q3_fa1_tradeoff():
    rows = read_csv(RESULTS / "q3_pareto" / "q3_refined_official_frontier.csv")
    pts = [r for r in rows if r["case"] == "FlashAttention_Case1"]
    pts.sort(key=lambda r: float(r["traffic_delta_pct"]))
    xs = [float(r["traffic_delta_pct"]) for r in pts]
    ys = [float(r["official_improvement_pct"]) for r in pts]

    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    ax.plot(xs, ys, marker="o")
    ax.set_xlabel("Extra traffic increase vs promoted Q2 (%)")
    ax.set_ylabel("Official-cycle reduction vs promoted Q2 (%)")
    ax.set_title("FA1 refined Traffic-Cycles trade-off")
    ax.grid(alpha=0.25)
    for r, x, y in zip(pts, xs, ys):
        label = "fixed traffic" if r["variant"] == "zero_traffic" else r["sequence"].replace(">", "->")
        ax.annotate(
            label,
            xy=(x, y),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=8,
        )
    save(fig, "q3_fa1_tradeoff")


def main():
    q1_peak_residency()
    q1_policy_ablation()
    q2_spill_and_traffic()
    q2_stage_ablation()
    q3_improvement()
    q3_stage_contribution()
    q3_raw_vs_final()
    q3_pareto_overview()
    q3_fa1_tradeoff()
    print(f"generated figures in {OUT}")


if __name__ == "__main__":
    main()
