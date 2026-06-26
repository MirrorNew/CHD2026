# -*- coding: utf-8 -*-
"""Draw a new Section 5.2.1 figure: classic R vs complexity class."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "artifacts" / "figures" / "05_2_benchmark"
FIG_STEM = "fig13_12graph_quality_complexity_all_methods"
CLASSIC_R = ROOT / "src" / "runs" / "classic_r_recomputed_20260624" / "method_mean_classic_r.csv"

BLOCKED = {"PUCT", "E26F", "BPD/MinSum-fallback", "GND-uniform_cost"}
DISPLAY = {"FINDER-uniform_cost": "FINDER"}


COMPLEXITY = {
    "DC": (0, r"$o(m+n\,\log n)$", "static degree scoring plus deterministic sorting", "local static-degree implementation", ""),
    "KCore": (0, r"$o(m+n\,\log n)$", "linear-time core decomposition plus deterministic sorting", "Batagelj-Zaversnik k-core complexity plus local sorter", "https://arxiv.org/abs/cs/0310049"),
    "HDA": (1, r"$o((m+n)\log n)$", "adaptive degree with heap/local degree updates on sparse graphs", "CI/HDA heap-update literature and local fast fallback", "https://www.nature.com/articles/srep30062"),
    "CoreHD": (1, r"$o((m+n)\log n)$", "highest degree in a maintained 2-core on sparse graphs", "CoreHD paper mechanism plus local fast fallback", "https://www.nature.com/articles/srep37954"),
    "CI": (1, r"$o((m+n)\log n)$", "fixed-radius Collective Influence with heap updates", "Morone-Makse CI fixed-radius complexity", "https://www.nature.com/articles/srep30062"),
    "HAST-Final-Q": (1, r"$o((m+n)\log n)$", "bounded local caps plus lazy heap", "local final candidate code upper bound", "src/runs/runs_paper_evidence_20260616/.../final/HAST-Final-Q.py"),
    "HAST-Final-S": (1, r"$o((m+n)\log n)$", "bounded local caps plus lazy heap", "local final candidate code upper bound", "src/runs/runs_paper_evidence_20260616/.../final/HAST-Final-S.py"),
    "CLUC": (2, r"$o(m\Delta)$", "ClusterRank-style local clustering / triangle term", "ClusterRank formula plus local clustering computation", "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0077455"),
    "NDC": (3, r"$o(n\Delta^2)$", "neighbor-dissimilarity score over bounded local neighborhoods", "NDC/NDJC paper complexity analysis", "https://www.homexinlu.com/files/%5B168%5D%202024%20ESWA_The%20role%20of%20link%20redundancy%20and%20structural%20heterogeneity%20in%20network%20disintegration.pdf"),
    "MCTS-AHD-like": (3, r"$o(n\Delta^2)$", "dynamic local two-hop rescoring", "local final candidate code upper bound", "src/runs/classic_r_recomputed_20260624/sequence_input_manifest.csv"),
    "FunSearch-like": (3, r"$o(n\Delta^2)$", "dynamic local branch/two-hop rescoring", "local final candidate code upper bound", "src/runs/classic_r_recomputed_20260624/sequence_input_manifest.csv"),
    "NCDC": (4, r"$o(m\,\log n+n\Delta^2)$", "community detection plus neighbor-dissimilarity scoring", "NDC/NDJC paper complexity analysis", "https://www.homexinlu.com/files/%5B168%5D%202024%20ESWA_The%20role%20of%20link%20redundancy%20and%20structural%20heterogeneity%20in%20network%20disintegration.pdf"),
    "NDJC": (4, r"$o(m\,\log n+n\Delta^2)$", "community detection plus Jaccard neighbor-dissimilarity scoring", "NDC/NDJC paper complexity analysis", "https://www.homexinlu.com/files/%5B168%5D%202024%20ESWA_The%20role%20of%20link%20redundancy%20and%20structural%20heterogeneity%20in%20network%20disintegration.pdf"),
    "AlphaEvolve-like": (5, r"$o(n(m+n))$", "dynamic component split and component-size scoring", "local final candidate code upper bound", "src/runs/classic_r_recomputed_20260624/sequence_input_manifest.csv"),
    "Clade-AHD-like": (5, r"$o(n(m+n))$", "periodic full component refresh", "local final candidate code upper bound", "src/runs/classic_r_recomputed_20260624/sequence_input_manifest.csv"),
    "FINDER-uniform_cost": (6, "RL-method", "reinforcement-learning method; uniform-cost sequence only", "FINDER paper category and user-specified axis placement", "https://arxiv.org/abs/1906.07978"),
}


COLORS = {
    "ours": "#D55E00",
    "algorithm_found": "#0072B2",
    "native_strong_baseline": "#009E73",
    "native_baseline": "#7B8794",
}

MARKERS = {
    "ours": "*",
    "algorithm_found": "o",
    "native_strong_baseline": "s",
    "native_baseline": "^",
}

JITTER = {
    "HAST-Final-Q": -0.18,
    "HAST-Final-S": 0.18,
    "CoreHD": -0.30,
    "HDA": -0.20,
    "DC": -0.18,
    "CI": 0.00,
    "KCore": 0.18,
    "CLUC": 0.00,
    "NDC": -0.18,
    "MCTS-AHD-like": 0.00,
    "FunSearch-like": 0.18,
    "NCDC": -0.16,
    "NDJC": 0.16,
    "AlphaEvolve-like": -0.14,
    "Clade-AHD-like": 0.14,
    "FINDER-uniform_cost": 0.00,
}

OFFSETS = {
    "FINDER-uniform_cost": (-56, -8),
    "HAST-Final-Q": (7, 8),
    "HAST-Final-S": (7, -13),
    "Clade-AHD-like": (8, 12),
    "FunSearch-like": (5, -14),
    "AlphaEvolve-like": (-74, -18),
    "MCTS-AHD-like": (8, 12),
    "NCDC": (7, -18),
    "NDC": (-34, -18),
    "NDJC": (5, 7),
    "CoreHD": (4, 7),
    "HDA": (4, -12),
    "DC": (4, 7),
    "CLUC": (5, 7),
    "CI": (4, -12),
    "KCore": (4, 7),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_frame() -> pd.DataFrame:
    df = pd.read_csv(CLASSIC_R, encoding="utf-8-sig")
    df = df[~df["method"].isin(BLOCKED)].copy()
    df = df[df["method"].isin(COMPLEXITY)].copy()
    df["complete_12_graphs"] = df["complete_12_graphs"].astype(str).str.lower().eq("true")
    df = df[df["complete_12_graphs"] | df["method"].eq("FINDER-uniform_cost")].copy()
    rows = []
    for _, row in df.iterrows():
        method = str(row["method"])
        rank, label, note, source, source_url = COMPLEXITY[method]
        rows.append(
            {
                "method": method,
                "display_method": DISPLAY.get(method, method),
                "group": str(row["group"]),
                "datasets": int(row["datasets"]),
                "complete_12_graphs": bool(row["complete_12_graphs"]),
                "mean_classic_R_percent": float(row["mean_classic_R_percent"]),
                "mean_classic_R_fraction": float(row["mean_classic_R_fraction"]),
                "complexity_rank": rank,
                "complexity_label": label,
                "complexity_note": note,
                "complexity_source": source,
                "complexity_source_url": source_url,
                "x_plot": rank + JITTER.get(method, 0.0),
            }
        )
    return pd.DataFrame(rows).sort_values(["complexity_rank", "mean_classic_R_percent"])


def write_data(frame: pd.DataFrame) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / f"{FIG_STEM}.data.csv"
    frame.to_csv(out, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    return out


def draw(frame: pd.DataFrame) -> tuple[Path, Path]:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.8,
            "axes.titlesize": 11,
            "axes.labelsize": 9.8,
            "legend.fontsize": 7.8,
            "figure.dpi": 180,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.20,
        }
    )
    fig, ax = plt.subplots(figsize=(11.3, 5.8))
    for _, row in frame.iterrows():
        group = row["group"]
        color = COLORS.get(group, "#6B7280")
        marker = MARKERS.get(group, "o")
        complete = bool(row["complete_12_graphs"])
        size = 390 if group == "ours" else 92 if group == "algorithm_found" else 76
        ax.scatter(
            row["x_plot"],
            row["mean_classic_R_percent"],
            s=size,
            marker=marker,
            facecolor=color if complete else "white",
            edgecolor="#111827" if group == "ours" else color if not complete else "white",
            linewidth=1.35 if group == "ours" or not complete else 0.6,
            alpha=0.96,
            zorder=6 if group == "ours" else 4 if not complete else 3,
        )

    for _, row in frame.iterrows():
        method = str(row["method"])
        label = str(row["display_method"])
        if not bool(row["complete_12_graphs"]):
            label += f" ({int(row['datasets'])}/12)"
        label += f"\nR={row['mean_classic_R_percent']:.2f}"
        dx, dy = OFFSETS.get(method, (5, 3))
        ax.annotate(
            label,
            (row["x_plot"], row["mean_classic_R_percent"]),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=8.4 if row["group"] == "ours" else 7.2,
            fontweight="bold" if row["group"] == "ours" else "normal",
            color="#111827" if row["group"] == "ours" else "#374151",
        )

    tick_labels = [
        "$o(m+n\\,\\log n)$",
        "$o((m+n)\\log n)$",
        "$o(m\\Delta)$",
        "$o(n\\Delta^2)$",
        "$o(m\\,\\log n+n\\Delta^2)$",
        "$o(n(m+n))$",
        "RL-method",
    ]
    ax.set_xticks(range(len(tick_labels)))
    ax.set_xticklabels(tick_labels)
    ax.set_xlim(-0.55, 6.55)
    y_min = frame["mean_classic_R_percent"].min() - 0.9
    y_max = frame["mean_classic_R_percent"].max() + 1.0
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel("Ordering complexity class")
    ax.set_ylabel("Classic full-sequence R (%) (lower is better)")
    ax.set_title("5.2.1 Root-relative HAST quality-complexity position")
    ax.axvspan(-0.5, 0.5, color="#F3F4F6", alpha=0.70, zorder=0)
    ax.axvspan(5.5, 6.5, color="#ECFDF5", alpha=0.76, zorder=0)
    legend_items = [
        ("ours", "HAST final"),
        ("algorithm_found", "algorithm-found"),
        ("native_baseline", "classic baseline"),
        ("native_strong_baseline", "strong / RL baseline"),
    ]
    handles = [
        plt.Line2D(
            [0],
            [0],
            marker=MARKERS[group],
            linestyle="",
            markerfacecolor=COLORS[group],
            markeredgecolor="#111827" if group == "ours" else "white",
            markersize=10 if group == "ours" else 7,
        )
        for group, _ in legend_items
    ]
    ax.legend(handles, [label for _, label in legend_items], loc="upper right", frameon=True, framealpha=0.94)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    png = FIG_DIR / f"{FIG_STEM}.png"
    pdf = FIG_DIR / f"{FIG_STEM}.pdf"
    fig.savefig(png, facecolor="white")
    fig.savefig(pdf, facecolor="white")
    plt.close(fig)
    return png, pdf


def update_manifest(png: Path, pdf: Path, data: Path) -> None:
    manifest = ROOT / "artifacts" / "figures" / "figure_manifest.csv"
    if not manifest.exists():
        return
    with manifest.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return
    fields = list(rows[0].keys())
    target_ref = f"../artifacts/figures/05_2_benchmark/{FIG_STEM}.png"
    updated = False
    for row in rows:
        if row.get("paper_line") == "727":
            row["original_src"] = target_ref
            row["resolved_src"] = str(png)
            row["copied_image"] = str(png)
            row["copied_pdf"] = str(pdf)
            row["data"] = str(data)
            row["raster_pdf"] = "False"
            updated = True
            break
    if not updated:
        rows.append(
            {
                field: ""
                for field in fields
            }
        )
        rows[-1].update(
            {
                "paper_line": "727",
                "section": "05_2_benchmark",
                "kind": "markdown",
                "original_src": target_ref,
                "resolved_src": str(png),
                "status": "ok",
                "copied_image": str(png),
                "copied_pdf": str(pdf),
                "data": str(data),
                "raster_pdf": "False",
            }
        )
    with manifest.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    frame = load_frame()
    missing = sorted(set(COMPLEXITY) - set(frame["method"]))
    if missing:
        print("Skipped methods:", ", ".join(missing))
    data = write_data(frame)
    png, pdf = draw(frame)
    update_manifest(png, pdf, data)
    print(png)
    print(pdf)
    print(data)


if __name__ == "__main__":
    main()
