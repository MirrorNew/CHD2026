# -*- coding: utf-8 -*-
"""Regenerate the HAST-Final-Q case study tables and figures."""

from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model.config import DATASET_RATES, DATASETS
from model.data import read_graph
from metrics.ND_fragmentation import compute_metrics, summarize_metrics


RUN_DIR = ROOT / "src" / "runs" / "runs_HAST_root_target_family_full_ritelt_20260525"
OUT_TABLE_DIR = ROOT / "artifacts" / "source_tables" / "case_study_hast_q"
FIG_DIR = ROOT / "artifacts" / "figures"

COL = {
    "full": "#0072B2",
    "knock": "#B8C2CC",
    "degree": "#7B8794",
    "accent": "#009E73",
    "warn": "#D55E00",
}


@dataclass(frozen=True)
class Variant:
    name: str
    label: str
    disable_frontier_twohop: bool = False
    disable_bridge_weak: bool = False
    disable_leaf_low: bool = False
    disable_redundancy_penalty: bool = False
    fixed_phase: bool = False
    degree_only: bool = False


VARIANTS = [
    Variant("full", "HAST-Final-Q full"),
    Variant("no_frontier_twohop", "- frontier/two-hop", disable_frontier_twohop=True),
    Variant("no_bridge_weak", "- bridge/weak", disable_bridge_weak=True),
    Variant("no_leaf_low", "- leaf/low pressure", disable_leaf_low=True),
    Variant("no_redundancy_penalty", "- redundancy penalty", disable_redundancy_penalty=True),
    Variant(
        "no_local_terms",
        "- all local terms",
        disable_frontier_twohop=True,
        disable_bridge_weak=True,
        disable_leaf_low=True,
        disable_redundancy_penalty=True,
    ),
    Variant("no_phase", "- phase weights", fixed_phase=True),
    Variant("degree_only", "residual degree only", degree_only=True),
]


def caps(progress: float, fixed_phase: bool = False) -> tuple[int, int, int, float, float, float, float]:
    if fixed_phase:
        progress = 0.25
    if progress < 0.16:
        return 22, 7, 112, 1.12, 0.88, 0.82, 0.70
    if progress < 0.38:
        return 28, 9, 128, 1.02, 1.08, 1.00, 0.88
    if progress < 0.66:
        return 34, 10, 128, 0.94, 1.18, 1.15, 1.05
    return 40, 12, 128, 0.86, 1.06, 1.32, 1.22


def refresh_caps(progress: float, fixed_phase: bool = False) -> tuple[int, int, int]:
    if fixed_phase:
        progress = 0.25
    if progress < 0.18:
        return 20, 6, 96
    if progress < 0.52:
        return 24, 7, 112
    return 28, 8, 128


def raw_terms(H: nx.Graph, deg: dict[Any, int], u: Any, n0: int, variant: Variant) -> dict[str, float]:
    d = deg.get(u, 0)
    if d <= 0:
        return {k: 0.0 for k in [
            "degree", "frontier", "twohop", "bridge", "weak", "leaf_pressure", "redundancy", "avg_nd", "max_nd",
            "term_hub", "term_frontier_twohop", "term_bridge_weak", "term_leaf_low", "term_redundancy_penalty",
        ]}
    rem = H.number_of_nodes()
    progress = 1.0 - float(rem) / float(n0)
    ncap, twcap, total_tw_cap, hub_w, front_w, bridge_w, red_w = caps(progress, fixed_phase=variant.fixed_phase)
    neigh_all = list(H.neighbors(u))
    neigh = neigh_all[:ncap]
    scanned = len(neigh)
    if scanned == 0:
        return {
            "degree": float(d),
            "frontier": 0.0,
            "twohop": 0.0,
            "bridge": 0.0,
            "weak": 0.0,
            "leaf_pressure": 0.0,
            "redundancy": 0.0,
            "avg_nd": 0.0,
            "max_nd": 0.0,
            "term_hub": hub_w * float(d) * 2.85,
            "term_frontier_twohop": 0.0,
            "term_bridge_weak": 0.0,
            "term_leaf_low": 0.0,
            "term_redundancy_penalty": 0.0,
        }
    nd_sum = max_nd = leaf_n = low_n = low4_n = 0.0
    boundary = weak = bridge_cnt = pendant_front = low_front = 0.0
    internal_edges = outward_sum = outward_max = 0.0
    twohop_mass = twohop_low = 0.0
    twohop_seen: set[Any] = set()
    twohop_steps = 0
    neigh_set = set(neigh_all) if d <= 30 else set(neigh)
    for v in neigh:
        dv = deg.get(v, 0)
        nd_sum += dv
        max_nd = max(max_nd, float(dv))
        if dv <= 1:
            leaf_n += 1.0
        if dv <= 3:
            low_n += 1.0
        if dv <= 4:
            low4_n += 1.0
        ext = inc = c2 = 0
        for w in H.neighbors(v):
            if w == u:
                continue
            if w in neigh_set:
                inc += 1
            else:
                ext += 1
                if w not in twohop_seen:
                    twohop_seen.add(w)
                    dw = deg.get(w, 0)
                    twohop_mass += math.sqrt(float(dw) + 1.0)
                    if dw <= 3:
                        twohop_low += 1.0
                c2 += 1
                twohop_steps += 1
                if c2 >= twcap or twohop_steps >= total_tw_cap:
                    break
        internal_edges += inc
        outward_sum += ext
        outward_max = max(outward_max, float(ext))
        if ext > inc:
            boundary += 1.0
        if ext == 0:
            weak += 0.35
        else:
            weak += float(ext) / float(dv + 1)
        if inc <= 1 and ext >= 1:
            bridge_cnt += 1.0
        if ext >= 2 and dv <= 4:
            low_front += 1.0
        if ext >= 1 and dv <= 2:
            pendant_front += 1.0
        if twohop_steps >= total_tw_cap:
            break
    inv_scan = 1.0 / float(scanned)
    avg_nd = nd_sum * inv_scan
    redundancy = internal_edges * inv_scan
    frontier = boundary + 0.55 * low_front + 0.38 * pendant_front + 0.16 * outward_sum
    bridge = bridge_cnt + 0.28 * outward_max + 0.22 * weak + 0.18 * twohop_low
    leaf_pressure = leaf_n * 1.25 + low_n * 0.45 + low4_n * 0.18
    twohop = twohop_mass + 0.42 * len(twohop_seen)
    term_hub = hub_w * (float(d) * 2.85 + math.sqrt(float(d) + 1.0) * avg_nd * 0.34)
    term_frontier_twohop = front_w * (frontier * 1.55 + twohop * 0.21)
    term_bridge_weak = bridge_w * (bridge * 1.36 + weak * 0.44)
    term_leaf_low = leaf_pressure
    term_redundancy_penalty = -red_w * redundancy * 0.54
    return {
        "degree": float(d),
        "frontier": float(frontier),
        "twohop": float(twohop),
        "bridge": float(bridge),
        "weak": float(weak),
        "leaf_pressure": float(leaf_pressure),
        "redundancy": float(redundancy),
        "avg_nd": float(avg_nd),
        "max_nd": float(max_nd),
        "term_hub": float(term_hub),
        "term_frontier_twohop": float(term_frontier_twohop),
        "term_bridge_weak": float(term_bridge_weak),
        "term_leaf_low": float(term_leaf_low),
        "term_redundancy_penalty": float(term_redundancy_penalty),
    }


def score_node(H: nx.Graph, deg: dict[Any, int], u: Any, n0: int, variant: Variant) -> tuple[float, ...]:
    d = deg.get(u, 0)
    su = str(u)
    if d <= 0:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, su)
    if variant.degree_only:
        return (float(d), float(d), 0.0, float(d), 0.0, 0.0, 0.0, 0.0, su)
    terms = raw_terms(H, deg, u, n0, variant)
    rem = H.number_of_nodes()
    progress = 1.0 - float(rem) / float(n0)
    _, _, _, hub_w, front_w, bridge_w, red_w = caps(progress, fixed_phase=variant.fixed_phase)
    frontier = 0.0 if variant.disable_frontier_twohop else terms["frontier"]
    twohop = 0.0 if variant.disable_frontier_twohop else terms["twohop"]
    bridge = 0.0 if variant.disable_bridge_weak else terms["bridge"]
    weak = 0.0 if variant.disable_bridge_weak else terms["weak"]
    leaf_pressure = 0.0 if variant.disable_leaf_low else terms["leaf_pressure"]
    redundancy_penalty = 0.0 if variant.disable_redundancy_penalty else red_w * terms["redundancy"] * 0.54
    main = (
        hub_w * (float(d) * 2.85 + math.sqrt(float(d) + 1.0) * terms["avg_nd"] * 0.34)
        + front_w * (frontier * 1.55 + twohop * 0.21)
        + bridge_w * (bridge * 1.36 + weak * 0.44)
        + leaf_pressure
        - redundancy_penalty
    )
    secondary = (
        float(d) * 1.75
        + terms["avg_nd"] * 0.72
        + frontier * 0.92
        + bridge * 0.68
        + twohop * 0.12
        - (0.0 if variant.disable_redundancy_penalty else terms["redundancy"] * 0.36)
    )
    tertiary = frontier + weak * 0.55 + bridge * 0.70
    return (
        float(main),
        float(secondary),
        float(tertiary),
        float(d),
        float(twohop),
        float(frontier),
        float(-terms["redundancy"]),
        float(terms["max_nd"]),
        su,
    )


def hast_q_order_variant(G: nx.Graph, variant: Variant, record_features: bool = False) -> tuple[list[Any], list[dict[str, Any]]]:
    import heapq

    H = G.copy()
    n0 = H.number_of_nodes()
    if n0 == 0:
        return [], []
    deg = dict(H.degree())
    heap: list[tuple[Any, ...]] = []
    stamp: dict[Any, int] = {}
    tick = 0
    feature_rows: list[dict[str, Any]] = []

    def push(u: Any) -> None:
        nonlocal tick
        if u not in deg:
            return
        tick += 1
        stamp[u] = tick
        key = score_node(H, deg, u, n0, variant)
        heapq.heappush(heap, (-key[0], -key[1], -key[2], -key[3], -key[4], -key[5], -key[6], -key[7], key[8], tick, u))

    for node in list(H.nodes()):
        push(node)
    order: list[Any] = []
    while deg:
        retries = 0
        u = None
        while heap and retries < 6:
            item = heapq.heappop(heap)
            t = item[9]
            cand = item[10]
            if cand in deg and stamp.get(cand) == t:
                u = cand
                break
            retries += 1
        if u is None:
            while heap:
                item = heapq.heappop(heap)
                t = item[9]
                cand = item[10]
                if cand in deg and stamp.get(cand) == t:
                    u = cand
                    break
            if u is None:
                u = max(deg, key=lambda x: (deg[x], str(x)))
        if u not in deg:
            continue
        step = len(order) + 1
        if record_features and step <= max(1, int(round(0.20 * n0))):
            row = raw_terms(H, deg, u, n0, variant)
            row.update({"step": step, "removal_ratio": step / n0, "node": str(u)})
            feature_rows.append(row)
        affected: set[Any] = set()
        if u in H:
            neigh = list(H.neighbors(u))
            affected.update(neigh)
            rem = H.number_of_nodes()
            progress = 1.0 - float(rem) / float(n0)
            capn, capt, total = refresh_caps(progress, fixed_phase=variant.fixed_phase)
            touched = 0
            for v in neigh[:capn]:
                c = 0
                for w in H.neighbors(v):
                    if w != u:
                        affected.add(w)
                        c += 1
                        touched += 1
                        if c >= capt or touched >= total:
                            break
                if touched >= total:
                    break
        order.append(u)
        H.remove_node(u)
        deg.pop(u, None)
        for v in affected:
            if v in H:
                deg[v] = H.degree[v]
                push(v)
    return order, feature_rows


def evaluate_variants() -> tuple[pd.DataFrame, pd.DataFrame]:
    per_graph_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        graph = read_graph(dataset)
        rate = DATASET_RATES.get(dataset, 0.30)
        full_order, _ = hast_q_order_variant(graph, VARIANTS[0], record_features=False)
        prefix_steps = max(1, int(round(0.20 * graph.number_of_nodes())))
        for variant in VARIANTS:
            t0 = time.perf_counter()
            if variant.name == "full":
                order = full_order
                _, features = hast_q_order_variant(graph, variant, record_features=True)
            else:
                order, features = hast_q_order_variant(graph, variant, record_features=variant.name == "degree_only")
            elapsed = time.perf_counter() - t0
            curve = compute_metrics(graph, order, rate=rate, method_time=elapsed)
            summary = summarize_metrics(curve)
            same_prefix_positions = sum(1 for a, b in zip(full_order[:prefix_steps], order[:prefix_steps]) if a == b)
            per_graph_rows.append(
                {
                    "dataset": dataset,
                    "variant": variant.name,
                    "label": variant.label,
                    "nodes": graph.number_of_nodes(),
                    "steps": len(curve),
                    "full_order_equal": bool(order == full_order),
                    "prefix20_positions": prefix_steps,
                    "prefix20_same_positions": same_prefix_positions,
                    "prefix20_change_rate": 1.0 - same_prefix_positions / prefix_steps,
                    **summary,
                }
            )
            for row in features:
                row.update({"dataset": dataset, "variant": variant.name, "label": variant.label})
                feature_rows.append(row)
    return pd.DataFrame(per_graph_rows), pd.DataFrame(feature_rows)


def stage_summary() -> pd.DataFrame:
    stage1 = pd.read_csv(RUN_DIR / "stage1_candidate_log.csv", encoding="utf-8-sig")
    stage3 = pd.read_csv(RUN_DIR / "stage3_candidate_log.csv", encoding="utf-8-sig")
    return pd.DataFrame(
        [
            {
                "stage": "Stage 1 free tree search",
                "budget": 300,
                "generated_nodes": len(stage1),
                "valid_nodes": int(stage1["valid"].astype(bool).sum()),
                "valid_rate": float(stage1["valid"].astype(bool).mean()),
                "mean_prompt_s": float(stage1["llm_elapsed_s"].mean()),
                "mean_candidate_time_s": float(stage1["time_s"].mean()),
            },
            {"stage": "Stage 2 bound induction", "budget": 10, "generated_nodes": 0, "valid_nodes": 0},
            {
                "stage": "Stage 3 bounded tree search",
                "budget": 200,
                "generated_nodes": len(stage3),
                "valid_nodes": int(stage3["valid"].astype(bool).sum()),
                "valid_rate": float(stage3["valid"].astype(bool).mean()),
                "mean_prompt_s": float(stage3["llm_elapsed_s"].mean()),
                "mean_candidate_time_s": float(stage3["time_s"].mean()),
            },
        ]
    )


def lineage_table() -> pd.DataFrame:
    final = json.loads((RUN_DIR / "stage3_final_selection.json").read_text(encoding="utf-8"))
    stage3 = pd.read_csv(RUN_DIR / "stage3_tree_nodes.csv", encoding="utf-8-sig")
    rows = []
    current = final["HAST-Final-Q"]["candidate_id"]
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        sub = stage3[stage3["candidate_id"].astype(str).eq(current)]
        if sub.empty:
            break
        r = sub.iloc[0]
        rows.append(
            {
                "node_id": r["node_id"],
                "candidate_id": r["candidate_id"],
                "parent_node_id": r["parent_node_id"],
                "parent_candidate_id": r["parent_candidate_id"],
                "depth": int(r["depth"]),
                "tree_branch": r.get("tree_branch", ""),
                "proxy_R": float(r["R"]),
                "proxy_auc_cNBI": float(r["auc_cNBI"]),
                "proxy_time_s": float(r["time_s"]),
                "delta_root_auc_cNBI": float(r["delta_root_auc_cNBI"]),
            }
        )
        current = str(r["parent_candidate_id"]) if pd.notna(r["parent_candidate_id"]) else ""
    return pd.DataFrame(rows).iloc[::-1].reset_index(drop=True)


def aggregate_knockouts(per_graph: pd.DataFrame) -> pd.DataFrame:
    mean = (
        per_graph.groupby(["variant", "label"], as_index=False)
        .agg(
            datasets=("dataset", "nunique"),
            mean_R=("R", "mean"),
            mean_auc_cNBI=("auc_cNBI", "mean"),
            mean_time_s=("time_s", "mean"),
            mean_early_cNBI=("early_cNBI", "mean"),
            full_order_equal_graphs=("full_order_equal", "sum"),
            mean_prefix20_change_rate=("prefix20_change_rate", "mean"),
        )
        .sort_values("mean_auc_cNBI", ascending=False)
    )
    full_auc = float(mean.loc[mean["variant"].eq("full"), "mean_auc_cNBI"].iloc[0])
    full_time = float(mean.loc[mean["variant"].eq("full"), "mean_time_s"].iloc[0])
    mean["delta_auc_vs_full"] = mean["mean_auc_cNBI"] - full_auc
    mean["time_ratio_vs_full"] = mean["mean_time_s"] / full_time
    mean["full_order_equal_graphs"] = mean["full_order_equal_graphs"].astype(int)
    return mean


def aggregate_features(features: pd.DataFrame) -> pd.DataFrame:
    keep = ["degree", "frontier", "twohop", "bridge", "weak", "leaf_pressure", "redundancy", "avg_nd"]
    mean = features.groupby(["variant", "label"], as_index=False)[keep].mean()
    full = mean[mean["variant"].eq("full")].iloc[0]
    deg = mean[mean["variant"].eq("degree_only")].iloc[0]
    rows = []
    for feature in keep:
        base = float(deg[feature])
        rows.append(
            {
                "feature": feature,
                "HAST_Final_Q": float(full[feature]),
                "residual_degree_only": base,
                "ratio_HAST_over_degree": float(full[feature] / base) if base else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def aggregate_score_terms(features: pd.DataFrame) -> pd.DataFrame:
    terms = [
        ("term_hub", "hub/degree"),
        ("term_frontier_twohop", "frontier/two-hop"),
        ("term_bridge_weak", "bridge/weak"),
        ("term_leaf_low", "leaf/low"),
        ("term_redundancy_penalty", "redundancy penalty"),
    ]
    full = features[features["variant"].eq("full")].copy()
    rows = []
    for col, label in terms:
        mean_signed = float(full[col].mean())
        mean_abs = float(full[col].abs().mean())
        rows.append({"term": col, "label": label, "mean_signed": mean_signed, "mean_abs": mean_abs})
    out = pd.DataFrame(rows)
    total_abs = float(out["mean_abs"].sum())
    out["abs_share"] = out["mean_abs"] / total_abs if total_abs else 0.0
    return out


def draw_knockout(mean: pd.DataFrame) -> None:
    order = [
        "full",
        "no_frontier_twohop",
        "no_bridge_weak",
        "no_leaf_low",
        "no_redundancy_penalty",
        "no_local_terms",
        "no_phase",
        "degree_only",
    ]
    frame = mean.set_index("variant").loc[order].reset_index()
    colors = [COL["full"] if v == "full" else COL["degree"] if v == "degree_only" else COL["knock"] for v in frame["variant"]]
    labels = frame["label"].tolist()
    fig, axes = plt.subplots(1, 3, figsize=(14.4, 4.6), gridspec_kw={"width_ratios": [1.1, 0.95, 1.1]})
    y = np.arange(len(frame))
    axes[0].barh(y, frame["mean_auc_cNBI"], color=colors, edgecolor="white", height=0.62)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels)
    axes[0].invert_yaxis()
    axes[0].axvline(float(frame.loc[frame["variant"].eq("full"), "mean_auc_cNBI"].iloc[0]), color="#111827", ls="--", lw=1)
    axes[0].set_xlabel("Mean auc-cNBI")
    axes[0].set_title("Component knockout quality")
    for yi, v in zip(y, frame["mean_auc_cNBI"]):
        axes[0].text(v + 3.0, yi, f"{v:.1f}", va="center", fontsize=8)
    axes[1].barh(y, frame["mean_R"], color=colors, edgecolor="white", height=0.62)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([])
    axes[1].invert_yaxis()
    full_r = float(frame.loc[frame["variant"].eq("full"), "mean_R"].iloc[0])
    axes[1].axvline(full_r, color="#111827", ls="--", lw=1)
    axes[1].set_xlim(max(0, float(frame["mean_R"].min()) - 0.025), float(frame["mean_R"].max()) + 0.025)
    axes[1].set_xlabel("Mean R (lower is better)")
    axes[1].set_title("GCC/R effect")
    for yi, v in zip(y, frame["mean_R"]):
        axes[1].text(v + 0.0025, yi, f"{v:.3f}", va="center", fontsize=8)
    changed_pct = frame["mean_prefix20_change_rate"] * 100.0
    axes[2].barh(y, changed_pct, color=colors, edgecolor="white", height=0.62)
    axes[2].set_yticks(y)
    axes[2].set_yticklabels([])
    axes[2].invert_yaxis()
    axes[2].set_xlim(0, 102)
    axes[2].set_xlabel("First-20% order changed vs full (%)")
    axes[2].set_title("Order sensitivity")
    for yi, v, eq in zip(y, changed_pct, frame["full_order_equal_graphs"]):
        text = f"{v:.1f}%"
        if eq == 12:
            text += " / all orders identical"
        axes[2].text(min(v + 1.0, 96), yi, text, va="center", fontsize=8)
    fig.tight_layout(w_pad=3.0)
    fig.savefig(FIG_DIR / "fig27_hast_q_component_knockout.png", dpi=240)
    fig.savefig(FIG_DIR / "fig27_hast_q_component_knockout.pdf")
    plt.close(fig)


def draw_features(feature_mean: pd.DataFrame) -> None:
    labels = {
        "degree": "residual degree",
        "frontier": "frontier",
        "twohop": "two-hop mass",
        "bridge": "bridge",
        "weak": "weak",
        "leaf_pressure": "leaf/low pressure",
        "redundancy": "redundancy",
        "avg_nd": "avg neighbor degree",
    }
    frame = feature_mean.copy()
    frame["label"] = frame["feature"].map(labels)
    frame = frame.sort_values("ratio_HAST_over_degree", ascending=True)
    fig, ax = plt.subplots(figsize=(8.8, 4.4))
    y = np.arange(len(frame))
    colors = [COL["full"] if v >= 1.0 else COL["degree"] for v in frame["ratio_HAST_over_degree"]]
    ax.barh(y, frame["ratio_HAST_over_degree"], color=colors, edgecolor="white", height=0.62)
    ax.axvline(1.0, color="#111827", ls="--", lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels(frame["label"])
    ax.set_xlabel("Feature ratio: HAST-Final-Q / residual-degree-only")
    ax.set_title("Early removed-node structural profile")
    for yi, v in zip(y, frame["ratio_HAST_over_degree"]):
        ax.text(v + 0.018, yi, f"{v:.2f}x", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig28_hast_q_early_node_features.png", dpi=240)
    fig.savefig(FIG_DIR / "fig28_hast_q_early_node_features.pdf")
    plt.close(fig)


def draw_score_terms(score_terms: pd.DataFrame) -> None:
    frame = score_terms.copy()
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.0), gridspec_kw={"width_ratios": [1.1, 1]})
    y = np.arange(len(frame))
    colors = [COL["full"] if row["term"] == "term_hub" else COL["accent"] if row["mean_signed"] >= 0 else COL["warn"] for _, row in frame.iterrows()]
    axes[0].barh(y, frame["mean_signed"], color=colors, edgecolor="white", height=0.62)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(frame["label"])
    axes[0].invert_yaxis()
    axes[0].axvline(0, color="#111827", lw=1)
    axes[0].set_xlabel("Mean signed score contribution")
    axes[0].set_title("Score terms on selected early nodes")
    for yi, v in zip(y, frame["mean_signed"]):
        axes[0].text(v + (0.2 if v >= 0 else -0.2), yi, f"{v:.2f}", va="center", ha="left" if v >= 0 else "right", fontsize=8)
    axes[1].barh(y, frame["abs_share"] * 100, color=colors, edgecolor="white", height=0.62)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([])
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Absolute contribution share (%)")
    axes[1].set_title("Relative scale of score terms")
    for yi, v in zip(y, frame["abs_share"] * 100):
        axes[1].text(v + 1.0, yi, f"{v:.1f}%", va="center", fontsize=8)
    fig.tight_layout(w_pad=3.0)
    fig.savefig(FIG_DIR / "fig29_hast_q_score_decomposition.png", dpi=240)
    fig.savefig(FIG_DIR / "fig29_hast_q_score_decomposition.pdf")
    plt.close(fig)


def main() -> None:
    OUT_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    per_graph, features = evaluate_variants()
    knockout_mean = aggregate_knockouts(per_graph)
    feature_mean = aggregate_features(features)
    score_terms = aggregate_score_terms(features)
    stages = stage_summary()
    lineage = lineage_table()
    per_graph.to_csv(OUT_TABLE_DIR / "hast_q_knockout_per_graph.csv", index=False, encoding="utf-8-sig")
    knockout_mean.to_csv(OUT_TABLE_DIR / "hast_q_knockout_mean.csv", index=False, encoding="utf-8-sig")
    features.to_csv(OUT_TABLE_DIR / "hast_q_early_node_features_raw.csv", index=False, encoding="utf-8-sig")
    feature_mean.to_csv(OUT_TABLE_DIR / "hast_q_early_node_features_mean.csv", index=False, encoding="utf-8-sig")
    score_terms.to_csv(OUT_TABLE_DIR / "hast_q_score_decomposition.csv", index=False, encoding="utf-8-sig")
    stages.to_csv(OUT_TABLE_DIR / "hast_q_search_stage_summary.csv", index=False, encoding="utf-8-sig")
    lineage.to_csv(OUT_TABLE_DIR / "hast_q_lineage.csv", index=False, encoding="utf-8-sig")
    draw_knockout(knockout_mean)
    draw_features(feature_mean)
    draw_score_terms(score_terms)
    report = {
        "tables": str(OUT_TABLE_DIR),
        "figures": [
            str(FIG_DIR / "fig27_hast_q_component_knockout.png"),
            str(FIG_DIR / "fig28_hast_q_early_node_features.png"),
            str(FIG_DIR / "fig29_hast_q_score_decomposition.png"),
        ],
        "knockout_mean": knockout_mean.to_dict("records"),
        "lineage": lineage.to_dict("records"),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

