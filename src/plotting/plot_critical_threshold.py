# -*- coding: utf-8 -*-
"""Plot GCC critical-threshold ratios and 1% node counts from point curves."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "artifacts" / "source_tables" / "benchmark_12graph"
DATASETS = ["CEnew", "Collaboration", "condmat", "crime", "email", "Grid", "GrQC", "hamster", "HepPh", "PH", "Powerlaw_500", "Yeast"]
BASELINE_METHODS = ["PUCT", "FunSearch-like", "Clade-AHD-like", "NCDC", "BPD/MinSum-fallback", "CoreHD", "HDA"]
HAST_METHODS = ["HAST-Final-Q", "HAST-Final-S"]
THRESHOLD = 0.01
RATIO_THRESHOLDS = [0.10, 0.05]

COL = {
    "HAST-Final-Q": "#D62728",
    "HAST-Final-S": "#F2C94C",
    "PUCT": "#E69F00",
    "FunSearch-like": "#CC79A7",
    "Clade-AHD-like": "#D55E00",
    "NCDC": "#80B1D3",
    "BPD/MinSum-fallback": "#B15928",
    "CoreHD": "#9CA3AF",
    "HDA": "#6B7280",
}


def setup() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.2,
            "legend.fontsize": 7.6,
            "figure.dpi": 180,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.18,
        }
    )


def safe_method_filename(name: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._+-]+", "_", str(name)).strip("_")
    return text or "method"


def run_method_map(run_dir: Path) -> dict[str, str]:
    manifest_path = run_dir / "final" / "final_code_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    method_mean = pd.read_csv(run_dir / "full_validation" / "method_mean_metrics.csv", encoding="utf-8-sig")
    out: dict[str, str] = {}
    for label, item in manifest.items():
        if not item:
            continue
        cid = str(item.get("candidate_id", ""))
        matched = method_mean[method_mean["candidate_id"].astype(str).eq(cid)]
        if not matched.empty:
            out[str(matched.iloc[0]["method"])] = str(label)
    return out


def read_curve(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig")
    if "step" not in df or "removal_ratio" not in df or "GCC" not in df:
        return pd.DataFrame()
    out = df[["step", "removal_ratio", "GCC"]].copy()
    out["step"] = pd.to_numeric(out["step"], errors="coerce")
    out["removal_ratio"] = pd.to_numeric(out["removal_ratio"], errors="coerce")
    out["GCC"] = pd.to_numeric(out["GCC"], errors="coerce")
    out = out.dropna().sort_values("step")
    return out


def baseline_curve(dataset: str, method: str) -> pd.DataFrame:
    return read_curve(BENCHMARK / dataset / "point_evaluations" / f"{safe_method_filename(method)}.csv")


def run_curve(run_dir: Path, dataset: str, method: str) -> pd.DataFrame:
    matches = list((run_dir / "full_validation" / "point_evaluations" / dataset).glob(f"{method}.csv"))
    return read_curve(matches[0]) if matches else pd.DataFrame()


def first_crossing_nodes(curve: pd.DataFrame, threshold: float = THRESHOLD) -> tuple[float, bool]:
    if curve.empty:
        return float("nan"), False
    hit = curve[curve["GCC"].le(threshold)]
    if len(hit) == 0:
        return float(curve["step"].max()), False
    return float(hit.iloc[0]["step"]), True


def first_crossing_ratio(curve: pd.DataFrame, threshold: float) -> tuple[float, bool]:
    if curve.empty:
        return float("nan"), False
    x = np.concatenate([[0.0], curve["removal_ratio"].to_numpy(dtype=float)])
    y = np.concatenate([[1.0], curve["GCC"].to_numpy(dtype=float)])
    hit = np.where(y <= threshold)[0]
    if len(hit) == 0:
        return float(x[-1]), False
    i = int(hit[0])
    if i == 0:
        return float(x[0]), True
    x0, x1 = float(x[i - 1]), float(x[i])
    y0, y1 = float(y[i - 1]), float(y[i])
    if y0 == y1:
        return x1, True
    alpha = min(1.0, max(0.0, (threshold - y0) / (y1 - y0)))
    return x0 + alpha * (x1 - x0), True


def collect_ratio_thresholds(run_dir: Path) -> pd.DataFrame:
    method_map = run_method_map(run_dir)
    label_to_method = {label: method for method, label in method_map.items()}
    rows = []
    for dataset in DATASETS:
        for method in BASELINE_METHODS:
            curve = baseline_curve(dataset, method)
            for threshold in RATIO_THRESHOLDS:
                value, reached = first_crossing_ratio(curve, threshold)
                rows.append({"dataset": dataset, "method": method, "label": "ERA-like" if method == "PUCT" else method, "threshold": threshold, "ct_ratio": value, "reached": reached})
        for label in HAST_METHODS:
            method = label_to_method.get(label)
            if method is None:
                continue
            curve = run_curve(run_dir, dataset, method)
            for threshold in RATIO_THRESHOLDS:
                value, reached = first_crossing_ratio(curve, threshold)
                rows.append({"dataset": dataset, "method": label, "label": label, "threshold": threshold, "ct_ratio": value, "reached": reached})
    return pd.DataFrame(rows)


def collect_thresholds(run_dir: Path) -> pd.DataFrame:
    method_map = run_method_map(run_dir)
    label_to_method = {label: method for method, label in method_map.items()}
    rows = []
    for dataset in DATASETS:
        for method in BASELINE_METHODS:
            curve = baseline_curve(dataset, method)
            value, reached = first_crossing_nodes(curve)
            rows.append({"dataset": dataset, "method": method, "label": "ERA-like" if method == "PUCT" else method, "threshold": THRESHOLD, "ct_nodes": value, "reached": reached})
        for label in HAST_METHODS:
            method = label_to_method.get(label)
            if method is None:
                continue
            curve = run_curve(run_dir, dataset, method)
            value, reached = first_crossing_nodes(curve)
            rows.append({"dataset": dataset, "method": label, "label": label, "threshold": THRESHOLD, "ct_nodes": value, "reached": reached})
    return pd.DataFrame(rows)


def save(fig: plt.Figure, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{stem}.png", facecolor="white")
    fig.savefig(out_dir / f"{stem}.pdf", facecolor="white")
    plt.close(fig)


def plot_mean_ratios(df: pd.DataFrame, out_dir: Path) -> Path:
    summary = (
        df.groupby(["method", "label", "threshold"], as_index=False)
        .agg(mean_ct=("ct_ratio", "mean"), median_ct=("ct_ratio", "median"), reached_rate=("reached", "mean"), datasets=("dataset", "count"))
    )
    order = (
        summary[summary["threshold"].eq(0.10)]
        .sort_values(["mean_ct", "method"], ascending=[True, True])["method"]
        .tolist()
    )
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.4), sharey=True)
    y = np.arange(len(order))
    labels = [summary[summary["method"].eq(m)]["label"].iloc[0] for m in order]
    colors = [COL.get(m, "#9CA3AF") for m in order]
    for ax, threshold in zip(axes, RATIO_THRESHOLDS):
        part = summary[summary["threshold"].eq(threshold)].set_index("method").loc[order]
        values = part["mean_ct"].to_numpy(dtype=float)
        ax.barh(y, values, color=colors, edgecolor="white", height=0.64)
        ax.set_title(f"CT@{threshold:.2f}")
        ax.set_xlabel("Critical removal ratio (lower is better)")
        ax.set_xlim(0, max(0.55, float(np.nanmax(values)) + 0.04))
        ax.invert_yaxis()
        for yi, val, reached in zip(y, values, part["reached_rate"].to_numpy(dtype=float)):
            suffix = "" if reached >= 0.999 else f" ({reached * 100:.0f}%)"
            ax.text(val + 0.008, yi, f"{val:.3f}{suffix}", va="center", fontsize=7.4)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels)
    fig.suptitle("GCC critical threshold across 12 benchmark graphs", y=1.02, fontsize=11, fontweight="bold")
    fig.text(0.02, -0.02, "CT@tau is the first removal ratio where GCC <= tau, linearly interpolated between sampled points. Lower means earlier network collapse.", fontsize=7.8, color="#4B5563")
    save(fig, out_dir, "fig21_gcc_critical_threshold_mean")
    return out_dir / "fig21_gcc_critical_threshold_mean.png"


def plot_ct10_heatmap(df: pd.DataFrame, out_dir: Path) -> Path:
    part = df[df["threshold"].eq(0.10)].copy()
    order = part.groupby("method")["ct_ratio"].mean().sort_values().index.tolist()
    label_map = part.drop_duplicates("method").set_index("method")["label"].to_dict()
    mat = part.pivot(index="dataset", columns="method", values="ct_ratio").loc[DATASETS, order]
    fig, ax = plt.subplots(figsize=(10.2, 5.2))
    vmax = min(0.6, max(0.1, float(np.nanmax(mat.to_numpy(dtype=float)))))
    im = ax.imshow(mat.to_numpy(dtype=float), aspect="auto", cmap="viridis_r", vmin=0, vmax=vmax)
    ax.set_xticks(np.arange(len(order)))
    ax.set_xticklabels([label_map[m] for m in order], rotation=35, ha="right")
    ax.set_yticks(np.arange(len(DATASETS)))
    ax.set_yticklabels(DATASETS)
    ax.set_title("Per-graph GCC critical threshold CT@0.10")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            val = mat.iloc[i, j]
            if pd.notna(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=6.8, color="white" if val > 0.22 else "#111827")
    cbar = fig.colorbar(im, ax=ax, fraction=0.028, pad=0.02)
    cbar.set_label("Removal ratio, lower is better")
    fig.text(0.02, -0.02, "Each cell is the deletion fraction where the method first reduces GCC to 10% of the original graph.", fontsize=7.8, color="#4B5563")
    save(fig, out_dir, "fig22_gcc_critical_threshold_ct10_heatmap")
    return out_dir / "fig22_gcc_critical_threshold_ct10_heatmap.png"


def plot_mean_nodes(df: pd.DataFrame, out_dir: Path) -> Path:
    summary = (
        df.groupby(["method", "label"], as_index=False)
        .agg(mean_nodes=("ct_nodes", "mean"), median_nodes=("ct_nodes", "median"), reached_rate=("reached", "mean"), datasets=("dataset", "count"))
        .sort_values(["mean_nodes", "method"], ascending=[True, True])
    )
    y = np.arange(len(summary))
    values = summary["mean_nodes"].to_numpy(dtype=float)
    colors = [COL.get(m, "#9CA3AF") for m in summary["method"]]
    fig, ax = plt.subplots(figsize=(7.8, 4.9))
    ax.barh(y, values, color=colors, edgecolor="white", height=0.64)
    ax.set_yticks(y)
    ax.set_yticklabels(summary["label"])
    ax.set_xlabel("Mean nodes removed until GCC <= 1% (lower is better)")
    ax.set_title("GCC critical threshold at 1% across 12 benchmark graphs")
    ax.set_xlim(0, float(np.nanmax(values)) * 1.16)
    ax.invert_yaxis()
    for yi, val, reached in zip(y, values, summary["reached_rate"].to_numpy(dtype=float)):
        suffix = "" if reached >= 0.999 else f" ({reached * 100:.0f}% reached)"
        ax.text(val + float(np.nanmax(values)) * 0.012, yi, f"{val:.1f}{suffix}", va="center", fontsize=7.5)
    fig.text(0.02, -0.02, "Critical threshold follows the advisor definition: the first integer deletion step where GCC falls to 1% or below.", fontsize=7.8, color="#4B5563")
    save(fig, out_dir, "fig21_gcc_critical_threshold_1pct_nodes_mean")
    return out_dir / "fig21_gcc_critical_threshold_1pct_nodes_mean.png"


def plot_per_graph_nodes(df: pd.DataFrame, out_dir: Path) -> Path:
    order = df.groupby("method")["ct_nodes"].mean().sort_values().index.tolist()
    label_map = df.drop_duplicates("method").set_index("method")["label"].to_dict()
    fig, axes = plt.subplots(3, 4, figsize=(13.0, 8.1), sharex=False)
    axes = axes.ravel()
    for ax, dataset in zip(axes, DATASETS):
        part = df[df["dataset"].eq(dataset)].set_index("method").loc[order].reset_index()
        y = np.arange(len(order))
        values = part["ct_nodes"].to_numpy(dtype=float)
        colors = [COL.get(m, "#9CA3AF") for m in part["method"]]
        ax.barh(y, values, color=colors, edgecolor="white", height=0.62)
        ax.set_title(dataset, fontsize=9.2)
        ax.invert_yaxis()
        ax.tick_params(labelsize=7)
        ax.set_xlim(0, float(np.nanmax(values)) * 1.16)
        for yi, val, reached in zip(y, values, part["reached"].to_numpy(dtype=bool)):
            suffix = "" if reached else "*"
            ax.text(val + float(np.nanmax(values)) * 0.015, yi, f"{val:.0f}{suffix}", va="center", fontsize=6.5)
        if ax in axes[::4]:
            ax.set_yticks(y)
            ax.set_yticklabels([label_map[m] for m in order])
        else:
            ax.set_yticks(y)
            ax.set_yticklabels([])
        ax.set_xlabel("Nodes", fontsize=7.4)
    fig.suptitle("Per-graph GCC critical threshold: nodes removed until GCC <= 1%", y=0.995, fontsize=11, fontweight="bold")
    fig.text(0.02, 0.012, "Lower is better. Asterisks mark methods that did not reach GCC <= 1% within the recorded curve; their last recorded step is shown.", fontsize=7.8, color="#4B5563")
    save(fig, out_dir, "fig22_gcc_critical_threshold_1pct_nodes_12graphs")
    return out_dir / "fig22_gcc_critical_threshold_1pct_nodes_12graphs.png"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    setup()
    run_dir = args.run_dir.resolve()
    out_dir = run_dir / "figures_5_2"
    ratio_df = collect_ratio_thresholds(run_dir)
    node_df = collect_thresholds(run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ratio_df.to_csv(out_dir / "critical_threshold_ratio_values.csv", index=False, encoding="utf-8-sig")
    ratio_summary = (
        ratio_df.groupby(["method", "label", "threshold"], as_index=False)
        .agg(mean_ct=("ct_ratio", "mean"), median_ct=("ct_ratio", "median"), std_ct=("ct_ratio", "std"), reached_rate=("reached", "mean"), datasets=("dataset", "count"))
        .sort_values(["threshold", "mean_ct", "method"])
    )
    ratio_summary.to_csv(out_dir / "critical_threshold_ratio_summary.csv", index=False, encoding="utf-8-sig")
    node_df.to_csv(out_dir / "critical_threshold_1pct_nodes_values.csv", index=False, encoding="utf-8-sig")
    node_summary = (
        node_df.groupby(["method", "label", "threshold"], as_index=False)
        .agg(mean_nodes=("ct_nodes", "mean"), median_nodes=("ct_nodes", "median"), std_nodes=("ct_nodes", "std"), reached_rate=("reached", "mean"), datasets=("dataset", "count"))
        .sort_values(["mean_nodes", "method"])
    )
    node_summary.to_csv(out_dir / "critical_threshold_1pct_nodes_summary.csv", index=False, encoding="utf-8-sig")
    outputs = [
        plot_mean_ratios(ratio_df, out_dir),
        plot_ct10_heatmap(ratio_df, out_dir),
        plot_mean_nodes(node_df, out_dir),
        plot_per_graph_nodes(node_df, out_dir),
    ]
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
