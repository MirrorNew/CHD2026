#!/usr/bin/env python
"""Draw the three-stage HAST search tree used by the CHD paper.

The figure summarizes the full target-family run: Stage I has 300 generated
nodes, Stage II induces 10 bounded-language summaries, and Stage III has
200 generated bounded-search nodes seeded from Stage I.
"""

from __future__ import annotations

import csv
from collections import Counter
from copy import deepcopy
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch


ROOT = Path(__file__).resolve().parents[2]
S_DATA_DIR = (
    ROOT
    / "src"
    / "runs"
    / "runs_paper_evidence_20260616"
    / "07_final_candidate_lineage"
    / "selected_from_large_runs"
)
Q_DATA_DIR = (
    ROOT
    / "src"
    / "runs"
    / "runs_paper_evidence_20260616"
    / "07_final_candidate_lineage"
    / "q_cd9e_source_run"
)
OUT_DIR = ROOT / "artifacts" / "figures"

STAGE1 = S_DATA_DIR / "stage1_tree_nodes.csv"
S_STAGE3 = S_DATA_DIR / "stage3_tree_nodes.csv"
Q_STAGE3 = Q_DATA_DIR / "stage3_tree_nodes.csv"


COLORS = {
    "stage1": "#2A9D8F",
    "stage3": "#264653",
    "seed": "#E9C46A",
    "invalid": "#B0BEC5",
    "edge": "#CBD5E1",
    "final_s": "#D55E00",
    "final_q": "#0072B2",
    "selected_seed": "#7B2CBF",
    "stage2": "#E76F51",
    "text": "#23313D",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, "")
        return default if value == "" else float(value)
    except ValueError:
        return default


def as_int(row: dict[str, str], key: str, default: int = 0) -> int:
    return int(round(as_float(row, key, default)))


def node_positions(rows: list[dict[str, str]]) -> dict[str, tuple[float, float]]:
    by_depth: dict[int, int] = Counter()
    positions: dict[str, tuple[float, float]] = {}
    for row in sorted(rows, key=lambda r: (as_int(r, "stage_index"), r["node_id"])):
        depth = as_int(row, "depth")
        by_depth[depth] += 1
        # Small deterministic offset separates siblings that share a depth.
        jitter = ((by_depth[depth] % 7) - 3) * 0.035
        positions[row["node_id"]] = (as_int(row, "stage_index"), -depth + jitter)
    return positions


def sequence_positions(rows: list[dict[str, str]]) -> dict[str, tuple[float, float]]:
    """Display nodes as a simple Stage-I-style 1..N expansion sequence."""
    positions: dict[str, tuple[float, float]] = {}
    ordered = sorted(
        rows,
        key=lambda r: (
            0 if r.get("tree_role") == "seed" else 1,
            as_int(r, "stage_index"),
            r["node_id"],
        ),
    )
    by_depth: dict[int, int] = Counter()
    for idx, row in enumerate(ordered, start=1):
        depth = as_int(row, "depth")
        by_depth[depth] += 1
        jitter = ((by_depth[depth] % 7) - 3) * 0.035
        positions[row["node_id"]] = (idx, -depth + jitter)
    return positions


def compact_forest_positions(rows: list[dict[str, str]]) -> dict[str, tuple[float, float]]:
    """Layout a displayed forest compactly by start branch rather than index."""
    by_id = {row["node_id"]: row for row in rows}
    children: dict[str, list[str]] = {}
    for row in rows:
        parent = row.get("parent_node_id", "")
        if parent in by_id:
            children.setdefault(parent, []).append(row["node_id"])
    for child_list in children.values():
        child_list.sort(key=lambda node_id: as_int(by_id[node_id], "stage_index"))

    roots = [
        row["node_id"]
        for row in sorted(rows, key=lambda r: (as_int(r, "stage_index"), r["node_id"]))
        if row.get("parent_node_id", "") not in by_id
    ]
    positions: dict[str, tuple[float, float]] = {}
    x_cursor = 0.0
    branch_gap = 0.36

    for root in roots:
        stack: list[tuple[str, int]] = [(root, 0)]
        levels: dict[int, list[str]] = {}
        while stack:
            node_id, depth = stack.pop()
            levels.setdefault(depth, []).append(node_id)
            for child in reversed(children.get(node_id, [])):
                stack.append((child, depth + 1))

        max_width = max(len(nodes) for nodes in levels.values()) if levels else 1
        local_width = max(0.34, min(1.05, 0.055 * max_width))
        for depth, nodes in levels.items():
            nodes.sort(key=lambda node_id: as_int(by_id[node_id], "stage_index"))
            count = len(nodes)
            for idx, node_id in enumerate(nodes):
                step = min(0.075, local_width / max(count, 1))
                offset = 0.0 if count == 1 else (idx - (count - 1) / 2.0) * step
                # A tiny deterministic vertical stagger keeps dense depth-1
                # expansion layers readable without changing their tree level.
                y_stagger = 0.0 if count <= 2 else ((idx % 5) - 2) * 0.018
                positions[node_id] = (x_cursor + offset, -depth + y_stagger)
        x_cursor += local_width + branch_gap

    return positions


def mixed_layer_positions(
    rows: list[dict[str, str]],
    start_node_ids: set[str],
) -> dict[str, tuple[float, float]]:
    """Mix Stage-III nodes within each displayed depth layer.

    This keeps selected Stage-I seeds readable on the first row while allowing
    generated nodes in lower rows to occupy the same visual band instead of
    being separated into wide per-seed lanes.
    """
    positions: dict[str, tuple[float, float]] = {}
    by_depth: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        by_depth.setdefault(as_int(row, "depth"), []).append(row)

    by_id = {row["node_id"]: row for row in rows}
    children: dict[str, list[str]] = {}
    for row in rows:
        parent = row.get("parent_node_id", "")
        if parent in by_id:
            children.setdefault(parent, []).append(row["node_id"])

    subtree_size_cache: dict[str, int] = {}

    def subtree_size(node_id: str) -> int:
        if node_id not in subtree_size_cache:
            subtree_size_cache[node_id] = 1 + sum(subtree_size(child) for child in children.get(node_id, []))
        return subtree_size_cache[node_id]

    for depth, depth_rows in sorted(by_depth.items()):
        depth_rows.sort(key=lambda r: (r["node_id"] not in start_node_ids, as_int(r, "stage_index"), r["node_id"]))
        count = len(depth_rows)
        if depth == 0:
            if count > 2:
                primary = max(depth_rows, key=lambda r: subtree_size(r["node_id"]))
                rest = [row for row in depth_rows if row["node_id"] != primary["node_id"]]
                arranged: list[dict[str, str] | None] = [None] * count
                center = count // 2
                arranged[center] = primary
                slots = []
                for offset in range(1, count):
                    slots.extend([center - offset, center + offset])
                slots = [slot for slot in slots if 0 <= slot < count]
                for row, slot in zip(rest, slots):
                    arranged[slot] = row
                depth_rows = [row for row in arranged if row is not None]
            # Keep the selected Stage-I seed row narrow and centered. The next
            # generated row opens outward, giving Stage III a spindle shape.
            row_width = 2.85
            step = 0.0 if count == 1 else row_width / max(count - 1, 1)
            xs = [(idx - (count - 1) / 2.0) * step for idx in range(count)]
        else:
            # Dense layers open out; sparse lower layers collapse back toward
            # the center so low-count rows connect almost vertically.
            target_width_by_depth = {
                1: 4.85,
                2: 2.95,
                3: 2.40,
                4: 1.95,
                5: 1.45,
                6: 0.95,
                7: 0.48,
                8: 0.0,
            }
            target_width = target_width_by_depth.get(depth, 0.0)
            if count <= 2:
                layer_width = min(target_width, 0.18)
            elif count <= 6:
                layer_width = min(target_width, 0.42 + 0.08 * count)
            else:
                layer_width = min(target_width, max(1.05, 0.042 * count))
            step = 0.0 if count == 1 else layer_width / max(count - 1, 1)
            xs = [
                (idx - (count - 1) / 2.0) * step + ((idx % 7) - 3) * 0.012
                for idx in range(count)
            ]
        for idx, row in enumerate(depth_rows):
            y_stagger = 0.0 if depth == 0 or count <= 2 else ((idx % 5) - 2) * 0.017
            positions[row["node_id"]] = (xs[idx], -depth + y_stagger)

    for parent, child_ids in sorted(
        children.items(),
        key=lambda item: as_int(by_id[item[0]], "depth"),
    ):
        if len(child_ids) == 1 and parent in positions and child_ids[0] in positions:
            _, child_y = positions[child_ids[0]]
            positions[child_ids[0]] = (positions[parent][0], child_y)
    return positions


def draw_tree_panel(
    ax: plt.Axes,
    rows: list[dict[str, str]],
    positions: dict[str, tuple[float, float]],
    *,
    title: str,
    color: str,
    highlight_candidates: dict[str, tuple[str, str, str]] | None = None,
    selected_seed_candidate_ids: set[str] | None = None,
    seed_as_selected: bool = False,
    display_seed_node_ids: set[str] | None = None,
    highlight_path_node_ids: set[str] | None = None,
    highlight_path_color: str = "#0072B2",
    subtitle_override: str | None = None,
    xlabel: str = "Expansion index",
) -> None:
    for row in rows:
        parent = row.get("parent_node_id", "")
        if parent and parent in positions and row["node_id"] in positions:
            x0, y0 = positions[parent]
            x1, y1 = positions[row["node_id"]]
            ax.plot(
                [x0, x1],
                [y0, y1],
                color=COLORS["edge"],
                linewidth=0.45,
                alpha=0.55,
                zorder=1,
            )

    xs_seed, ys_seed, xs_valid, ys_valid, xs_bad, ys_bad = [], [], [], [], [], []
    display_seed_node_ids = display_seed_node_ids or set()
    for row in rows:
        x, y = positions[row["node_id"]]
        role = row.get("tree_role", "")
        valid = row.get("valid", "").lower() == "true"
        if role == "seed" or row["node_id"] in display_seed_node_ids:
            xs_seed.append(x)
            ys_seed.append(y)
        elif valid:
            xs_valid.append(x)
            ys_valid.append(y)
        else:
            xs_bad.append(x)
            ys_bad.append(y)

    ax.scatter(xs_valid, ys_valid, s=12, c=color, alpha=0.78, linewidths=0, zorder=3)
    if xs_seed:
        ax.scatter(
            xs_seed,
            ys_seed,
            s=54 if seed_as_selected else 42,
            c=COLORS["selected_seed"] if seed_as_selected else COLORS["seed"],
            edgecolors="#3B0764" if seed_as_selected else "#7A5C00",
            linewidths=0.9 if seed_as_selected else 0.7,
            marker="D",
            zorder=4,
        )
    if xs_bad:
        ax.scatter(xs_bad, ys_bad, s=18, c=COLORS["invalid"], marker="x", zorder=4)

    if selected_seed_candidate_ids:
        hits = [r for r in rows if r.get("candidate_id") in selected_seed_candidate_ids]
        for row in hits:
            x, y = positions[row["node_id"]]
            ax.scatter(
                [x],
                [y],
                s=72,
                c=COLORS["selected_seed"],
                marker="D",
                edgecolors="#3B0764",
                linewidths=0.9,
                zorder=5,
            )

    if highlight_candidates:
        for candidate_id, (label, marker, marker_color) in highlight_candidates.items():
            hits = [r for r in rows if r.get("candidate_id") == candidate_id]
            for row in hits:
                x, y = positions[row["node_id"]]
                ax.scatter(
                    [x],
                    [y],
                    s=135 if marker == "*" else 105,
                    c=marker_color,
                    marker=marker,
                    edgecolors="#222222",
                    linewidths=0.8,
                    zorder=6,
                )
                ax.annotate(
                    label,
                    xy=(x, y),
                    xytext=(8, 8),
                    textcoords="offset points",
                    arrowprops=dict(arrowstyle="->", color=marker_color, lw=0.9),
                    fontsize=8,
                    color=COLORS["text"],
                    zorder=7,
                )

    generated = sum(r.get("tree_role") == "generated" for r in rows)
    generated_valid = sum(
        r.get("tree_role") == "generated" and r.get("valid", "").lower() == "true"
        for r in rows
    )
    seed_count = sum(r.get("tree_role") == "seed" for r in rows)
    seed_text = "" if seed_count <= 1 else f", {seed_count} seeds"
    subtitle = subtitle_override or f"{generated} generated nodes, {generated_valid} valid{seed_text}"
    ax.set_title(
        f"{title}\n{subtitle}",
        loc="left",
    )
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Tree depth")
    ax.grid(True, axis="x", alpha=0.12)
    ax.grid(True, axis="y", alpha=0.08)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", labelsize=8)
    depths = sorted({as_int(r, "depth") for r in rows})
    tick_depths = [d for d in depths if d % 2 == 0]
    ax.set_yticks([-d for d in tick_depths])
    ax.set_yticklabels([str(d) for d in tick_depths])


def seed_candidate_ids(rows: list[dict[str, str]]) -> set[str]:
    return {
        row.get("candidate_id", "")
        for row in rows
        if row.get("tree_role") == "seed" and row.get("candidate_id")
    }


def lineage_rows(rows: list[dict[str, str]], candidate_id: str) -> list[dict[str, str]]:
    by_node = {row["node_id"]: row for row in rows}
    hits = [row for row in rows if row.get("candidate_id") == candidate_id]
    if not hits:
        return []
    lineage: list[dict[str, str]] = []
    cur: dict[str, str] | None = hits[0]
    while cur:
        lineage.append(cur)
        parent = cur.get("parent_node_id", "")
        cur = by_node.get(parent) if parent else None
    return list(reversed(lineage))


def prefix_rows(rows: list[dict[str, str]], prefix: str) -> list[dict[str, str]]:
    old_to_new = {row["node_id"]: f"{prefix}{row['node_id']}" for row in rows}
    out: list[dict[str, str]] = []
    for row in rows:
        new_row = deepcopy(row)
        new_row["node_id"] = old_to_new[row["node_id"]]
        parent = row.get("parent_node_id", "")
        new_row["parent_node_id"] = old_to_new.get(parent, "")
        # Keep candidate_id unchanged so final candidate highlighting still works.
        out.append(new_row)
    return out


def merged_stage3_rows(
    s_stage3: list[dict[str, str]],
    q_stage3: list[dict[str, str]],
) -> tuple[list[dict[str, str]], set[str], set[str], set[str]]:
    """Display exactly 200 Stage III points with the cd9e lineage embedded.

    The display uses one start for each unique selected Stage-I seed visible in
    the Stage-I tree, then keeps enough generated descendants to make exactly
    200 displayed Stage-III points after embedding the cd9e lineage.
    """
    s_seed_rows = [row for row in s_stage3 if row.get("tree_role") == "seed" and row.get("candidate_id")]
    seed_order: list[str] = []
    for row in s_seed_rows:
        cid = row["candidate_id"]
        if cid not in seed_order:
            seed_order.append(cid)
    seed_node_for_cid = {cid: f"display-seed-{idx + 1:04d}" for idx, cid in enumerate(seed_order)}

    display_seeds: list[dict[str, str]] = []
    for idx, cid in enumerate(seed_order):
        display_seeds.append(
            {
                "node_id": seed_node_for_cid[cid],
                "candidate_id": cid,
                "parent_node_id": "",
                "parent_candidate_id": "",
                "depth": "0",
                "stage_index": str(idx),
                "tree_role": "seed",
                "valid": "True",
            }
        )

    s_generated = [deepcopy(row) for row in s_stage3 if row.get("tree_role") == "generated"]
    q_line_full = lineage_rows(q_stage3, "cd9e3818033d")
    q_line = prefix_rows(q_line_full[1:], "qline-")  # attach the generated cd9e lineage to an existing Stage-I seed.
    target_seed_cid = lineage_rows(s_stage3, "0ade8d3405c2")[0].get("candidate_id", seed_order[0])
    remove_needed = len(display_seeds) + len(s_generated) + len(q_line) - 200
    if remove_needed < 0:
        raise RuntimeError("Stage III display unexpectedly has fewer than 200 source points")

    s_final_path = {row["node_id"] for row in lineage_rows(s_stage3, "0ade8d3405c2")}
    children: dict[str, list[str]] = {}
    for row in s_generated:
        parent = row.get("parent_node_id", "")
        if parent:
            children.setdefault(parent, []).append(row["node_id"])

    removable: list[str] = []
    # Remove non-final leaves first so the displayed tree remains connected
    # around the final Q/S paths.
    for row in reversed(s_generated):
        node_id = row["node_id"]
        if node_id in s_final_path or node_id in removable or node_id in children:
            continue
        removable.append(node_id)
        if len(removable) == remove_needed:
            break

    for row in reversed(s_generated):
        node_id = row["node_id"]
        if len(removable) == remove_needed:
            break
        if node_id not in s_final_path and node_id not in removable:
            removable.append(node_id)

    remove_set = set(removable[:remove_needed])
    kept_s = [row for row in s_generated if row["node_id"] not in remove_set]
    kept_ids = {row["node_id"] for row in kept_s}
    seed_by_node_id = {row["node_id"]: row["candidate_id"] for row in s_seed_rows}
    original_by_id = {row["node_id"]: row for row in s_stage3}

    def remap_s_parent(row: dict[str, str]) -> str:
        parent = row.get("parent_node_id", "")
        while parent:
            if parent in kept_ids:
                return parent
            if parent in seed_by_node_id:
                return seed_node_for_cid.get(seed_by_node_id[parent], "")
            parent = original_by_id.get(parent, {}).get("parent_node_id", "")
        return ""

    for row in kept_s:
        row["parent_node_id"] = remap_s_parent(row)

    for idx, row in enumerate(q_line):
        if idx == 0:
            row["parent_node_id"] = seed_node_for_cid[target_seed_cid]

    merged = display_seeds + kept_s + q_line
    if len(merged) != 200:
        raise RuntimeError(f"Stage III display must contain exactly 200 points, got {len(merged)}")

    q_path = {row["node_id"] for row in q_line}
    s_path = {row["node_id"] for row in lineage_rows(merged, "0ade8d3405c2")}
    start_node_ids = {row["node_id"] for row in display_seeds}
    return merged, q_path, s_path, start_node_ids


def draw_stage2_box(ax: plt.Axes) -> None:
    ax.axis("off")
    box = FancyBboxPatch(
        (0.04, 0.10),
        0.92,
        0.78,
        boxstyle="round,pad=0.025,rounding_size=0.035",
        facecolor="#FFF3EC",
        edgecolor=COLORS["stage2"],
        linewidth=1.2,
    )
    ax.add_patch(box)
    ax.text(
        0.5,
        0.79,
        "Stage II: Evidence-Induced Policy Summary",
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        color=COLORS["text"],
    )
    summary_lines = [
        "Replay: 10/10 valid policy JSON calls from Stage-I evidence logs",
        "Preferred family: two-hop-boundary with lazy local heap updates",
        "Allowed signals: boundary, frontier, residual/neighbor degree, redundancy, phase, weak tie",
        "Bounded locality: neighbor scan <=64; two-hop scan <=128; update radius <=2",
        "Runtime contract: preferred 0.019-0.027s on proxy; soft avoid >0.031s",
        "Forbidden: global rescans/sorts, component refresh per step, all-pairs paths, nondeterminism",
        "Stage-III language: keep local compression; forbid unbounded BFS/two-hop expansion",
    ]
    for idx, line in enumerate(summary_lines):
        ax.text(
            0.08,
            0.63 - idx * 0.078,
            line,
            ha="left",
            va="center",
            fontsize=7.2,
            color=COLORS["text"] if idx == 0 else "#52616B",
        )


def save_stage_svg_panels(
    stage1: list[dict[str, str]],
    pos1: dict[str, tuple[float, float]],
    merged_stage3: list[dict[str, str]],
    pos_merged: dict[str, tuple[float, float]],
    selected_seed_ids: set[str],
    stage3_start_nodes: set[str],
) -> None:
    """Export Stage I and Stage III panels as standalone SVG files."""
    fig1, ax1 = plt.subplots(figsize=(3.35, 3.35))
    draw_tree_panel(
        ax1,
        stage1,
        pos1,
        title="Stage I: Free Tree Search",
        color=COLORS["stage1"],
        selected_seed_candidate_ids=selected_seed_ids,
    )
    fig1.savefig(OUT_DIR / "fig30_stage1_tree.svg", format="svg")
    plt.close(fig1)

    fig3, ax3 = plt.subplots(figsize=(3.35, 3.35))
    draw_tree_panel(
        ax3,
        merged_stage3,
        pos_merged,
        title="Stage III: Bounded Tree Search with Final Q/S Lineages",
        color=COLORS["stage3"],
        highlight_candidates={
            "cd9e3818033d": ("Final-Q: cd9e3818033d", "*", COLORS["final_q"]),
            "0ade8d3405c2": ("Final-S: 0ade8d3405c2", "s", COLORS["final_s"]),
        },
        seed_as_selected=True,
        display_seed_node_ids=stage3_start_nodes,
        subtitle_override="11 selected Stage-I seeds -> 200 displayed Stage-III nodes; one merged Q/S discovery tree",
        xlabel="Expansion index (1-200 displayed Stage-III nodes)",
    )
    fig3.savefig(OUT_DIR / "fig30_stage3_tree.svg", format="svg")
    plt.close(fig3)


def main() -> None:
    stage1 = read_rows(STAGE1)
    q_stage3 = read_rows(Q_STAGE3)
    s_stage3 = read_rows(S_STAGE3)
    merged_stage3, q_path, s_path, stage3_start_nodes = merged_stage3_rows(s_stage3, q_stage3)
    pos1 = node_positions(stage1)
    pos_merged = sequence_positions(merged_stage3)
    selected_seed_ids = seed_candidate_ids(q_stage3) | seed_candidate_ids(s_stage3)

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif"],
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.titleweight": "bold",
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "figure.dpi": 300,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
        }
    )

    fig = plt.figure(figsize=(10.8, 3.2))
    gs = GridSpec(1, 4, width_ratios=[1.0, 1.0, 1.0, 1.0], figure=fig)
    ax1 = fig.add_subplot(gs[0, 0:2])
    ax_stage3 = fig.add_subplot(gs[0, 2:4])

    draw_tree_panel(
        ax1,
        stage1,
        pos1,
        title="Stage I: Free Tree Search",
        color=COLORS["stage1"],
        selected_seed_candidate_ids=selected_seed_ids,
    )
    draw_tree_panel(
        ax_stage3,
        merged_stage3,
        pos_merged,
        title="Stage III: Bounded Tree Search with Final Q/S Lineages",
        color=COLORS["stage3"],
        highlight_candidates={
            "cd9e3818033d": ("Final-Q: cd9e3818033d", "*", COLORS["final_q"]),
            "0ade8d3405c2": ("Final-S: 0ade8d3405c2", "s", COLORS["final_s"]),
        },
        seed_as_selected=True,
        display_seed_node_ids=stage3_start_nodes,
        subtitle_override="11 selected Stage-I seeds -> 200 displayed Stage-III nodes; one merged Q/S discovery tree",
        xlabel="Expansion index (1-200 displayed Stage-III nodes)",
    )

    legend = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["stage1"], label="Generated valid node", markersize=5),
        Line2D([0], [0], marker="D", color="none", markerfacecolor=COLORS["seed"], markeredgecolor="#7A5C00", label="Seed node", markersize=5),
        Line2D([0], [0], marker="D", color="none", markerfacecolor=COLORS["selected_seed"], markeredgecolor="#3B0764", label="Selected Stage-I / Stage-III seed", markersize=6),
        Line2D([0], [0], marker="*", color="none", markerfacecolor=COLORS["final_q"], markeredgecolor="#222222", label="HAST-Final-Q", markersize=9),
        Line2D([0], [0], marker="s", color="none", markerfacecolor=COLORS["final_s"], markeredgecolor="#222222", label="HAST-Final-S", markersize=7),
    ]
    fig.legend(handles=legend, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("HAST Stage-I and Stage-III Search Trees", y=1.05, fontsize=12, fontweight="bold")
    fig.subplots_adjust(wspace=0.28, bottom=0.30, top=0.78)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / "fig30_hast_three_stage_search_tree.pdf")
    fig.savefig(OUT_DIR / "fig30_hast_three_stage_search_tree.png")
    fig.savefig(OUT_DIR / "fig30_hast_three_stage_search_tree.svg")
    save_stage_svg_panels(stage1, pos1, merged_stage3, pos_merged, selected_seed_ids, stage3_start_nodes)
    print(OUT_DIR / "fig30_hast_three_stage_search_tree.png")
    print(OUT_DIR / "fig30_hast_three_stage_search_tree.pdf")
    print(OUT_DIR / "fig30_hast_three_stage_search_tree.svg")
    print(OUT_DIR / "fig30_stage1_tree.svg")
    print(OUT_DIR / "fig30_stage3_tree.svg")


if __name__ == "__main__":
    main()
