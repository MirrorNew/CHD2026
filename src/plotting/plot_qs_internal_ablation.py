# -*- coding: utf-8 -*-
"""HAST-Final-Q/S 算法内部结构消融。

该脚本用显式 knockout 开关重实现两个固定 final 算法的评分和更新组件，
并按完整验证相同的 12 图协议评估每个变体。
"""

from __future__ import annotations

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

OUT_DIR = (
    ROOT
    / "analyze_past_results"
    / "pE3_gcc_failure_analysis_20260528"
    / "final_ablation_interpretability"
    / "internal_qs_ablation"
)

COL = {
    "q": "#D62728",
    "s": "#F2C94C",
    "knock": "#B8C2CC",
    "degree": "#7B8794",
    "good": "#009E73",
    "warn": "#E69F00",
    "bad": "#CC79A7",
    "dark": "#111827",
}


@dataclass(frozen=True)
class Variant:
    name: str
    label: str
    disable_degree_main: bool = False
    disable_neighbor_degree: bool = False
    disable_frontier: bool = False
    disable_boundary: bool = False
    disable_twohop: bool = False
    disable_weak_bridge: bool = False
    disable_leaf_low: bool = False
    disable_redundancy_penalty: bool = False
    fixed_phase: bool = False
    local_refresh_only: bool = False
    degree_only: bool = False


Q_VARIANTS = [
    Variant("full", "full"),
    Variant("no_degree_main", "- residual-degree hub", disable_degree_main=True),
    Variant("no_neighbor_degree", "- neighbor-degree terms", disable_neighbor_degree=True),
    Variant("no_frontier_reach", "- frontier + bounded two-hop", disable_frontier=True, disable_twohop=True),
    Variant("no_boundary_fraction", "- boundary fraction", disable_boundary=True),
    Variant("no_weak_bridge", "- weak-tie + bridge", disable_weak_bridge=True),
    Variant("no_leaf_low", "- leaf/low-degree pressure", disable_leaf_low=True),
    Variant("no_redundancy_penalty", "- redundancy penalty", disable_redundancy_penalty=True),
    Variant("no_phase_schedule", "- phase schedule", fixed_phase=True),
    Variant("local_refresh_only", "- 2-hop local refresh", local_refresh_only=True),
    Variant("degree_only", "residual degree only", degree_only=True),
]

S_VARIANTS = [
    Variant("full", "full"),
    Variant("no_degree_main", "- residual degree", disable_degree_main=True),
    Variant("no_neighbor_degree", "- neighbor-degree terms", disable_neighbor_degree=True),
    Variant("no_frontier", "- frontier", disable_frontier=True),
    Variant("no_boundary", "- boundary", disable_boundary=True),
    Variant("no_twohop", "- bounded two-hop", disable_twohop=True),
    Variant("no_weak_bridge", "- weak-tie + bridge", disable_weak_bridge=True),
    Variant("no_leaf", "- leaf pressure", disable_leaf_low=True),
    Variant("no_redundancy_penalty", "- redundancy penalty", disable_redundancy_penalty=True),
    Variant("no_phase_schedule", "- phase schedule", fixed_phase=True),
    Variant("local_refresh_only", "- 2-hop local refresh", local_refresh_only=True),
    Variant("degree_only", "residual degree only", degree_only=True),
]


def setup() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.4,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.0,
            "legend.fontsize": 7.4,
            "figure.dpi": 180,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.20,
        }
    )


def save(fig: plt.Figure, stem: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{stem}.png"
    fig.savefig(png, facecolor="white")
    fig.savefig(OUT_DIR / f"{stem}.pdf", facecolor="white")
    plt.close(fig)
    return png


def skey(u: Any) -> str:
    return str(u)


def degree_only_order(G: nx.Graph) -> list[Any]:
    import heapq

    H = G.copy()
    order: list[Any] = []
    heap = [(-H.degree[u], skey(u), u) for u in H.nodes()]
    heapq.heapify(heap)
    while H.number_of_nodes():
        while heap:
            neg_d, _key, u = heapq.heappop(heap)
            if u in H and -neg_d == H.degree[u]:
                break
            if u in H:
                heapq.heappush(heap, (-H.degree[u], skey(u), u))
        else:
            u = max(H.nodes(), key=lambda x: (H.degree[x], skey(x)))
        neigh = list(H.neighbors(u)) if u in H else []
        order.append(u)
        H.remove_node(u)
        for v in neigh:
            if v in H:
                heapq.heappush(heap, (-H.degree[v], skey(v), v))
    return order


def q_params(p: float, fixed_phase: bool = False) -> tuple[int, int, int, int, float, float, float, float, float, float, float]:
    if fixed_phase:
        p = 0.25
    if p < 0.04:
        return 30, 5, 20, 18, 1.26, 0.76, 0.78, 0.88, 0.78, 0.92, 0.70
    if p < 0.14:
        return 38, 6, 26, 22, 1.16, 0.94, 0.92, 1.00, 0.86, 1.00, 0.82
    if p < 0.32:
        return 46, 6, 32, 28, 1.04, 1.12, 1.08, 1.12, 0.96, 1.08, 0.96
    if p < 0.56:
        return 54, 6, 38, 32, 0.94, 1.26, 1.24, 1.22, 1.08, 1.18, 1.10
    if p < 0.78:
        return 60, 7, 34, 30, 0.86, 1.18, 1.38, 1.30, 1.20, 1.26, 1.22
    return 64, 7, 30, 28, 0.78, 1.02, 1.48, 1.20, 1.30, 1.34, 1.34


def q_order_variant(G: nx.Graph, variant: Variant) -> list[Any]:
    import heapq

    if variant.degree_only:
        return degree_only_order(G)
    H = G.copy()
    n0 = H.number_of_nodes()
    if n0 == 0:
        return []
    deg = dict(H.degree())
    heap: list[tuple[Any, ...]] = []
    stamp: dict[Any, int] = {}
    tick = 0

    def score(u: Any) -> tuple[float, float, float, float, float, float, float, float, str]:
        su = skey(u)
        d = deg.get(u, 0)
        if d <= 0:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, su)
        p = 1.0 - float(H.number_of_nodes()) / float(n0)
        ncap, scap, _acap, _tcap, hub_w, front_w, bound_w, weak_w, leaf_w, bridge_w, red_w = q_params(
            p, variant.fixed_phase
        )
        neigh_all = list(H.neighbors(u))
        if len(neigh_all) > ncap:
            neigh = neigh_all[:ncap]
            scale = float(d) / float(ncap)
        else:
            neigh = neigh_all
            scale = 1.0

        ns = set(neigh)
        nd_sum = max_nd = weak = 0.0
        leaf_n = low_n = low4_n = boundary = twohop = outward_max = bridge_cnt = internal_hits = sampled_pairs = 0
        seen2: set[Any] = set()
        for v in neigh:
            dv = deg.get(v, 0)
            nd_sum += dv
            max_nd = max(max_nd, float(dv))
            leaf_n += int(dv <= 1)
            low_n += int(dv <= 3)
            low4_n += int(dv <= 4)
            inv = outv = c = 0
            for w in H.neighbors(v):
                if w == u:
                    continue
                if w in ns:
                    inv += 1
                else:
                    outv += 1
                    boundary += 1
                    if w not in seen2:
                        seen2.add(w)
                        twohop += 1
                c += 1
                if c >= scap:
                    break
            internal_hits += inv
            sampled_pairs += c
            outward_max = max(outward_max, outv)
            bridge_cnt += int(outv >= inv + 1)
            weak += float(outv + 1) / float(dv + 1)

        sn = float(len(neigh)) if neigh else 1.0
        frontier = scale * boundary
        reach = scale * twohop
        avg_nd = nd_sum / sn
        boundary_frac = boundary / float(boundary + internal_hits + 1)
        redundancy = internal_hits / float(sampled_pairs + 1)
        weak_tie = scale * weak
        leaf_frac = leaf_n / sn
        low_frac = low_n / sn
        low4_frac = low4_n / sn
        bridge_pressure = scale * (bridge_cnt + 0.35 * outward_max)
        assort_pen = avg_nd / float(d + avg_nd + 1.0)
        pendant_pressure = leaf_n + 0.45 * low_n + 0.20 * low4_n

        hub = 0.0 if variant.disable_degree_main else math.log1p(d) * math.sqrt(d)
        nd_term = 0.0 if variant.disable_neighbor_degree else math.log1p(nd_sum * scale)
        max_nd_term = 0.0 if variant.disable_neighbor_degree else math.log1p(max_nd)
        assort_term = 0.0 if variant.disable_neighbor_degree else assort_pen
        front_term = 0.0 if variant.disable_frontier else math.log1p(frontier + (0.0 if variant.disable_twohop else 1.5 * reach))
        bound_term = 0.0 if variant.disable_boundary else d * boundary_frac
        weak_term = 0.0 if variant.disable_weak_bridge else math.log1p(weak_tie)
        bridge_term = 0.0 if variant.disable_weak_bridge else math.log1p(bridge_pressure + 1.0) * math.sqrt(d)
        leaf_term = 0.0 if variant.disable_leaf_low else pendant_pressure
        low_penalty = 0.0 if variant.disable_leaf_low else (0.13 * low_frac + 0.08 * low4_frac + 0.06 * leaf_frac)
        red_penalty = 0.0 if variant.disable_redundancy_penalty else red_w * 1.55 * redundancy * math.sqrt(d)
        val = (
            hub_w * hub
            + 0.30 * nd_term
            + front_w * front_term
            + bound_w * bound_term
            + weak_w * weak_term
            + bridge_w * bridge_term
            + leaf_w * leaf_term
            + 0.20 * max_nd_term
            - red_penalty
            - low_penalty
            - 0.16 * assort_term
        )
        return (float(val), float(d), float(frontier), float(bridge_pressure), float(reach), -float(redundancy), float(boundary_frac), float(max_nd), su)

    def push(u: Any) -> None:
        nonlocal tick
        if u not in deg:
            return
        tick += 1
        stamp[u] = tick
        k = score(u)
        heapq.heappush(heap, (-k[0], -k[1], -k[2], -k[3], -k[4], -k[5], -k[6], -k[7], k[8], tick, u))

    for u in list(H.nodes()):
        push(u)
    order: list[Any] = []
    while deg:
        retries = 0
        chosen = None
        while heap:
            item = heapq.heappop(heap)
            t, u = item[9], item[10]
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
            chosen = max(deg, key=lambda x: (deg[x], skey(x)))
        u = chosen
        if u not in deg:
            continue
        affected = set()
        if u in H:
            neigh = list(H.neighbors(u))
            affected.update(neigh)
            if not variant.local_refresh_only:
                p = 1.0 - float(H.number_of_nodes()) / float(n0)
                _ncap, scap, acap, tcap, *_ = q_params(p, variant.fixed_phase)
                added = 0
                for v in neigh[:acap]:
                    c = 0
                    for w in H.neighbors(v):
                        if w != u:
                            affected.add(w)
                            added += 1
                        c += 1
                        if c >= scap or added >= tcap:
                            break
                    if added >= tcap:
                        break
        order.append(u)
        H.remove_node(u)
        deg.pop(u, None)
        for v in affected:
            if v in H:
                deg[v] = H.degree[v]
                push(v)
    return order


def s_order_variant(G: nx.Graph, variant: Variant) -> list[Any]:
    import heapq

    if variant.degree_only:
        return degree_only_order(G)
    n0 = G.number_of_nodes()
    if n0 == 0:
        return []
    adj = {u: list(G[u]) for u in G.nodes()}
    active = set(adj)
    deg = {u: len(adj[u]) for u in adj}
    order: list[Any] = []
    heap: list[tuple[Any, ...]] = []
    version: dict[Any, int] = {}
    counter = 0
    neigh_cap_lo, neigh_cap_mid, neigh_cap_hi = 12, 16, 24
    two_cap_early, two_cap_mid, two_cap_late = 6, 8, 8
    affect_neigh_cap, affect_per_neigh_cap, affect_two_cap = 6, 3, 18

    def score(u: Any) -> tuple[float, float, float, float, float, float, str]:
        d = deg.get(u, 0)
        fd = float(d)
        key = skey(u)
        if d <= 0:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, key)
        p = 0.20 if variant.fixed_phase else len(order) / float(n0)
        ncap = neigh_cap_lo if d <= 18 else neigh_cap_mid if d <= 64 else neigh_cap_hi
        neigh = []
        sum_nd = max_nd = leaf = 0.0
        for v in adj[u]:
            if v in active:
                dv = deg.get(v, 0)
                neigh.append(v)
                sum_nd += float(dv)
                max_nd = max(max_nd, float(dv))
                leaf += float(dv <= 1)
                if len(neigh) >= ncap:
                    break
        cnt = len(neigh)
        if cnt == 0:
            return (fd, fd, 0.0, 0.0, 0.0, 0.0, key)
        if p < 0.25:
            tcap, per_v_cap, w_deg, w_front, w_weak, w_bound, w_red, w_leaf, w_bridge, w_two = (
                two_cap_early,
                2,
                1.15,
                0.32,
                0.58,
                0.70,
                -0.50,
                0.045,
                0.62,
                0.046,
            )
        elif p < 0.62:
            tcap, per_v_cap, w_deg, w_front, w_weak, w_bound, w_red, w_leaf, w_bridge, w_two = (
                two_cap_mid,
                3,
                1.02,
                0.58,
                0.92,
                1.04,
                -0.76,
                0.078,
                1.00,
                0.070,
            )
        else:
            tcap, per_v_cap, w_deg, w_front, w_weak, w_bound, w_red, w_leaf, w_bridge, w_two = (
                two_cap_late,
                3,
                0.91,
                0.50,
                0.98,
                1.23,
                -0.90,
                0.070,
                1.12,
                0.058,
            )
        neigh_set = set(neigh)
        frontier = weak = boundary = redundancy = bridge = two_front = 0.0
        seen2: set[Any] = set()
        two_seen_count = 0
        for v in neigh:
            dv = deg.get(v, 0)
            internal = sampled2 = external = 0
            for w in adj[v]:
                if w not in active or w == u:
                    continue
                if w in neigh_set:
                    internal += 1
                else:
                    external += 1
                    if two_seen_count < tcap and sampled2 < per_v_cap:
                        if w not in seen2:
                            seen2.add(w)
                            two_seen_count += 1
                            two_front += math.sqrt(float(deg.get(w, 0) + 1))
                        sampled2 += 1
                if sampled2 >= per_v_cap and internal > 1 and (external >= 2 or two_seen_count >= tcap):
                    break
            redundancy += float(internal)
            frontier += float(external > 0)
            weak += float(dv <= 2 or external >= max(1, dv - internal - 1))
            boundary += float(internal <= 1 and external > 0)
            if internal == 0 and external > 0:
                bridge += 1.0
            elif external > internal + 1:
                bridge += 0.5
        avg_nd = sum_nd / float(cnt)
        droot = math.sqrt(fd)
        red_norm = redundancy / float(cnt)
        leaf_pressure = leaf / float(cnt)
        cut_pressure = (frontier + boundary + weak) / float(1 + cnt)
        val = (
            (0.0 if variant.disable_degree_main else w_deg * fd)
            + (0.0 if variant.disable_frontier else w_front * frontier)
            + (0.0 if variant.disable_weak_bridge else w_weak * weak)
            + (0.0 if variant.disable_boundary else w_bound * boundary)
            + (0.0 if variant.disable_redundancy_penalty else w_red * red_norm * droot)
            + (0.0 if variant.disable_leaf_low else w_leaf * leaf_pressure * droot)
            + (0.0 if variant.disable_weak_bridge else w_bridge * bridge * droot)
            + (0.0 if variant.disable_twohop else w_two * two_front)
            + (0.0 if variant.disable_neighbor_degree else 0.010 * avg_nd)
            - (0.0 if variant.disable_neighbor_degree else 0.015 * max_nd)
            + 0.052 * cut_pressure
        )
        return (float(val), fd, float(frontier), float(boundary), float(weak), float(bridge), key)

    def push(u: Any) -> None:
        nonlocal counter
        if u not in active:
            return
        s = score(u)
        counter += 1
        version[u] = counter
        heapq.heappush(heap, (-s[0], -s[1], -s[2], -s[3], -s[4], -s[5], s[6], counter, u))

    for u in list(active):
        push(u)
    while active:
        while heap:
            a, b, c, dkey, e, f, k, st, u = heapq.heappop(heap)
            if u not in active or version.get(u) != st:
                continue
            s = score(u)
            cur = (-s[0], -s[1], -s[2], -s[3], -s[4], -s[5], s[6])
            if cur == (a, b, c, dkey, e, f, k):
                break
            push(u)
        else:
            u = max(active, key=lambda x: (deg.get(x, 0), skey(x)))
        if u not in active:
            continue
        neigh = [v for v in adj[u] if v in active]
        affected = set(neigh)
        if not variant.local_refresh_only:
            added = sampled = 0
            for v in neigh:
                if sampled >= affect_neigh_cap or added >= affect_two_cap:
                    break
                sampled += 1
                cnt = 0
                for w in adj[v]:
                    if w in active and w != u:
                        affected.add(w)
                        added += 1
                        cnt += 1
                        if cnt >= affect_per_neigh_cap or added >= affect_two_cap:
                            break
        order.append(u)
        active.remove(u)
        deg[u] = 0
        for v in neigh:
            deg[v] -= 1
        for v in affected:
            if v in active:
                push(v)
    return order


def critical_ratio(points: pd.DataFrame, threshold: float) -> tuple[float, bool]:
    hit = points[pd.to_numeric(points["GCC"], errors="coerce") <= threshold]
    if hit.empty:
        return (float(points["removal_ratio"].max()) if len(points) else float("nan"), False)
    return (float(hit.iloc[0]["removal_ratio"]), True)


def evaluate_all(force: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_path = OUT_DIR / "internal_ablation_per_graph_metrics.csv"
    mean_path = OUT_DIR / "internal_ablation_mean_metrics.csv"
    ct_path = OUT_DIR / "internal_ablation_critical_thresholds.csv"
    if not force and per_path.exists() and mean_path.exists() and ct_path.exists():
        return (
            pd.read_csv(per_path, encoding="utf-8-sig"),
            pd.read_csv(mean_path, encoding="utf-8-sig"),
            pd.read_csv(ct_path, encoding="utf-8-sig"),
        )
    graph_cache = {dataset: read_graph(dataset) for dataset in DATASETS}
    per_rows: list[dict[str, Any]] = []
    ct_rows: list[dict[str, Any]] = []
    for algorithm, variants, runner in [
        ("HAST-Final-Q", Q_VARIANTS, q_order_variant),
        ("HAST-Final-S", S_VARIANTS, s_order_variant),
    ]:
        for variant in variants:
            print(f"[internal-ablation] {algorithm} {variant.name}", flush=True)
            for dataset, graph in graph_cache.items():
                rate = DATASET_RATES.get(dataset, 0.30)
                t0 = time.perf_counter()
                order = runner(graph, variant)
                elapsed = time.perf_counter() - t0
                points = compute_metrics(graph, order, rate=rate, method_time=elapsed)
                summary = summarize_metrics(points)
                row = {
                    "algorithm": algorithm,
                    "variant": variant.name,
                    "label": variant.label,
                    "dataset": dataset,
                    **summary,
                }
                per_rows.append(row)
                for threshold in [0.10, 0.05, 0.01]:
                    value, reached = critical_ratio(points, threshold)
                    ct_rows.append(
                        {
                            "algorithm": algorithm,
                            "variant": variant.name,
                            "label": variant.label,
                            "dataset": dataset,
                            "threshold": threshold,
                            "critical_removal_ratio": value,
                            "reached": reached,
                        }
                    )
    per = pd.DataFrame(per_rows)
    mean = (
        per.groupby(["algorithm", "variant", "label"], as_index=False)
        .agg(
            mean_R=("R", "mean"),
            mean_auc_cNBI=("auc_cNBI", "mean"),
            mean_time_s=("time_s", "mean"),
            median_time_s=("time_s", "median"),
            datasets=("dataset", "count"),
        )
    )
    full_lookup = mean[mean["variant"].eq("full")].set_index("algorithm")
    mean["delta_R_vs_full"] = mean.apply(lambda r: r["mean_R"] - float(full_lookup.loc[r["algorithm"], "mean_R"]), axis=1)
    mean["delta_auc_vs_full"] = mean.apply(
        lambda r: r["mean_auc_cNBI"] - float(full_lookup.loc[r["algorithm"], "mean_auc_cNBI"]), axis=1
    )
    mean["time_ratio_vs_full"] = mean.apply(
        lambda r: r["mean_time_s"] / max(float(full_lookup.loc[r["algorithm"], "mean_time_s"]), 1e-9), axis=1
    )
    ct = pd.DataFrame(ct_rows)
    ct_summary = (
        ct.groupby(["algorithm", "variant", "label", "threshold"], as_index=False)
        .agg(mean_critical_ratio=("critical_removal_ratio", "mean"), reached_rate=("reached", "mean"))
    )
    per.to_csv(per_path, index=False, encoding="utf-8-sig")
    mean.to_csv(mean_path, index=False, encoding="utf-8-sig")
    ct_summary.to_csv(ct_path, index=False, encoding="utf-8-sig")
    ct.to_csv(OUT_DIR / "internal_ablation_critical_threshold_values.csv", index=False, encoding="utf-8-sig")
    return per, mean, ct_summary


def plot_impact(mean: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.0), sharex=False, sharey=False)
    for ax, algorithm, variants, color in [
        (axes[0], "HAST-Final-Q", Q_VARIANTS, COL["q"]),
        (axes[1], "HAST-Final-S", S_VARIANTS, COL["s"]),
    ]:
        order = [v.name for v in variants if v.name != "full"]
        sub = mean[mean["algorithm"].eq(algorithm)].set_index("variant").reindex(order).reset_index()
        y = np.arange(len(sub))
        bar_colors = [COL["degree"] if x == "degree_only" else COL["knock"] for x in sub["variant"]]
        ax.barh(y, sub["delta_R_vs_full"], color=bar_colors, edgecolor="white", height=0.62)
        ax.axvline(0, color=COL["dark"], lw=0.9)
        ax.set_yticks(y)
        ax.set_yticklabels(sub["label"])
        ax.invert_yaxis()
        ax.set_xlabel("Delta mean R after knockout (positive = worse)")
        ax.set_title(f"{algorithm}: GCC robustness contribution")
        for yi, val in zip(y, sub["delta_R_vs_full"]):
            ax.text(val + (0.001 if val >= 0 else -0.001), yi, f"{val:+.4f}", va="center", ha="left" if val >= 0 else "right", fontsize=7.2)
        ax.text(0.98, 0.03, "full color: " + ("red Q" if algorithm.endswith("Q") else "yellow S"), transform=ax.transAxes, ha="right", fontsize=7, color=color)
    fig.suptitle("Internal ablation: contribution of each HAST-Final-Q/S structure", fontsize=12, fontweight="bold")
    return save(fig, "figE_internal_ablation_delta_R")


def plot_multi_metric(mean: pd.DataFrame, ct: pd.DataFrame) -> Path:
    ct10 = ct[ct["threshold"].eq(0.10)][["algorithm", "variant", "mean_critical_ratio", "reached_rate"]]
    data = mean.merge(ct10, on=["algorithm", "variant"], how="left")
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 7.2))
    axes = axes.ravel()
    metrics = [
        ("mean_R", "Mean R (lower better)", False),
        ("mean_auc_cNBI", "Mean auc-cNBI (higher better)", True),
        ("mean_critical_ratio", "CT@0.10 removal ratio (lower better)", False),
        ("mean_time_s", "Runtime / graph (s, lower better)", False),
    ]
    for ax, (metric, ylabel, higher) in zip(axes, metrics):
        frames = []
        labels = []
        colors = []
        for algorithm, variants, color in [("HAST-Final-Q", Q_VARIANTS, COL["q"]), ("HAST-Final-S", S_VARIANTS, COL["s"])]:
            order = [v.name for v in variants]
            sub = data[data["algorithm"].eq(algorithm)].set_index("variant").reindex(order)
            full = float(sub.loc["full", metric])
            impact = sub[metric] - full
            if higher:
                impact = -impact
            frames.extend(impact.tolist())
            labels.extend([f"{algorithm[-1]}:{v.label}" for v in variants])
            colors.extend([color if v.name == "full" else COL["knock"] if v.name != "degree_only" else COL["degree"] for v in variants])
        y = np.arange(len(labels))
        ax.barh(y, frames, color=colors, edgecolor="white", height=0.56)
        ax.axvline(0, color=COL["dark"], lw=0.8)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=6.5)
        ax.invert_yaxis()
        ax.set_xlabel("Worse-than-full impact" if metric != "mean_time_s" else "Runtime change vs full")
        ax.set_title(ylabel)
    fig.suptitle("Internal ablation across R, cNBI, critical threshold, and runtime", fontsize=12, fontweight="bold")
    return save(fig, "figF_internal_ablation_multi_metric")


def plot_ct_heatmap(ct: pd.DataFrame) -> Path:
    rows = []
    for algorithm, variants in [("HAST-Final-Q", Q_VARIANTS), ("HAST-Final-S", S_VARIANTS)]:
        for variant in variants:
            label = f"{algorithm[-1]}: {variant.label}"
            sub = ct[(ct["algorithm"].eq(algorithm)) & (ct["variant"].eq(variant.name))]
            row = {"label": label}
            for th in [0.10, 0.05, 0.01]:
                row[f"CT@{th:g}"] = float(sub[sub["threshold"].eq(th)]["mean_critical_ratio"].iloc[0])
            rows.append(row)
    frame = pd.DataFrame(rows).set_index("label")
    fig, ax = plt.subplots(figsize=(6.9, 7.0))
    vals = frame.to_numpy()
    im = ax.imshow(vals, cmap="YlGnBu_r", aspect="auto")
    ax.set_xticks(np.arange(frame.shape[1]))
    ax.set_xticklabels(frame.columns)
    ax.set_yticks(np.arange(frame.shape[0]))
    ax.set_yticklabels(frame.index, fontsize=7)
    for i in range(frame.shape[0]):
        for j in range(frame.shape[1]):
            ax.text(j, i, f"{vals[i, j]:.3f}", ha="center", va="center", fontsize=6.7)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title("Critical-threshold sensitivity by internal structure")
    return save(fig, "figG_internal_ablation_critical_threshold_heatmap")


def write_report(mean: pd.DataFrame, ct: pd.DataFrame, paths: list[Path]) -> None:
    lines = [
        "# HAST-Final-Q/S internal structure ablation",
        "",
        "Each row is a controlled knockout of one structure from the current pE4 final algorithms, evaluated on the same 12 benchmark graphs.",
        "",
        "## Most important structures by mean R degradation",
        "",
    ]
    for algorithm in ["HAST-Final-Q", "HAST-Final-S"]:
        sub = mean[(mean["algorithm"].eq(algorithm)) & (~mean["variant"].eq("full"))].sort_values("delta_R_vs_full", ascending=False)
        lines.append(f"### {algorithm}")
        lines.append("")
        lines.append(sub[["label", "delta_R_vs_full", "delta_auc_vs_full", "time_ratio_vs_full"]].head(6).to_markdown(index=False))
        lines.append("")
    lines.extend(["## Generated figures", ""])
    for path in paths:
        lines.append(f"- {path.name}")
    (OUT_DIR / "internal_ablation_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    setup()
    force = "--force" in sys.argv
    _per, mean, ct = evaluate_all(force=force)
    paths = [plot_impact(mean), plot_multi_metric(mean, ct), plot_ct_heatmap(ct)]
    write_report(mean, ct, paths)
    for path in paths:
        print(path)
    print(OUT_DIR / "internal_ablation_report.md")


if __name__ == "__main__":
    main()
