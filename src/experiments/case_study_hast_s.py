# -*- coding: utf-8 -*-
"""重建 HAST-Final-S 案例研究表格和图片。

该脚本只读阶段3固定候选：它用受控 knockout 重实现已发现的
HAST-Final-S 评分模板，再用完整验证相同的指标函数评估这些变体。
"""

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
from metrics.fragmentation import compute_metrics, summarize_metrics


RUN_DIR = ROOT / "src" / "runs" / "runs_HAST_root_target_family_full_ritelt_20260525"
OUT_TABLE_DIR = ROOT / "artifacts" / "source_tables" / "case_study_hast_s"
FIG_DIR = ROOT / "artifacts" / "figures"

COL = {
    "full": "#009E73",
    "knock": "#B8C2CC",
    "degree": "#7B8794",
    "accent": "#0072B2",
    "warn": "#D55E00",
}


@dataclass(frozen=True)
class Variant:
    name: str
    label: str
    disable_frontier: bool = False
    disable_boundary_reach: bool = False
    disable_weak_bridge: bool = False
    disable_redundancy_penalty: bool = False
    fixed_phase: bool = False
    degree_only: bool = False


VARIANTS = [
    Variant("full", "HAST-Final-S full"),
    Variant("no_frontier", "- frontier"),
    Variant("no_boundary_reach", "- boundary/reach"),
    Variant("no_weak_bridge", "- weak/bridge"),
    Variant("no_redundancy_penalty", "- redundancy penalty"),
    Variant(
        "no_local_terms",
        "- all local terms",
        disable_frontier=True,
        disable_boundary_reach=True,
        disable_weak_bridge=True,
        disable_redundancy_penalty=True,
    ),
    Variant("no_phase", "- phase weights", fixed_phase=True),
    Variant("degree_only", "residual degree only", degree_only=True),
]


def node_key(u: Any) -> str:
    return str(u)


def phase_params(p: float, fixed_phase: bool = False) -> tuple[int, int, int, int, float, float, float, float, float, float, float]:
    if fixed_phase:
        p = 0.20
    if p < 0.04:
        return (24, 5, 18, 16, 1.30, 0.72, 0.78, 0.82, 1.08, 0.66, 0.72)
    if p < 0.14:
        return (32, 5, 24, 20, 1.18, 0.92, 0.92, 0.98, 1.04, 0.80, 0.86)
    if p < 0.34:
        return (44, 6, 30, 26, 1.02, 1.14, 1.08, 1.12, 0.98, 1.00, 1.02)
    if p < 0.58:
        return (52, 6, 34, 30, 0.92, 1.26, 1.22, 1.24, 0.92, 1.16, 1.16)
    if p < 0.80:
        return (60, 7, 32, 28, 0.84, 1.16, 1.38, 1.30, 0.86, 1.28, 1.28)
    return (64, 7, 28, 26, 0.78, 1.00, 1.46, 1.22, 0.80, 1.38, 1.36)


def probe_features(H: nx.Graph, deg: dict[Any, int], u: Any, n0: int, variant: Variant) -> dict[str, float]:
    d = deg.get(u, 0)
    if d <= 0:
        return {
            "degree": 0.0,
            "frontier": 0.0,
            "twohop": 0.0,
            "boundary_frac": 0.0,
            "weak_pressure": 0.0,
            "bridge_pressure": 0.0,
            "reach": 0.0,
            "redundancy": 0.0,
            "low_frac": 0.0,
            "pendant_frac": 0.0,
        }
    rem = H.number_of_nodes()
    p = 1.0 - float(rem) / float(n0)
    ncap, scap, _, _, hub_w, front_w, bound_w, weak_w, leaf_w, bridge_w, reach_w = phase_params(
        p, fixed_phase=variant.fixed_phase
    )
    neigh_all = list(H.neighbors(u))
    if len(neigh_all) > ncap:
        neigh = neigh_all[:ncap]
        scale = float(d) / float(ncap)
    else:
        neigh = neigh_all
        scale = 1.0
    neigh_set = set(neigh)
    leaf_n = low_n = 0
    boundary = twohop = 0
    weak = 0.0
    outward_max = 0
    bridge_cnt = 0
    internal_hits = 0
    sampled_pairs = 0
    seen2: set[Any] = set()
    for v in neigh:
        dv = deg.get(v, 0)
        if dv <= 1:
            leaf_n += 1
        if dv <= 3:
            low_n += 1
        inv = outv = c = 0
        for w in H.neighbors(v):
            if w == u:
                continue
            if w in neigh_set:
                inv += 1
            else:
                outv += 1
                boundary += 1
                if w not in seen2:
                    seen2.add(w)
                    twohop += 1
                outward_max = max(outward_max, deg.get(w, 0))
            c += 1
            if c >= scap:
                break
        internal_hits += inv
        sampled_pairs += c
        if outv > inv:
            weak += outv - inv
        if inv <= 1 and outv >= 2:
            bridge_cnt += 1
    sd = len(neigh)
    if sd <= 0:
        return {
            "degree": float(d),
            "frontier": 0.0,
            "twohop": 0.0,
            "boundary_frac": 0.0,
            "weak_pressure": 0.0,
            "bridge_pressure": 0.0,
            "reach": 0.0,
            "redundancy": 0.0,
            "low_frac": 0.0,
            "pendant_frac": 0.0,
        }
    boundary_frac = boundary / float(boundary + internal_hits + 1)
    weak_pressure = scale * weak / float(sampled_pairs + 1)
    bridge_pressure = scale * bridge_cnt * (1.0 + boundary_frac)
    redundancy = internal_hits / float(sampled_pairs + sd + 1)
    avg_nd = sum(deg.get(v, 0) for v in neigh) / sd
    max_nd = max((deg.get(v, 0) for v in neigh), default=0)
    low4_frac = sum(1 for v in neigh if deg.get(v, 0) <= 4) / sd
    frontier = scale * (boundary + 0.62 * twohop)
    reach = scale * (twohop + 0.36 * outward_max)
    assort_pen = avg_nd / float(d + avg_nd + 1.0)
    logd = math.log1p(d)
    sqd = math.sqrt(d)
    term_degree = hub_w * (d + 0.34 * sqd * logd)
    term_frontier = front_w * (0.030 * frontier + 0.070 * math.sqrt(frontier + 1.0))
    term_boundary_reach = bound_w * (1.18 * boundary_frac + 0.016 * boundary * scale) + reach_w * (
        0.034 * reach + 0.018 * outward_max
    )
    term_weak_bridge = weak_w * (0.92 * weak_pressure + 0.050 * math.sqrt(weak + 1.0)) + bridge_w * (
        0.58 * bridge_pressure
    )
    term_leaf_misc = leaf_w * (0.18 * (leaf_n / sd)) + 0.020 * max_nd + 0.010 * avg_nd
    term_penalty = -(1.05 * redundancy + 0.125 * (low_n / sd) + 0.070 * low4_frac + 0.052 * (leaf_n / sd) + 0.135 * assort_pen)
    return {
        "degree": float(d),
        "frontier": float(frontier),
        "twohop": float(twohop),
        "boundary_frac": float(boundary_frac),
        "weak_pressure": float(weak_pressure),
        "bridge_pressure": float(bridge_pressure),
        "reach": float(reach),
        "redundancy": float(redundancy),
        "low_frac": float(low_n / sd),
        "pendant_frac": float(leaf_n / sd),
        "term_degree": float(term_degree),
        "term_frontier": float(term_frontier),
        "term_boundary_reach": float(term_boundary_reach),
        "term_weak_bridge": float(term_weak_bridge),
        "term_leaf_misc": float(term_leaf_misc),
        "term_penalty": float(term_penalty),
    }


def score_node(H: nx.Graph, deg: dict[Any, int], u: Any, n0: int, variant: Variant) -> tuple[float, ...]:
    su = node_key(u)
    d = deg.get(u, 0)
    if d <= 0:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, su)
    if variant.degree_only:
        return (float(d), float(d), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, su)

    rem = H.number_of_nodes()
    p = 1.0 - float(rem) / float(n0)
    ncap, scap, _, _, hub_w, front_w, bound_w, weak_w, leaf_w, bridge_w, reach_w = phase_params(
        p, fixed_phase=variant.fixed_phase
    )
    neigh_all = list(H.neighbors(u))
    if len(neigh_all) > ncap:
        neigh = neigh_all[:ncap]
        scale = float(d) / float(ncap)
    else:
        neigh = neigh_all
        scale = 1.0
    neigh_set = set(neigh)
    nd_sum = 0.0
    max_nd = 0
    leaf_n = low_n = low4_n = 0
    boundary = twohop = 0
    weak = 0.0
    outward_max = 0
    bridge_cnt = 0
    internal_hits = 0
    sampled_pairs = 0
    seen2: set[Any] = set()
    for v in neigh:
        dv = deg.get(v, 0)
        nd_sum += dv
        max_nd = max(max_nd, dv)
        if dv <= 1:
            leaf_n += 1
        if dv <= 3:
            low_n += 1
        if dv <= 4:
            low4_n += 1
        inv = outv = c = 0
        for w in H.neighbors(v):
            if w == u:
                continue
            if w in neigh_set:
                inv += 1
            else:
                outv += 1
                boundary += 1
                if w not in seen2:
                    seen2.add(w)
                    twohop += 1
                outward_max = max(outward_max, deg.get(w, 0))
            c += 1
            if c >= scap:
                break
        internal_hits += inv
        sampled_pairs += c
        if outv > inv:
            weak += outv - inv
        if inv <= 1 and outv >= 2:
            bridge_cnt += 1
    sd = len(neigh)
    if sd <= 0:
        return (float(d), float(d), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, su)
    avg_nd = nd_sum / sd
    frontier = scale * (boundary + 0.62 * twohop)
    reach = scale * (twohop + 0.36 * outward_max)
    boundary_frac = boundary / float(boundary + internal_hits + 1)
    weak_pressure = scale * weak / float(sampled_pairs + 1)
    bridge_pressure = scale * bridge_cnt * (1.0 + boundary_frac)
    redundancy = internal_hits / float(sampled_pairs + sd + 1)
    low_frac = low_n / sd
    low4_frac = low4_n / sd
    pendant_frac = leaf_n / sd
    assort_pen = avg_nd / float(d + avg_nd + 1.0)

    if variant.disable_frontier:
        front_w = 0.0
        frontier = 0.0
    if variant.disable_boundary_reach:
        bound_w = 0.0
        reach_w = 0.0
    if variant.disable_weak_bridge:
        weak_w = 0.0
        bridge_w = 0.0
    logd = math.log1p(d)
    sqd = math.sqrt(d)
    penalty = 0.0 if variant.disable_redundancy_penalty else (
        1.05 * redundancy + 0.125 * low_frac + 0.070 * low4_frac + 0.052 * pendant_frac + 0.135 * assort_pen
    )
    val = (
        hub_w * (d + 0.34 * sqd * logd)
        + front_w * (0.030 * frontier + 0.070 * math.sqrt(frontier + 1.0))
        + bound_w * (1.18 * boundary_frac + 0.016 * boundary * scale)
        + weak_w * (0.92 * weak_pressure + 0.050 * math.sqrt(weak + 1.0))
        + bridge_w * (0.58 * bridge_pressure)
        + reach_w * (0.034 * reach + 0.018 * outward_max)
        + leaf_w * (0.18 * pendant_frac)
        + 0.020 * max_nd
        + 0.010 * avg_nd
        - penalty
    )
    return (
        float(val),
        float(d),
        float(frontier),
        float(bridge_pressure),
        float(reach),
        -float(redundancy),
        float(boundary_frac),
        float(max_nd),
        su,
    )


def hast_s_order_variant(G: nx.Graph, variant: Variant, record_features: bool = False) -> tuple[list[Any], list[dict[str, Any]]]:
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
        k = score_node(H, deg, u, n0, variant)
        heapq.heappush(heap, (-k[0], -k[1], -k[2], -k[3], -k[4], -k[5], -k[6], -k[7], k[8], tick, u))

    for node in list(H.nodes()):
        push(node)

    order: list[Any] = []
    while deg:
        retries = 0
        chosen = None
        while heap:
            item = heapq.heappop(heap)
            t = item[9]
            u = item[10]
            if u not in deg:
                continue
            if stamp.get(u) == t:
                chosen = u
                break
            retries += 1
            if retries >= 4:
                push(u)
                retries = 0
        if chosen is None:
            chosen = max(deg, key=lambda x: (deg[x], node_key(x)))
        if chosen not in deg:
            continue
        u = chosen
        step = len(order) + 1
        if record_features and step <= max(1, int(round(0.20 * n0))):
            row = probe_features(H, deg, u, n0, variant)
            row.update({"step": step, "removal_ratio": step / n0, "node": str(u)})
            feature_rows.append(row)

        affected: set[Any] = set()
        if u in H:
            neigh = list(H.neighbors(u))
            affected.update(neigh)
            rem = H.number_of_nodes()
            p = 1.0 - float(rem) / float(n0)
            _, scap, acap, tcap, *_ = phase_params(p, fixed_phase=variant.fixed_phase)
            first = neigh[:acap]
            added2 = 0
            for v in first:
                c = 0
                for w in H.neighbors(v):
                    if w != u:
                        affected.add(w)
                        added2 += 1
                    c += 1
                    if c >= scap or added2 >= tcap:
                        break
                if added2 >= tcap:
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
        full_order, _ = hast_s_order_variant(graph, VARIANTS[0], record_features=False)
        prefix_steps = max(1, int(round(0.20 * graph.number_of_nodes())))
        for variant in VARIANTS:
            t0 = time.perf_counter()
            if variant.name == "full":
                order = full_order
                _, features = hast_s_order_variant(graph, variant, record_features=True)
            else:
                order, features = hast_s_order_variant(graph, variant, record_features=variant.name == "degree_only")
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
    stage2_policy = json.loads((RUN_DIR / "stage2" / "family_policy.json").read_text(encoding="utf-8"))
    rows = [
        {
            "stage": "Stage 1 free tree search",
            "budget": 300,
            "generated_nodes": len(stage1),
            "valid_nodes": int(stage1["valid"].astype(bool).sum()),
            "valid_rate": float(stage1["valid"].astype(bool).mean()),
            "mean_prompt_s": float(stage1["llm_elapsed_s"].mean()),
            "mean_candidate_time_s": float(stage1["time_s"].mean()),
        },
        {
            "stage": "Stage 2 bound induction",
            "budget": 10,
            "generated_nodes": 0,
            "valid_nodes": 0,
            "valid_rate": float("nan"),
            "mean_prompt_s": float("nan"),
            "mean_candidate_time_s": float("nan"),
            "policy_items": len(stage2_policy) if isinstance(stage2_policy, dict) else 0,
        },
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
    return pd.DataFrame(rows)


def lineage_table() -> pd.DataFrame:
    final = json.loads((RUN_DIR / "stage3_final_selection.json").read_text(encoding="utf-8"))
    stage3 = pd.read_csv(RUN_DIR / "stage3_tree_nodes.csv", encoding="utf-8-sig")
    rows = []
    current = final["HAST-Final-S"]["candidate_id"]
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
    keep = ["degree", "frontier", "twohop", "boundary_frac", "weak_pressure", "bridge_pressure", "reach", "redundancy", "low_frac"]
    mean = features.groupby(["variant", "label"], as_index=False)[keep].mean()
    full = mean[mean["variant"].eq("full")].iloc[0]
    deg = mean[mean["variant"].eq("degree_only")].iloc[0]
    rows = []
    for feature in keep:
        rows.append(
            {
                "feature": feature,
                "HAST_Final_S": float(full[feature]),
                "residual_degree_only": float(deg[feature]),
                "ratio_HAST_over_degree": float(full[feature] / deg[feature]) if float(deg[feature]) != 0 else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def aggregate_score_terms(features: pd.DataFrame) -> pd.DataFrame:
    terms = [
        ("term_degree", "residual degree"),
        ("term_frontier", "frontier"),
        ("term_boundary_reach", "boundary/reach"),
        ("term_weak_bridge", "weak/bridge"),
        ("term_leaf_misc", "leaf/misc local"),
        ("term_penalty", "penalties"),
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
        "no_frontier",
        "no_boundary_reach",
        "no_weak_bridge",
        "no_redundancy_penalty",
        "no_local_terms",
        "no_phase",
        "degree_only",
    ]
    frame = mean.set_index("variant").loc[order].reset_index()
    labels = frame["label"].tolist()
    colors = [COL["full"] if v == "full" else COL["degree"] if v == "degree_only" else COL["knock"] for v in frame["variant"]]
    fig, axes = plt.subplots(1, 3, figsize=(14.4, 4.6), gridspec_kw={"width_ratios": [1.1, 0.95, 1.1]})
    y = np.arange(len(frame))
    axes[0].barh(y, frame["mean_auc_cNBI"], color=colors, edgecolor="white", height=0.62)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("Mean auc-cNBI")
    axes[0].set_title("Component knockout quality")
    full_auc = float(frame.loc[frame["variant"].eq("full"), "mean_auc_cNBI"].iloc[0])
    axes[0].axvline(full_auc, color="#111827", ls="--", lw=1)
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
    fig.tight_layout(w_pad=3.2)
    fig.savefig(FIG_DIR / "fig24_hast_s_component_knockout.png", dpi=240)
    fig.savefig(FIG_DIR / "fig24_hast_s_component_knockout.pdf")
    plt.close(fig)


def draw_features(feature_mean: pd.DataFrame) -> None:
    labels = {
        "degree": "residual degree",
        "frontier": "frontier",
        "twohop": "two-hop unique",
        "boundary_frac": "boundary fraction",
        "weak_pressure": "weak pressure",
        "bridge_pressure": "bridge pressure",
        "reach": "reach",
        "redundancy": "redundancy",
        "low_frac": "low-neighbor frac.",
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
    ax.set_xlabel("Feature ratio: HAST-Final-S / residual-degree-only")
    ax.set_title("Early removed-node structural profile")
    for yi, v in zip(y, frame["ratio_HAST_over_degree"]):
        ax.text(v + 0.018, yi, f"{v:.2f}x", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig25_hast_s_early_node_features.png", dpi=240)
    fig.savefig(FIG_DIR / "fig25_hast_s_early_node_features.pdf")
    plt.close(fig)


def draw_score_terms(score_terms: pd.DataFrame) -> None:
    frame = score_terms.copy()
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.0), gridspec_kw={"width_ratios": [1.1, 1]})
    y = np.arange(len(frame))
    colors = [COL["full"] if row["term"] == "term_degree" else COL["accent"] if row["mean_signed"] >= 0 else COL["warn"] for _, row in frame.iterrows()]
    axes[0].barh(y, frame["mean_signed"], color=colors, edgecolor="white", height=0.62)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(frame["label"])
    axes[0].invert_yaxis()
    axes[0].axvline(0, color="#111827", lw=1)
    axes[0].set_xlabel("Mean signed score contribution")
    axes[0].set_title("Score terms on selected early nodes")
    for yi, v in zip(y, frame["mean_signed"]):
        axes[0].text(v + (0.08 if v >= 0 else -0.08), yi, f"{v:.2f}", va="center", ha="left" if v >= 0 else "right", fontsize=8)

    axes[1].barh(y, frame["abs_share"] * 100, color=colors, edgecolor="white", height=0.62)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([])
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Absolute contribution share (%)")
    axes[1].set_title("Relative scale of score terms")
    for yi, v in zip(y, frame["abs_share"] * 100):
        axes[1].text(v + 1.0, yi, f"{v:.1f}%", va="center", fontsize=8)
    fig.tight_layout(w_pad=3.0)
    fig.savefig(FIG_DIR / "fig26_hast_s_score_decomposition.png", dpi=240)
    fig.savefig(FIG_DIR / "fig26_hast_s_score_decomposition.pdf")
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

    per_graph.to_csv(OUT_TABLE_DIR / "hast_s_knockout_per_graph.csv", index=False, encoding="utf-8-sig")
    knockout_mean.to_csv(OUT_TABLE_DIR / "hast_s_knockout_mean.csv", index=False, encoding="utf-8-sig")
    features.to_csv(OUT_TABLE_DIR / "hast_s_early_node_features_raw.csv", index=False, encoding="utf-8-sig")
    feature_mean.to_csv(OUT_TABLE_DIR / "hast_s_early_node_features_mean.csv", index=False, encoding="utf-8-sig")
    score_terms.to_csv(OUT_TABLE_DIR / "hast_s_score_decomposition.csv", index=False, encoding="utf-8-sig")
    stages.to_csv(OUT_TABLE_DIR / "hast_s_search_stage_summary.csv", index=False, encoding="utf-8-sig")
    lineage.to_csv(OUT_TABLE_DIR / "hast_s_lineage.csv", index=False, encoding="utf-8-sig")

    draw_knockout(knockout_mean)
    draw_features(feature_mean)
    draw_score_terms(score_terms)

    report = {
        "tables": str(OUT_TABLE_DIR),
        "figures": [
            str(FIG_DIR / "fig24_hast_s_component_knockout.png"),
            str(FIG_DIR / "fig25_hast_s_early_node_features.png"),
            str(FIG_DIR / "fig26_hast_s_score_decomposition.png"),
        ],
        "knockout_mean": knockout_mean.to_dict("records"),
        "stage_summary": stages.to_dict("records"),
        "lineage": lineage.to_dict("records"),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

