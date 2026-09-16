from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"
OUT = Path(__file__).resolve().parents[1] / "generated"
OUT.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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


def q1_peak_residency():
    rows = read_csv(RESULTS / "q1_baseline" / "q1_baseline_summary.csv")
    labels = [short_case(r["case"]) for r in rows]
    values = [int(r["peak_residency"]) for r in rows]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(labels, values)
    ax.set_ylabel("Peak residency")
    ax.set_title("Q1 peak L1+UB residency across Appendix-E cases")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    save(fig, "q1_peak_residency")


def q2_spill_and_traffic():
    rows = read_csv(RESULTS / "q2_optimized" / "q2_optimized_summary.csv")
    labels = [short_case(r["case"]) for r in rows]

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(labels, [int(r["spill_count"]) for r in rows])
    ax.set_ylabel("SPILL count")
    ax.set_title("Q2 promoted SPILL count")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    save(fig, "q2_spill_count")

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(labels, [int(r["extra_traffic"]) for r in rows])
    ax.set_ylabel("Extra traffic")
    ax.set_title("Q2 promoted extra DDR traffic")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    save(fig, "q2_extra_traffic")


def q3_improvement():
    rows = read_csv(
        RESULTS / "q3_formal_fixed_traffic" / "q3_formal_fixed_traffic_summary.csv"
    )
    labels = [short_case(r["case"]) for r in rows]
    raw = [int(r["raw_official_cycles"]) for r in rows]
    final = [int(r["final_official_cycles"]) for r in rows]
    pct = [100.0 * (a - b) / a for a, b in zip(raw, final)]

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(labels, pct)
    ax.set_ylabel("Official-cycle reduction (%)")
    ax.set_title("Q3 fixed-traffic improvement over promoted Q2")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    save(fig, "q3_official_improvement_pct")


def q3_pareto():
    rows = read_csv(RESULTS / "q3_pareto" / "q3_refined_official_frontier.csv")
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for case in sorted({r["case"] for r in rows}):
        pts = [r for r in rows if r["case"] == case]
        xs = [int(r["extra_traffic"]) for r in pts]
        ys = [int(r["official_cycles"]) for r in pts]
        ax.plot(xs, ys, marker="o", label=short_case(case))
    ax.set_xlabel("Extra traffic")
    ax.set_ylabel("Official cycles")
    ax.set_title("Q3 refined Traffic–Cycles frontier")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    save(fig, "q3_refined_pareto")


def main():
    q1_peak_residency()
    q2_spill_and_traffic()
    q3_improvement()
    q3_pareto()
    print(f"generated figures in {OUT}")


if __name__ == "__main__":
    main()
