from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "generated"
OUT.mkdir(parents=True, exist_ok=True)


def save(fig, stem: str):
    fig.tight_layout()
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def box(ax, xy, width, height, text, fontsize=10, linewidth=1.4):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.02",
        linewidth=linewidth,
        fill=False,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
    )
    return patch


def arrow(ax, start, end, text=None, rad=0.0, linestyle="-"):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=14,
        linewidth=1.3,
        linestyle=linestyle,
        connectionstyle=f"arc3,rad={rad}",
    )
    ax.add_patch(patch)
    if text:
        mx = (start[0] + end[0]) / 2
        my = (start[1] + end[1]) / 2
        ax.text(mx, my + 0.025, text, ha="center", va="bottom", fontsize=8)
    return patch


def pipeline_overview():
    fig, ax = plt.subplots(figsize=(8.2, 7.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    w, h = 0.62, 0.12
    x = 0.19
    ys = [0.82, 0.63, 0.44, 0.25, 0.06]
    texts = [
        "Appendix-E computation graph\nNodes + Edges + buffer metadata",
        "Q1  Topological scheduling\nminimize peak L1+UB residency",
        "Q2  Contiguous allocation + optional SPILL\nminimize extra DDR traffic",
        "Q3  Timing-aware reschedule / recolor\nminimize official cycles under fixed Q2 traffic/SPILL",
        "Independent validation and evaluation\nstrict replay + official evaluator + residency-safe gate",
    ]
    for y, text in zip(ys, texts):
        box(ax, (x, y), w, h, text)

    for y0, y1 in zip(ys[:-1], ys[1:]):
        arrow(
            ax,
            (x + w / 2, y0),
            (x + w / 2, y1 + h),
        )

    ax.text(
        0.05,
        0.50,
        "Optimization hierarchy",
        rotation=90,
        ha="center",
        va="center",
        fontsize=10,
    )
    ax.text(
        0.95,
        0.50,
        "Every promoted result\nmust pass real replay",
        rotation=90,
        ha="center",
        va="center",
        fontsize=9,
    )
    ax.set_title("Unified solution pipeline for CPMCM 2025 Problem A", fontsize=13)
    save(fig, "pipeline_overview")


def q2_buffer_lifecycle():
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    box(ax, (0.05, 0.60), 0.14, 0.13, "ALLOC\ncontiguous interval")
    box(ax, (0.27, 0.60), 0.20, 0.13, "RESIDENT / USE\nL1 address interval")
    box(ax, (0.78, 0.60), 0.14, 0.13, "FREE\nrelease interval")

    arrow(ax, (0.19, 0.665), (0.27, 0.665))
    arrow(ax, (0.47, 0.665), (0.78, 0.665), text="no spill", linestyle="--")

    box(ax, (0.30, 0.24), 0.14, 0.13, "SPILL\nchoose victim")
    box(ax, (0.52, 0.24), 0.14, 0.13, "DDR\nextra traffic")
    box(ax, (0.72, 0.24), 0.14, 0.13, "RELOAD\nrestore buffer")

    arrow(ax, (0.37, 0.60), (0.37, 0.37))
    ax.text(0.275, 0.485, "memory pressure", ha="center", va="center", fontsize=8)
    arrow(ax, (0.44, 0.305), (0.52, 0.305))
    arrow(ax, (0.66, 0.305), (0.72, 0.305))
    arrow(ax, (0.79, 0.37), (0.44, 0.60), text="next use", rad=0.22)

    ax.text(
        0.59,
        0.13,
        "Strict replay checks address intervals, SPILL order,\nresident state and total extra DDR traffic.",
        ha="center",
        va="center",
        fontsize=9,
    )
    ax.set_title("Q2 buffer lifecycle and SPILL mechanism", fontsize=13)
    save(fig, "q2_buffer_lifecycle")


def main():
    pipeline_overview()
    q2_buffer_lifecycle()
    print(f"generated diagrams in {OUT}")


if __name__ == "__main__":
    main()
