#!/usr/bin/env python
"""Draw a large HAST framework concept figure with exact labels."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle, Wedge


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "artifacts" / "figures"

COL = {
    "green": "#6F947E",
    "green2": "#A8BFAE",
    "green3": "#DDE9DF",
    "teal": "#314F58",
    "edge": "#65756D",
    "gray": "#B8B8B8",
    "soft_gray": "#E6E6E6",
    "sand": "#D9C6A3",
    "orange": "#C9792F",
    "blue": "#476C7A",
    "text": "#111111",
    "red": "#8A5D55",
}


def arrow(ax, p0, p1, color="#7F8F83", lw=10, alpha=0.55, rad=0.0, z=2):
    ax.add_patch(
        FancyArrowPatch(
            p0,
            p1,
            arrowstyle="-|>",
            mutation_scale=18,
            linewidth=lw,
            color=color,
            alpha=alpha,
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=8,
            shrinkB=8,
            zorder=z,
        )
    )


def mini_graph(ax, x, y, r=0.28, node="#8BA79B", edge="#777", seed=0, faded=False):
    ax.add_patch(Circle((x, y), r, facecolor="#EEF4EF" if not faded else "#F4F4F4", edgecolor=COL["green"] if not faded else "#C8C8C8", lw=1.4, zorder=4))
    pts = [
        (x, y),
        (x - 0.12, y + 0.12),
        (x + 0.13, y + 0.10),
        (x - 0.15, y - 0.08),
        (x + 0.12, y - 0.13),
    ]
    edges = [(0, 1), (0, 2), (0, 3), (0, 4), (1, 2), (3, 4)]
    for a, b in edges:
        ax.plot([pts[a][0], pts[b][0]], [pts[a][1], pts[b][1]], color=edge, lw=1.0, alpha=0.7 if not faded else 0.35, zorder=5)
    sizes = [80, 38, 42, 36, 45]
    for i, (px, py) in enumerate(pts):
        ax.scatter([px], [py], s=sizes[i], c=node if not faded else "#D0D0D0", edgecolors=edge, linewidths=0.8, zorder=6)


def icon_two_hop(ax, x, y):
    ax.add_patch(Circle((x, y), 0.055, facecolor=COL["blue"], edgecolor="none", zorder=6))
    for ang in [30, 150, 270]:
        dx, dy = 0.22 * __import__("math").cos(__import__("math").radians(ang)), 0.22 * __import__("math").sin(__import__("math").radians(ang))
        ax.plot([x, x + dx], [y, y + dy], color="#8D9B95", lw=1.2, zorder=5)
        ax.add_patch(Circle((x + dx, y + dy), 0.045, facecolor="#98AFA3", edgecolor="#61756D", zorder=6))
        ax.plot([x + dx, x + dx * 1.45], [y + dy, y + dy * 1.45], color="#C0CBC5", lw=1.0, zorder=4)
        ax.add_patch(Circle((x + dx * 1.45, y + dy * 1.45), 0.035, facecolor="#D8E1DC", edgecolor="#9AA8A1", zorder=5))


def icon_residual(ax, x, y):
    mini_graph(ax, x, y, r=0.24)
    ax.scatter([x], [y], s=150, c="#73998B", edgecolors="#51675F", zorder=7)


def icon_frontier(ax, x, y):
    left = [(x - 0.25, y + 0.10), (x - 0.35, y - 0.08), (x - 0.12, y - 0.12)]
    right = [(x + 0.25, y + 0.10), (x + 0.35, y - 0.08), (x + 0.12, y - 0.12)]
    for pts in (left, right):
        for i in range(len(pts)):
            ax.plot([pts[i][0], pts[(i + 1) % len(pts)][0]], [pts[i][1], pts[(i + 1) % len(pts)][1]], color="#788C83", lw=1.1)
        for px, py in pts:
            ax.add_patch(Circle((px, py), 0.045, facecolor="#8EA99D", edgecolor="#65776F"))
    ax.plot([left[2][0], right[2][0]], [left[2][1], right[2][1]], color=COL["orange"], lw=2.0)


def icon_caps(ax, x, y):
    ax.add_patch(Rectangle((x - 0.28, y - 0.08), 0.56, 0.16, facecolor="#EEF3EF", edgecolor="#748A7F", lw=1.2))
    for i in range(7):
        xx = x - 0.24 + i * 0.08
        ax.plot([xx, xx], [y - 0.08, y + (0.05 if i % 2 == 0 else 0.02)], color="#748A7F", lw=0.9)
    ax.text(x, y - 0.28, "caps 64/128", ha="center", va="top", fontsize=8.5)


def icon_heap(ax, x, y):
    for i, w in enumerate([0.42, 0.32, 0.22]):
        ax.add_patch(Rectangle((x - w / 2, y - 0.15 + i * 0.12), w, 0.08, facecolor="#DDE9DF", edgecolor="#748A7F", lw=1.0))
    ax.add_patch(FancyArrowPatch((x + 0.22, y - 0.10), (x + 0.34, y + 0.14), arrowstyle="->", mutation_scale=10, color=COL["green"], lw=1.4))


def icon_no_rescan(ax, x, y):
    mini_graph(ax, x, y, r=0.22, node="#B7C5BF")
    ax.plot([x - 0.22, x + 0.22], [y - 0.22, y + 0.22], color="#7B5A4F", lw=3.0, zorder=8)


def label(ax, x, y, text, size=11, weight="normal", ha="center"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=size, fontweight=weight, color=COL["text"], zorder=20)


def main() -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.dpi": 300, "savefig.dpi": 300})
    fig, ax = plt.subplots(figsize=(16, 8.5))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    label(ax, 8.0, 8.18, "HAST: Three-Stage Heuristic Discovery for Network Dismantling", 18, "bold")
    label(ax, 2.5, 7.65, "Stage I: Free Tree Search", 16)
    label(ax, 8.8, 7.65, "Stage II: Evidence-Induced Candidate Boundaries", 16)
    label(ax, 12.5, 0.55, "Stage III: Bounded Tree Search and Selection", 16)

    # Stage I.
    mini_graph(ax, 0.9, 4.45, r=0.48)
    label(ax, 0.85, 3.55, "Root heuristic\n(degree, node size)", 11.5, "bold")
    centers = [(3.0, 5.7), (2.7, 4.55), (2.9, 3.25), (4.2, 5.0), (4.6, 3.8)]
    for idx, c in enumerate(centers):
        arrow(ax, (1.35, 4.45), c, color=COL["green"] if idx % 2 == 0 else COL["sand"], lw=9, alpha=0.55, rad=0.08 - idx * 0.03)
        mini_graph(ax, *c, r=0.34, faded=idx in {3})
    label(ax, 2.98, 6.35, "Candidate\nprogram h_t", 11)
    label(ax, 2.25, 4.18, "credit-aware\nexpansion", 10.5)
    label(ax, 1.8, 3.05, "low credit", 11)
    for x, y, t in [(4.95, 5.35, "high cost"), (5.05, 4.3, "unstable"), (4.7, 3.15, "failure")]:
        label(ax, x, y, t, 11, ha="left")
    for c in [(4.9, 6.35), (5.15, 5.65), (5.35, 3.05)]:
        mini_graph(ax, *c, r=0.26, faded=True)
        label(ax, c[0] + 0.42, c[1] + 0.24, "failure", 9, ha="left")

    # Log induction.
    arrow(ax, (5.1, 4.1), (6.55, 4.1), color=COL["sand"], lw=14, alpha=0.6, rad=-0.05)
    ax.add_patch(FancyBboxPatch((6.35, 3.55), 1.05, 0.85, boxstyle="round,pad=0.02", facecolor="#EEF0E8", edgecolor="#71817C", lw=1.4))
    label(ax, 6.87, 3.1, "Logging &\nlog induction", 12)
    ax.plot([6.52, 7.2], [3.85, 4.08], color=COL["green"], lw=2.0)
    ax.plot([6.52, 7.2], [3.75, 3.93], color=COL["green"], lw=2.0)

    # Stage II bounded candidate language banner.
    banner = Polygon(
        [(7.2, 6.05), (8.0, 7.25), (14.85, 7.25), (15.45, 6.2), (14.85, 5.2), (8.55, 5.2), (7.95, 4.55)],
        closed=True,
        facecolor="#EDF5EE",
        edgecolor=COL["green2"],
        lw=9,
        alpha=0.95,
        joinstyle="round",
    )
    ax.add_patch(banner)
    label(ax, 11.25, 6.95, "Log-Induced Bounded Candidate Language", 15, "bold")
    icon_xs = [8.55, 9.7, 10.85, 12.0, 13.15, 14.25]
    icons = [icon_two_hop, icon_residual, icon_frontier, icon_caps, icon_heap, icon_no_rescan]
    texts = ["two-hop\nboundary", "residual\ndegree", "frontier /\nweak tie", "", "lazy\nheap", "no global\nrescan"]
    for x, func, txt in zip(icon_xs, icons, texts):
        func(ax, x, 6.22)
        if txt:
            label(ax, x, 5.55, txt, 10)

    policy = FancyBboxPatch((8.35, 2.45), 3.15, 1.00, boxstyle="round,pad=0.04,rounding_size=0.08", facecolor="#F7FAF6", edgecolor=COL["green2"], lw=1.6)
    ax.add_patch(policy)
    label(ax, 9.92, 3.24, "Stage-II policy replay", 10.8, "bold")
    label(ax, 9.92, 2.94, "10/10 valid policy JSON; family: two-hop-boundary", 8.3)
    label(ax, 9.92, 2.68, "299/300 valid; mean runtime 0.026s; update radius <=2", 8.3)
    label(ax, 9.92, 2.12, "cost-aware credit + bounded locality caps", 10)

    arrow(ax, (7.35, 4.1), (10.35, 4.1), color=COL["green"], lw=16, alpha=0.62)

    # Stage III.
    search_nodes = [(10.7, 4.1), (12.2, 4.8), (12.25, 3.35), (13.45, 5.1), (13.55, 3.5)]
    for c in search_nodes:
        mini_graph(ax, *c, r=0.32)
    arrow(ax, (10.3, 4.1), search_nodes[0], color=COL["green"], lw=14, alpha=0.62)
    arrow(ax, search_nodes[0], search_nodes[1], color=COL["green"], lw=13, alpha=0.6, rad=0.12)
    arrow(ax, search_nodes[0], search_nodes[2], color=COL["green"], lw=13, alpha=0.6, rad=-0.12)
    arrow(ax, search_nodes[1], search_nodes[3], color=COL["green"], lw=12, alpha=0.62, rad=0.08)
    arrow(ax, search_nodes[2], search_nodes[4], color=COL["green"], lw=12, alpha=0.62, rad=-0.08)
    arrow(ax, search_nodes[1], (14.25, 4.25), color=COL["gray"], lw=8, alpha=0.55, rad=-0.1)
    label(ax, 13.85, 4.02, "prune\nlow-potential\nfamily", 11)
    ax.plot([14.4, 14.75], [4.0, 4.35], color="#7B5A4F", lw=4)
    ax.plot([14.75, 14.4], [4.0, 4.35], color="#7B5A4F", lw=4)

    # Final Q/S.
    for (x, y, txt, sub, color, glyph) in [
        (14.9, 3.75, "HAST-Final-Q", "(quality)\nquality-prioritized\nfinal candidate", COL["blue"], "*"),
        (14.9, 2.25, "HAST-Final-S", "(speed)\nspeed-prioritized\nfinal candidate", COL["orange"], "clock"),
    ]:
        ax.add_patch(Circle((x, y), 0.35, facecolor="#DDE9DF", edgecolor=COL["teal"], lw=2.0))
        if glyph == "*":
            ax.scatter([x], [y], marker="*", s=420, c="#FFF7D6", edgecolors=COL["teal"], linewidths=1.4, zorder=10)
        else:
            ax.add_patch(Circle((x, y), 0.18, facecolor="#FFF7D6", edgecolor=COL["teal"], lw=1.3, zorder=10))
            ax.plot([x, x], [y, y + 0.12], color=COL["teal"], lw=1.5, zorder=11)
            ax.plot([x, x + 0.1], [y, y - 0.06], color=COL["teal"], lw=1.5, zorder=11)
        label(ax, x + 0.58, y + 0.16, txt, 13, "bold", ha="left")
        label(ax, x + 0.58, y - 0.28, sub, 10, ha="left")
    arrow(ax, search_nodes[4], (14.58, 3.75), color=COL["green"], lw=12, alpha=0.62, rad=0.08)
    arrow(ax, search_nodes[4], (14.58, 2.25), color=COL["green"], lw=12, alpha=0.62, rad=-0.08)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / "HAST-Framework-big-local.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "HAST-Framework-big-local.pdf", bbox_inches="tight")
    print(OUT_DIR / "HAST-Framework-big-local.png")
    print(OUT_DIR / "HAST-Framework-big-local.pdf")


if __name__ == "__main__":
    main()
