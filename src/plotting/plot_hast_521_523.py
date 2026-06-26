# -*- coding: utf-8 -*-
"""Generate section 5.2.1-5.2.3 figures for one completed HAST run."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "artifacts" / "source_tables" / "benchmark_12graph"
SEARCH_RUNTIME = ROOT / "artifacts" / "source_tables" / "search_runtime"
HAST_METHODS = {"HAST-Final-Q", "HAST-Final-S"}
HAST_GROUP_MARKERS = ("HAST", "HAST stage", "HAST final", "HAST-current")

COL = {
    "q": "#0072B2",
    "s": "#009E73",
    "hast_star_q": "#D62728",
    "hast_star_s": "#F2C94C",
    "era": "#E69F00",
    "llm": "#CC79A7",
    "classic": "#9CA3AF",
    "strong": "#6B7280",
    "warn": "#D55E00",
    "grid": "#D1D5DB",
    "text": "#111827",
}


def setup() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.2,
            "legend.fontsize": 7.4,
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


def compressed_log_time(seconds: float, low_log: float = -2.0, fast_compress: float = 0.35) -> float:
    x = np.log10(max(float(seconds), 10**low_log))
    return x * fast_compress if x < 0 else x


def compressed_r_axis(value: float) -> float:
    """Piecewise display coordinate: expand R in [0.3, 0.5], compress worse R."""
    r = float(value)
    if r <= 0.30:
        return r
    if r <= 0.50:
        return 0.30 + (r - 0.30) * 1.85
    return 0.30 + 0.20 * 1.85 + (r - 0.50) * 0.42


def save(fig: plt.Figure, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{stem}.png", facecolor="white")
    fig.savefig(out_dir / f"{stem}.pdf", facecolor="white")
    plt.close(fig)


def is_hast_like_frame(df: pd.DataFrame) -> pd.Series:
    mask = df["method"].astype(str).isin(HAST_METHODS)
    if "group" in df.columns:
        mask = mask | df["group"].astype(str).str.contains("HAST", case=False, na=False)
    if "paper_label" in df.columns:
        mask = mask | df["paper_label"].astype(str).str.contains("HAST", case=False, na=False)
    return mask


def run_method_map(run_dir: Path) -> dict[str, str]:
    manifest = json.loads((run_dir / "final" / "final_code_manifest.json").read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for label, item in manifest.items():
        if not item:
            continue
        cid = str(item.get("candidate_id", ""))
        method_mean = pd.read_csv(run_dir / "full_validation" / "method_mean_metrics.csv", encoding="utf-8-sig")
        matched = method_mean[method_mean["candidate_id"].astype(str).eq(cid)]
        if not matched.empty:
            out[str(matched.iloc[0]["method"])] = label
    return out


def load_quality_table(run_dir: Path) -> pd.DataFrame:
    base = pd.read_csv(BENCHMARK / "method_mean_metrics.csv", encoding="utf-8-sig")
    base = base[~is_hast_like_frame(base) & base["method"].ne("E26F")].copy()
    run = pd.read_csv(run_dir / "full_validation" / "method_mean_metrics.csv", encoding="utf-8-sig")
    mapping = run_method_map(run_dir)
    run["method"] = run["method"].map(lambda m: mapping.get(str(m), str(m)))
    run["group"] = "HAST-current"
    run["coverage"] = run["datasets"].astype(int).astype(str) + "/12"
    base["coverage"] = base["datasets"].astype(int).astype(str) + "/12"
    combined = pd.concat([base, run], ignore_index=True, sort=False)
    for col in ["mean_R", "mean_auc_cNBI", "mean_time_s", "datasets"]:
        combined[col] = pd.to_numeric(combined[col], errors="coerce")
    return combined


def coverage_note(run_dir: Path) -> str:
    per = pd.read_csv(run_dir / "full_validation" / "per_graph_metrics.csv", encoding="utf-8-sig")
    mapping = run_method_map(run_dir)
    notes = []
    for method, label in mapping.items():
        sub = per[per["method"].astype(str).eq(str(method))]
        total = len(sub)
        completed = int(sub["valid"].astype(str).str.lower().eq("true").sum()) if total else 0
        timeouts = int(sub["error"].astype(str).str.contains("timeout", case=False, na=False).sum()) if total else 0
        if timeouts:
            notes.append(f"{label}: {completed}/{total} completed, {timeouts} timeout")
        else:
            notes.append(f"{label}: {completed}/{total} completed")
    return "; ".join(notes) if notes else "Current HAST coverage unavailable"


def draw_521_quality_runtime(run_dir: Path, out_dir: Path) -> Path:
    data = load_quality_table(run_dir)
    data["x_plot"] = data["mean_time_s"].map(compressed_log_time)
    data["y_plot"] = data["mean_R"].map(compressed_r_axis)
    hast = {"HAST-Final-Q", "HAST-Final-S"}
    search = {"PUCT", "FunSearch-like", "Clade-AHD-like", "MCTS-AHD-like", "AlphaEvolve-like"}
    strong = {"NCDC", "NDC", "NDJC", "BPD/MinSum-fallback", "GND-py", "VE-py", "LGD-RA2-py", "LGD-RA2num-py", "LGD-CND-py"}
    classic = {"CoreHD", "HDA", "DC", "CI", "KCore", "CLUC"}
    colors = {
        "HAST-Final-Q": COL["hast_star_q"],
        "HAST-Final-S": COL["hast_star_s"],
        "PUCT": COL["era"],
        "FunSearch-like": "#CC79A7",
        "Clade-AHD-like": "#D55E00",
        "MCTS-AHD-like": "#009E73",
        "AlphaEvolve-like": "#7B8794",
        "NCDC": "#80B1D3",
        "NDC": "#8DD3C7",
        "NDJC": "#2CA02C",
        "BPD/MinSum-fallback": "#B15928",
        "GND-py": "#9467BD",
        "VE-py": "#17BECF",
        "LGD-RA2-py": "#A55194",
        "LGD-RA2num-py": "#6B6ECF",
        "LGD-CND-py": "#637939",
    }
    fig, ax = plt.subplots(figsize=(8.7, 5.8))
    for _, row in data.iterrows():
        method = str(row["method"])
        color = colors.get(method, "#6B7280")
        if method in hast:
            ax.scatter(row["x_plot"], row["y_plot"], marker="*", s=430, color=color, edgecolor="#111827", linewidth=1.45, zorder=7)
        elif method in search:
            ax.scatter(row["x_plot"], row["y_plot"], s=78, color=color, edgecolor="#111827", linewidth=0.75, alpha=0.95, zorder=5)
        elif method in strong:
            ax.scatter(row["x_plot"], row["y_plot"], s=48, color=color, edgecolor="white", linewidth=0.45, alpha=0.90, zorder=4)
        elif method in classic:
            ax.scatter(row["x_plot"], row["y_plot"], s=34, color=COL["classic"], edgecolor="white", linewidth=0.35, alpha=0.88, zorder=2)
        else:
            ax.scatter(row["x_plot"], row["y_plot"], s=34, color=COL["classic"], edgecolor="white", linewidth=0.35, alpha=0.82, zorder=2)
    labels = {"PUCT": "ERA-like"}
    offsets = {
        "HAST-Final-Q": (8, 9),
        "HAST-Final-S": (8, -14),
        "PUCT": (5, 7),
        "FunSearch-like": (5, 5),
        "Clade-AHD-like": (5, -11),
        "NCDC": (5, 6),
        "CoreHD": (5, -12),
        "HDA": (5, 5),
        "DC": (5, 5),
        "CI": (5, -8),
        "KCore": (5, 5),
        "CLUC": (5, -8),
        "NDC": (5, -9),
        "NDJC": (5, 5),
        "BPD/MinSum-fallback": (5, -10),
        "GND-py": (5, 5),
        "VE-py": (5, 5),
    }
    for _, row in data.iterrows():
        method = str(row["method"])
        dx, dy = offsets.get(method, (5, 3))
        suffix = f" ({row['coverage']})" if method in hast else ""
        if method in hast:
            fontsize, weight, color_text = 8.5, "bold", "#111827"
        elif method in search:
            fontsize, weight, color_text = 7.8, "normal", "#111827"
        elif method in strong:
            fontsize, weight, color_text = 7.0, "normal", "#374151"
        else:
            fontsize, weight, color_text = 6.5, "normal", "#4B5563"
        ax.annotate(
            labels.get(method, method) + suffix,
            (row["x_plot"], row["y_plot"]),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=fontsize,
            fontweight=weight,
            color=color_text,
        )
    ax.axvspan(compressed_log_time(0.01), compressed_log_time(1), color="#F3F4F6", alpha=0.75, zorder=0)
    tick_powers = [-2, -1, 0, 1, 2, 3]
    ax.set_xticks([compressed_log_time(10**p) for p in tick_powers])
    ax.set_xticklabels([rf"$10^{{{p}}}$" for p in tick_powers])
    ax.set_xlim(compressed_log_time(10**-2) - 0.08, compressed_log_time(10**3) + 0.12)
    r_ticks = [0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.80]
    ax.set_yticks([compressed_r_axis(v) for v in r_ticks])
    ax.set_yticklabels([f"{v:.2f}" for v in r_ticks])
    y_min = float(data["y_plot"].min())
    y_max = float(data["y_plot"].max())
    pad = max(0.015, (y_max - y_min) * 0.10)
    ax.set_ylim(y_min - pad, y_max + pad)
    ax.set_xlabel("Mean runtime per graph (s, log; sub-second compressed)")
    ax.set_ylabel("Mean R / GCC robustness (lower is better; expanded 0.30-0.50)")
    ax.set_title("5.2.1 R-runtime position, current HAST run")
    ax.text(0.01, 0.02, coverage_note(run_dir), transform=ax.transAxes, fontsize=7.5, color="#4B5563")
    save(fig, out_dir, "fig13_12graph_quality_runtime_all_methods")
    return out_dir / "fig13_12graph_quality_runtime_all_methods.png"


def draw_522_high_quality_panel(run_dir: Path, out_dir: Path) -> Path:
    data = load_quality_table(run_dir).set_index("method")
    selected = [m for m in ["FunSearch-like", "Clade-AHD-like", "PUCT", "NCDC", "BPD/MinSum-fallback", "HAST-Final-Q", "HAST-Final-S", "CoreHD"] if m in data.index]
    q_auc = float(data.loc["HAST-Final-Q", "mean_auc_cNBI"])
    q_time = float(data.loc["HAST-Final-Q", "mean_time_s"])
    rows = []
    for method in selected:
        rows.append(
            {
                "method": "ERA-like" if method == "PUCT" else method,
                "quality_vs_q": float(data.loc[method, "mean_auc_cNBI"]) / q_auc * 100.0,
                "speed_vs_q": q_time / float(data.loc[method, "mean_time_s"]),
                "coverage": data.loc[method, "coverage"],
                "raw": method,
            }
        )
    frame = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.4), gridspec_kw={"width_ratios": [1.2, 1.0]})
    y = np.arange(len(frame))
    colors = [COL["q"] if m == "HAST-Final-Q" else COL["s"] if m == "HAST-Final-S" else COL["era"] if m == "PUCT" else "#B8C2CC" for m in frame["raw"]]
    axes[0].barh(y, frame["quality_vs_q"], color=colors, height=0.62, edgecolor="white")
    axes[0].axvline(100, color="#777", ls="--", lw=1)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(frame["method"])
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, max(110, frame["quality_vs_q"].max() + 8))
    axes[0].set_xlabel("auc-cNBI vs current HAST-Final-Q (%)")
    axes[0].set_title("High-quality region")
    speed_vals = frame["speed_vs_q"].clip(upper=25)
    axes[1].barh(y, speed_vals, color=colors, height=0.62, edgecolor="white")
    axes[1].axvline(1, color="#777", ls="--", lw=1)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([])
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Speed relative to HAST-Final-Q")
    axes[1].set_title("Runtime advantage")
    for ax in axes:
        ax.grid(axis="x", alpha=0.18)
    fig.suptitle("5.2.2 Among high-quality candidates, current HAST trades quality for speed", y=1.03, fontsize=10.5, fontweight="bold")
    fig.text(0.02, -0.03, f"Current HAST-Final-Q/S coverage: {coverage_note(run_dir)}.", fontsize=7.5, color="#4B5563")
    save(fig, out_dir, "fig17_hast_quality_speed_panel")
    return out_dir / "fig17_hast_quality_speed_panel.png"


def read_point(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def baseline_point(dataset: str, method: str) -> pd.DataFrame:
    return read_point(BENCHMARK / dataset / "point_evaluations" / f"{safe_method_filename(method)}.csv")


def run_point(run_dir: Path, dataset: str, method: str) -> pd.DataFrame:
    matches = list((run_dir / "full_validation" / "point_evaluations" / dataset).glob(f"{method}.csv"))
    return read_point(matches[0]) if matches else pd.DataFrame()


def draw_curve_grid(run_dir: Path, out_dir: Path, metric: str, stem: str, title: str) -> Path:
    per_graph = pd.read_csv(run_dir / "full_validation" / "per_graph_metrics.csv", encoding="utf-8-sig")
    method_map = run_method_map(run_dir)
    label_to_method = {label: method for method, label in method_map.items()}
    datasets = ["CEnew", "Collaboration", "condmat", "crime", "email", "Grid", "GrQC", "hamster", "HepPh", "PH", "Powerlaw_500", "Yeast"]
    compare = ["PUCT", "FunSearch-like", "CoreHD", "HDA"]
    fig, axes = plt.subplots(3, 4, figsize=(12.4, 8.0), sharex=False, sharey=False)
    axes = axes.ravel()
    for ax, dataset in zip(axes, datasets):
        for method in compare:
            df = baseline_point(dataset, method)
            if df.empty or metric not in df:
                continue
            ax.plot(pd.to_numeric(df["removal_ratio"], errors="coerce"), pd.to_numeric(df[metric], errors="coerce"), lw=1.0, alpha=0.72, label="ERA-like" if method == "PUCT" else method)
        timeout_labels = []
        for label, method in label_to_method.items():
            row = per_graph[(per_graph["dataset"].eq(dataset)) & (per_graph["method"].eq(method))]
            valid = (not row.empty) and str(row.iloc[0].get("valid", "")).lower() == "true"
            if not valid:
                timeout_labels.append(label)
                continue
            df = run_point(run_dir, dataset, method)
            if df.empty or metric not in df:
                continue
            hast_color = COL["hast_star_q"] if label.endswith("Q") else COL["hast_star_s"]
            ax.plot(pd.to_numeric(df["removal_ratio"], errors="coerce"), pd.to_numeric(df[metric], errors="coerce"), lw=1.8, label=label, color=hast_color)
        ax.set_title(dataset, fontsize=9)
        if timeout_labels:
            ax.text(0.5, 0.5, "timeout under 90s:\n" + ", ".join(timeout_labels), transform=ax.transAxes, ha="center", va="center", fontsize=7, color=COL["warn"], bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": COL["warn"], "alpha": 0.85})
        ax.set_xlabel("Removal ratio", fontsize=7.5)
        ax.tick_params(labelsize=7)
    handles, labels = axes[0].get_legend_handles_labels()
    uniq = {}
    for h, l in zip(handles, labels):
        uniq.setdefault(l, h)
    fig.legend(uniq.values(), uniq.keys(), loc="lower center", ncol=6, frameon=False)
    fig.suptitle(title, y=0.995, fontsize=11, fontweight="bold")
    fig.text(0.02, 0.015, "Current HAST curves are shown only where the candidate completed under the 90s guard; timeout panels are explicitly marked.", fontsize=7.5, color="#4B5563")
    save(fig, out_dir, stem)
    return out_dir / f"{stem}.png"


def draw_523_curves(run_dir: Path, out_dir: Path) -> list[Path]:
    return [
        draw_curve_grid(run_dir, out_dir, "GCC", "fig10_gcc_curves_12graphs", "5.2.3 GCC curves across benchmark graphs"),
        draw_curve_grid(run_dir, out_dir, "cNBI", "fig11_cnbi_curves_12graphs", "5.2.3 cNBI curves across benchmark graphs"),
    ]


def stage_cost_row(stage: str, path: Path, label: str) -> dict[str, object]:
    if not path.exists():
        return {
            "paper_label": label,
            "group": "HAST stage",
            "candidates": 0,
            "valid_rate": 0.0,
            "mean_eval_s": float("nan"),
            "median_eval_s": float("nan"),
            "total_eval_s": 0.0,
            "mean_prompt_s": float("nan"),
            "median_prompt_s": float("nan"),
            "total_prompt_s": 0.0,
            "mean_logged_search_s_per_candidate": float("nan"),
            "total_logged_search_s": 0.0,
        }
    df = pd.read_csv(path, encoding="utf-8-sig")
    candidates = int(len(df))
    eval_s = pd.to_numeric(df.get("time_s", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    prompt_s = pd.to_numeric(df.get("llm_elapsed_s", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    valid = df.get("valid", pd.Series([False] * candidates)).astype(str).str.lower().isin({"true", "1", "yes"})
    logged = eval_s + prompt_s
    return {
        "paper_label": label,
        "group": "HAST stage",
        "candidates": candidates,
        "valid_rate": float(valid.mean()) if candidates else 0.0,
        "mean_eval_s": float(eval_s.mean()) if candidates else float("nan"),
        "median_eval_s": float(eval_s.median()) if candidates else float("nan"),
        "total_eval_s": float(eval_s.sum()),
        "mean_prompt_s": float(prompt_s.mean()) if candidates else float("nan"),
        "median_prompt_s": float(prompt_s.median()) if candidates else float("nan"),
        "total_prompt_s": float(prompt_s.sum()),
        "mean_logged_search_s_per_candidate": float(logged.mean()) if candidates else float("nan"),
        "total_logged_search_s": float(logged.sum()),
        "stage": stage,
    }


def load_search_cost_table(run_dir: Path) -> pd.DataFrame:
    base_path = SEARCH_RUNTIME / "framework_search_time_summary.csv"
    if base_path.exists():
        base = pd.read_csv(base_path, encoding="utf-8-sig")
        base = base[~is_hast_like_frame(base)].copy()
    else:
        base = pd.DataFrame()
    stage_rows = [
        stage_cost_row("stage1", run_dir / "stage1_candidate_log.csv", "HAST-free search"),
        stage_cost_row("stage3", run_dir / "stage3_candidate_log.csv", "HAST bounded search"),
    ]
    hast = pd.DataFrame(stage_rows)
    total_candidates = float(hast["candidates"].sum())
    if total_candidates:
        mean_row = {
            "paper_label": "mean HAST",
            "group": "HAST stage",
            "candidates": total_candidates,
            "valid_rate": float((hast["valid_rate"] * hast["candidates"]).sum() / total_candidates),
            "mean_eval_s": float((hast["mean_eval_s"] * hast["candidates"]).sum() / total_candidates),
            "median_eval_s": float(hast["median_eval_s"].median()),
            "total_eval_s": float(hast["total_eval_s"].sum()),
            "mean_prompt_s": float((hast["mean_prompt_s"] * hast["candidates"]).sum() / total_candidates),
            "median_prompt_s": float(hast["median_prompt_s"].median()),
            "total_prompt_s": float(hast["total_prompt_s"].sum()),
            "mean_logged_search_s_per_candidate": float((hast["mean_logged_search_s_per_candidate"] * hast["candidates"]).sum() / total_candidates),
            "total_logged_search_s": float(hast["total_logged_search_s"].sum()),
        }
        hast = pd.concat([hast, pd.DataFrame([mean_row])], ignore_index=True)
    return pd.concat([base, hast], ignore_index=True, sort=False)


def draw_524_framework_search_time(run_dir: Path, out_dir: Path) -> Path:
    df = load_search_cost_table(run_dir)
    df["paper_label"] = df["paper_label"].replace({"PUCT": "ERA-like"})
    order = ["ERA-like", "FunSearch-like", "Clade-AHD-like", "MCTS-AHD-like", "AlphaEvolve-like", "HAST-free search", "HAST bounded search", "mean HAST"]
    df = df[df["paper_label"].isin(order)].copy()
    df["paper_label"] = pd.Categorical(df["paper_label"], categories=order, ordered=True)
    df = df.sort_values("paper_label")
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.2), gridspec_kw={"width_ratios": [1.1, 1.0]})
    y = np.arange(len(df))
    colors = [COL["q"] if "HAST" in str(g) else "#B8C2CC" for g in df["group"]]
    labels = [str(x).replace(" ", "\n", 1) if len(str(x)) > 16 else str(x) for x in df["paper_label"]]
    search_s = pd.to_numeric(df["mean_logged_search_s_per_candidate"], errors="coerce").fillna(0.0)
    axes[0].barh(y, search_s, color=colors, height=0.62, edgecolor="white")
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels)
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, float(search_s.max()) + 14 if len(search_s) else 1)
    axes[0].set_xlabel("Mean logged search time / candidate (s)")
    axes[0].set_title("Candidate-level search cost")
    for yi, v in zip(y, search_s):
        axes[0].text(v + 1.2, yi, f"{v:.1f}s", va="center", fontsize=7.5)
    valid_pct = pd.to_numeric(df["valid_rate"], errors="coerce").fillna(0.0) * 100.0
    axes[1].barh(y, valid_pct, color=colors, height=0.62, edgecolor="white")
    axes[1].set_yticks(y)
    axes[1].set_yticklabels(labels)
    axes[1].invert_yaxis()
    axes[1].set_xlim(0, 105)
    axes[1].set_xlabel("Valid candidate rate (%)")
    axes[1].set_title("Generation validity")
    for yi, v in zip(y, valid_pct):
        axes[1].text(min(v + 1.0, 101.5), yi, f"{v:.1f}%", va="center", fontsize=7.5)
    fig.tight_layout(w_pad=4.0)
    fig.text(0.55, -0.02, "Logged search time = prompt elapsed time + candidate validation time; root excluded.", ha="center", fontsize=8, color="#555")
    save(fig, out_dir, "fig20_framework_search_time")
    return out_dir / "fig20_framework_search_time.png"


def write_summary(run_dir: Path, out_dir: Path, paths: list[Path]) -> None:
    mean = pd.read_csv(run_dir / "full_validation" / "method_mean_metrics.csv", encoding="utf-8-sig")
    per = pd.read_csv(run_dir / "full_validation" / "per_graph_metrics.csv", encoding="utf-8-sig")
    method_map = run_method_map(run_dir)
    mean["label"] = mean["method"].map(lambda m: method_map.get(str(m), str(m)))
    rows = []
    for _, row in mean.iterrows():
        method = row["method"]
        sub = per[per["method"].eq(method)]
        rows.append(
            {
                "label": row["label"],
                "candidate_id": row["candidate_id"],
                "completed": int(sub["valid"].astype(str).str.lower().eq("true").sum()),
                "total": int(len(sub)),
                "mean_R_completed": float(row["mean_R"]),
                "mean_auc_cNBI_completed": float(row["mean_auc_cNBI"]),
                "mean_time_s_completed": float(row["mean_time_s"]),
                "timeouts": int(sub["error"].astype(str).str.contains("timeout", case=False, na=False).sum()),
            }
        )
    selection_path = run_dir / "stage3_final_selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8")) if selection_path.exists() else {}
    summary = {"figures": [str(p) for p in paths], "current_run": rows, "stage3_final_selection": selection}
    (out_dir / "figures_5_2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    setup()
    run_dir = args.run_dir.resolve()
    out_dir = run_dir / "figures_5_2"
    paths = [
        draw_521_quality_runtime(run_dir, out_dir),
        draw_522_high_quality_panel(run_dir, out_dir),
        *draw_523_curves(run_dir, out_dir),
        draw_524_framework_search_time(run_dir, out_dir),
    ]
    write_summary(run_dir, out_dir, paths)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
