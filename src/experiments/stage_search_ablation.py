# -*- coding: utf-8 -*-
"""第 5.3 节 CHD 阶段搜索消融分析与小预算实验入口。"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from experiments.full_validation import FullValidationConfig, evaluate_full_validation, load_candidate_file
from model.candidate import CandidateProgram, extract_code, make_program
from model.config import DATASET_RATES, PROJECT_ROOT, RUNS_ROOT, STAGE1_WEIGHTS, STAGE3_WEIGHTS
from model.data import read_graph
from model.stage1_stage3_search import (
    HDA_ROOT_CODE,
    StageSearchConfig,
    benchmark_context_text,
    build_stage1_prompt,
    default_config,
    ensure_dirs,
    evaluate_candidate_with_timeout,
    evaluate_root,
    generate_and_evaluate_tree_stage,
    invalid_row,
    read_benchmark_context,
    refresh_generated_scores,
    request_llm_one,
    select_stage3_seed_nodes,
    stage3_branch_for_index,
    truncate_text,
)
from model.llm import OpenAICompatibleLLMProvider
from model.ranking import pareto_frontier


MAIN_RUN = RUNS_ROOT / "runs_HAST_root_target_family_full_ritelt_20260525"
BENCHMARK = PROJECT_ROOT / "artifacts" / "source_tables" / "benchmark_12graph"
FIG_DIR = PROJECT_ROOT / "artifacts" / "figures"
SOURCE_DIR = PROJECT_ROOT / "artifacts" / "source_tables" / "stage_search_ablation"
FULL_DATASETS = [
    "CEnew",
    "Collaboration",
    "condmat",
    "crime",
    "email",
    "Grid",
    "GrQC",
    "hamster",
    "HepPh",
    "PH",
    "Yeast",
    "Powerlaw_500",
]

COL = {
    "stage1": "#56B4E9",
    "stage3": "#0072B2",
    "mean": "#009E73",
    "free": "#D55E00",
    "gray": "#9CA3AF",
    "text": "#111827",
    "grid": "#D1D5DB",
}


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def setup_plot() -> None:
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


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def rank01(series: pd.Series, higher_is_better: bool) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    mask = values.notna()
    out = pd.Series(0.0, index=series.index)
    if int(mask.sum()) <= 1:
        out.loc[mask] = 1.0
        return out
    ranked = values.loc[mask].rank(method="average", ascending=not higher_is_better)
    out.loc[mask] = 1.0 - (ranked - 1.0) / (len(ranked) - 1.0)
    return out


def add_section53_rank_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    valid = out["valid"].map(boolish) if "valid" in out else pd.Series(True, index=out.index)
    out["rank53_auc"] = 0.0
    out["rank53_R"] = 0.0
    out["rank53_time"] = 0.0
    out["rank_score_53"] = 0.0
    if valid.any():
        idx = out.index[valid]
        out.loc[idx, "rank53_auc"] = rank01(out.loc[idx, "auc_cNBI"], True)
        out.loc[idx, "rank53_R"] = rank01(out.loc[idx, "R"], False)
        out.loc[idx, "rank53_time"] = rank01(out.loc[idx, "time_s"], False)
        out.loc[idx, "rank_score_53"] = 100.0 * (
            0.4 * out.loc[idx, "rank53_auc"]
            + 0.3 * out.loc[idx, "rank53_R"]
            + 0.3 * out.loc[idx, "rank53_time"]
        )
    return out


def load_stage_candidates(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    stage1 = pd.read_csv(run_dir / "stage1_candidate_log.csv", encoding="utf-8-sig")
    stage3 = pd.read_csv(run_dir / "stage3_candidate_log.csv", encoding="utf-8-sig")
    stage1["pool"] = "HAST-free search"
    stage3["pool"] = "HAST bounded search"
    return add_section53_rank_score(stage1), add_section53_rank_score(stage3)


def powerlaw_thresholds() -> dict[str, float]:
    per_graph = pd.read_csv(BENCHMARK / "per_graph_metrics.csv", encoding="utf-8-sig")
    powerlaw = per_graph[per_graph["dataset"].eq("Powerlaw_500")]
    out: dict[str, float] = {}
    for label, candidates in {
        "HDA": ["HDA"],
        "AlphaEvolve-like": ["AlphaEvolve-like"],
        "ERA-like": ["ERA-like", "PUCT"],
    }.items():
        row = powerlaw[powerlaw["method"].isin(candidates)]
        if not row.empty:
            out[label] = float(row.iloc[0]["auc_cNBI"])
    return out


def method_mean_thresholds() -> dict[str, float]:
    means = pd.read_csv(BENCHMARK / "method_mean_metrics.csv", encoding="utf-8-sig")
    out: dict[str, float] = {}
    for label, candidates in {
        "HDA": ["HDA"],
        "AlphaEvolve-like": ["AlphaEvolve-like"],
        "ERA-like": ["ERA-like", "PUCT"],
    }.items():
        row = means[means["method"].isin(candidates)]
        if not row.empty:
            out[label] = float(row.iloc[0]["mean_auc_cNBI"])
    return out


def summarize_pool(df: pd.DataFrame, setting: str, budget: str, thresholds: dict[str, float]) -> dict[str, Any]:
    valid = df[df["valid"].map(boolish)].copy()
    top_auc = valid.sort_values("auc_cNBI", ascending=False).head(10)
    top_rank = valid.sort_values("rank_score_53", ascending=False).head(10)
    frontier = pareto_frontier(valid.to_dict("records"))
    return {
        "group": "Full HAST" if setting.startswith("HAST") else "Offline analysis",
        "setting": setting,
        "budget": budget,
        "valid_rate": float(len(valid) / max(1, len(df))),
        "valid_candidates": int(len(valid)),
        "best_proxy_auc_cNBI": float(valid["auc_cNBI"].max()) if len(valid) else float("nan"),
        "proxy_top10_auc_mean": float(top_auc["auc_cNBI"].mean()) if len(top_auc) else float("nan"),
        "proxy_top10_rank_score_mean": float(top_rank["rank_score_53"].mean()) if len(top_rank) else float("nan"),
        "proxy_pareto_size": int(len(frontier)),
        "mean_proxy_time_s": float(valid["time_s"].mean()) if len(valid) else float("nan"),
        "mean_llm_elapsed_s": float(pd.to_numeric(valid.get("llm_elapsed_s", pd.Series(dtype=float)), errors="coerce").mean()) if len(valid) else float("nan"),
        "# > AlphaEvolve": int((valid["auc_cNBI"] > thresholds.get("AlphaEvolve-like", float("inf"))).sum()),
        "# > ERA-like": int((valid["auc_cNBI"] > thresholds.get("ERA-like", float("inf"))).sum()),
        "hit_rate_alpha": float((valid["auc_cNBI"] > thresholds.get("AlphaEvolve-like", float("inf"))).mean()) if len(valid) else 0.0,
        "hit_rate_era": float((valid["auc_cNBI"] > thresholds.get("ERA-like", float("inf"))).mean()) if len(valid) else 0.0,
    }


def select_top_candidates(
    stage1: pd.DataFrame,
    stage3: pd.DataFrame,
    top_k: int,
    extra_pools: list[tuple[str, pd.DataFrame]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selections: list[dict[str, Any]] = []

    def take(df: pd.DataFrame, setting: str, criterion: str, sort_col: str, ascending: bool = False) -> None:
        valid = df[df["valid"].map(boolish)].sort_values(sort_col, ascending=ascending).head(top_k)
        for rank, row in enumerate(valid.to_dict("records"), start=1):
            selections.append(
                {
                    "setting": setting,
                    "criterion": criterion,
                    "selection_rank": rank,
                    "candidate_id": row["candidate_id"],
                    "node_id": row.get("node_id", ""),
                    "source_stage": row.get("source_stage", ""),
                    "code_path": row.get("code_path", ""),
                }
            )

    take(stage1, "Stage 1 free search", "proxy auc-cNBI top10", "auc_cNBI")
    take(stage1, "Stage 1 free search", "proxy rank_score top10", "rank_score_53")
    take(stage3, "Stage 3 bounded search", "proxy auc-cNBI top10", "auc_cNBI")
    take(stage3, "Stage 3 bounded search", "proxy rank_score top10", "rank_score_53")
    for setting, frame in extra_pools or []:
        if frame.empty:
            continue
        take(frame, setting, "proxy auc-cNBI top10", "auc_cNBI")
        take(frame, setting, "proxy rank_score top10", "rank_score_53")

    for name, sort_cols in {
        "raw proxy score": ["auc_cNBI"],
        "parent-relative delta": ["delta_auc_cNBI"],
        "root-relative delta": ["delta_root_auc_cNBI"],
        "quality-only selection": ["auc_cNBI"],
        "quality+R selection": ["auc_cNBI", "R"],
        "quality+R+time Pareto": ["rank_score_53"],
    }.items():
        frame = stage3[stage3["valid"].map(boolish)].copy()
        if sort_cols == ["auc_cNBI", "R"]:
            frame = frame.sort_values(["auc_cNBI", "R"], ascending=[False, True]).head(top_k)
        elif sort_cols == ["rank_score_53"]:
            frontier_ids = {str(row["candidate_id"]) for row in pareto_frontier(frame.to_dict("records"))}
            frame = frame[frame["candidate_id"].astype(str).isin(frontier_ids)].sort_values("rank_score_53", ascending=False).head(top_k)
        else:
            frame = frame.sort_values(sort_cols[0], ascending=False).head(top_k)
        for rank, row in enumerate(frame.to_dict("records"), start=1):
            selections.append(
                {
                    "setting": name,
                    "criterion": f"{name} top10",
                    "selection_rank": rank,
                    "candidate_id": row["candidate_id"],
                    "node_id": row.get("node_id", ""),
                    "source_stage": row.get("source_stage", ""),
                    "code_path": row.get("code_path", ""),
                }
            )

    membership = pd.DataFrame(selections)
    unique = (
        membership.drop_duplicates(subset=["candidate_id"], keep="first")
        .sort_values(["source_stage", "candidate_id"])
        .reset_index(drop=True)
    )
    unique["method_name"] = [f"A53-{i:03d}-{str(cid)[:8]}" for i, cid in enumerate(unique["candidate_id"], start=1)]
    membership = membership.merge(unique[["candidate_id", "method_name"]], on="candidate_id", how="left")
    return membership, unique


def run_top_candidate_full_validation(run_dir: Path, unique: pd.DataFrame, out_dir: Path, timeout_s: float) -> Path:
    validation_dir = out_dir / "top_candidates_full_validation"
    method_mean = validation_dir / "method_mean_metrics.csv"
    if method_mean.exists():
        return validation_dir
    programs: list[CandidateProgram] = []
    names: list[str] = []
    for row in unique.to_dict("records"):
        code_path = Path(str(row["code_path"]))
        if not code_path.exists():
            continue
        programs.append(load_candidate_file(code_path, family="HAST-5.3-top", source_stage=str(row["method_name"])))
        names.append(str(row["method_name"]))
    if not programs:
        raise RuntimeError("No top candidates with existing code_path were selected.")
    config = FullValidationConfig(
        output_dir=validation_dir,
        datasets=FULL_DATASETS,
        method_names=names,
        source="chd_5_3_proxy_selected_full_validation",
        group="HAST-5.3-ablation",
        evidence_tier="proxy_selected_top10",
        candidate_timeout_s=timeout_s,
        selection_source="section_5_3_proxy_selection_no_reselection",
    )
    evaluate_full_validation(config, programs)
    return validation_dir


def aggregate_full_validation_memberships(membership: pd.DataFrame, unique: pd.DataFrame, validation_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    method_mean_path = validation_dir / "method_mean_metrics.csv"
    if not method_mean_path.exists():
        return pd.DataFrame(), pd.DataFrame()
    method_mean = pd.read_csv(method_mean_path, encoding="utf-8-sig")
    method_mean = method_mean.merge(unique[["candidate_id", "method_name"]], left_on="method", right_on="method_name", how="left", suffixes=("", "_selected"))
    method_mean = method_mean.rename(columns={"candidate_id_selected": "selected_candidate_id"})
    method_mean = add_section53_rank_score(
        method_mean.rename(columns={"mean_auc_cNBI": "auc_cNBI", "mean_R": "R", "mean_time_s": "time_s"}).assign(valid=True)
    ).rename(columns={"auc_cNBI": "mean_auc_cNBI", "R": "mean_R", "time_s": "mean_time_s"})
    joined = membership.merge(
        method_mean[["method", "method_name", "mean_auc_cNBI", "mean_R", "mean_time_s", "rank_score_53"]],
        on="method_name",
        how="left",
    )
    agg = (
        joined.groupby(["setting", "criterion"], as_index=False)
        .agg(
            selected_candidates=("candidate_id", "nunique"),
            full_validation_top10_mean_auc_cNBI=("mean_auc_cNBI", "mean"),
            full_validation_top10_mean_R=("mean_R", "mean"),
            full_validation_top10_mean_time_s=("mean_time_s", "mean"),
            full_validation_top10_rank_score=("rank_score_53", "mean"),
        )
        .sort_values(["setting", "criterion"])
    )
    return joined, agg


def draw_ablation_figure(stage1: pd.DataFrame, stage3: pd.DataFrame, out_path: Path, extra_pools: list[tuple[str, pd.DataFrame]] | None = None) -> None:
    setup_plot()
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.35))
    pools = [
        ("HAST-free search", stage1, COL["stage1"]),
        ("HAST bounded search", stage3, COL["stage3"]),
    ] + [(name, frame, color) for (name, frame), color in zip(extra_pools or [], ["#CC79A7", COL["free"], "#E69F00"])]
    for label, df, color in pools:
        if df.empty:
            continue
        valid = df[df["valid"].map(boolish)].sort_values("stage_index")
        axes[0].plot(valid["stage_index"], valid["auc_cNBI"].cummax(), label=label, color=color, lw=1.8)
    axes[0].set_xlabel("Candidate count")
    axes[0].set_ylabel("Best-so-far proxy auc-cNBI")
    axes[0].set_title("Proxy quality accumulation")

    for label, df, color in pools:
        if df.empty:
            continue
        valid = df[df["valid"].map(boolish)].sort_values("stage_index")
        axes[1].plot(valid["stage_index"], valid["rank_score_53"].cummax(), label=label, color=color, lw=1.8)
    axes[1].set_xlabel("Candidate count")
    axes[1].set_ylabel("Best-so-far proxy rank_score")
    axes[1].set_title("Composite proxy rank")

    rows = []
    for label, df, _color in pools:
        if df.empty:
            continue
        valid = df[df["valid"].map(boolish)].copy()
        rows.append(
            {
                "setting": label,
                "valid_rate": len(valid) / max(1, len(df)),
                "pareto_density": len(pareto_frontier(valid.to_dict("records"))) / max(1, len(valid)),
            }
        )
    bars = pd.DataFrame(rows)
    x = np.arange(len(bars))
    width = 0.34
    axes[2].bar(x - width / 2, bars["valid_rate"], width, label="valid rate", color="#009E73")
    axes[2].bar(x + width / 2, bars["pareto_density"], width, label="Pareto density", color="#E69F00")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels([str(v).replace("HAST ", "").replace(" search", "") for v in bars["setting"]], rotation=18, ha="right")
    axes[2].set_ylim(0, 1.05)
    axes[2].set_title("Search reliability")
    axes[2].legend(frameon=False)
    for ax in axes[:2]:
        ax.legend(frameon=False)
    fig.suptitle("Fig. 5.3 CHD stage-search ablation on Powerlaw_500 proxy", y=1.03, fontweight="bold")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path.with_suffix(".png"), facecolor="white")
    fig.savefig(out_path.with_suffix(".pdf"), facecolor="white")
    plt.close(fig)


def load_optional_pool(path_text: str, log_name: str, pool_name: str) -> tuple[str, pd.DataFrame] | None:
    if not path_text:
        return None
    path = Path(path_text)
    log = path / log_name
    if not log.exists():
        return None
    frame = pd.read_csv(log, encoding="utf-8-sig")
    frame["pool"] = pool_name
    return pool_name, add_section53_rank_score(frame)


def offline_analysis(
    run_dir: Path,
    out_dir: Path,
    top_k: int,
    evaluate_top: bool,
    timeout_s: float,
    independent_run_dir: str = "",
    no_time_run_dir: str = "",
    stage3_free_run_dir: str = "",
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    stage1, stage3 = load_stage_candidates(run_dir)
    thresholds = powerlaw_thresholds()
    extra_pools = [
        item
        for item in [
            load_optional_pool(independent_run_dir, "independent_candidate_log.csv", "independent sampling"),
            load_optional_pool(no_time_run_dir, "independent_candidate_log.csv", "no-time-awareness search"),
            load_optional_pool(stage3_free_run_dir, "stage3_free_candidate_log.csv", "Stage3 LLM free exploration"),
        ]
        if item is not None
    ]

    mean_pool = pd.concat([stage1, stage3], ignore_index=True, sort=False)
    pool_rows = [
        summarize_pool(stage1, "HAST-free search", "300 tree nodes", thresholds),
        summarize_pool(stage3, "HAST bounded search", "200 tree nodes", thresholds),
        summarize_pool(mean_pool, "mean HAST", "500 generated nodes", thresholds),
    ]
    for name, frame in extra_pools:
        budget = "200 tree nodes" if name.startswith("Stage3") else "100 independent candidates"
        row = summarize_pool(frame, name, budget, thresholds)
        row["group"] = "Sampling/search loop" if name.startswith("independent") else "Cost awareness" if name.startswith("no-time") else "Bound induction"
        pool_rows.append(row)
    pool_summary = pd.DataFrame(pool_rows)
    membership, unique = select_top_candidates(stage1, stage3, top_k, extra_pools=extra_pools)
    save_csv(pool_summary, out_dir / "pool_summary_proxy.csv")
    save_csv(membership, out_dir / "top_candidate_membership.csv")
    save_csv(unique, out_dir / "top_candidate_unique_manifest.csv")

    validation_dir = None
    joined = pd.DataFrame()
    validation_agg = pd.DataFrame()
    if evaluate_top:
        validation_dir = run_top_candidate_full_validation(run_dir, unique, out_dir, timeout_s)
        joined, validation_agg = aggregate_full_validation_memberships(membership, unique, validation_dir)
        save_csv(joined, out_dir / "top_candidate_full_validation_membership_metrics.csv")
        save_csv(validation_agg, out_dir / "top_candidate_full_validation_setting_summary.csv")

    final_validation = pd.read_csv(run_dir / "full_validation" / "method_mean_metrics.csv", encoding="utf-8-sig")
    final_validation = final_validation.rename(
        columns={"mean_auc_cNBI": "full_validation_top10_mean_auc_cNBI", "mean_R": "full_validation_top10_mean_R", "mean_time_s": "full_validation_top10_mean_time_s"}
    )
    final_rows = []
    for _, row in final_validation.iterrows():
        proxy_row = pd.concat([stage1, stage3], ignore_index=True)
        proxy_row = proxy_row[proxy_row["candidate_id"].astype(str).eq(str(row["candidate_id"]))]
        final_rows.append(
            {
                "group": "Full HAST",
                "setting": row["method"],
                "budget": "Stage 3 fixed final",
                "valid_rate": 1.0,
                "best_proxy_auc_cNBI": float(proxy_row.iloc[0]["auc_cNBI"]) if not proxy_row.empty else float("nan"),
                "proxy_top10_auc_mean": float(proxy_row.iloc[0]["auc_cNBI"]) if not proxy_row.empty else float("nan"),
                "full_validation_top10_mean_auc_cNBI": row["full_validation_top10_mean_auc_cNBI"],
                "full_validation_top10_mean_R": row["full_validation_top10_mean_R"],
                "full_validation_top10_mean_time_s": row["full_validation_top10_mean_time_s"],
                "rank_score": float("nan"),
                "# > AlphaEvolve": int(float(row["full_validation_top10_mean_auc_cNBI"]) > method_mean_thresholds().get("AlphaEvolve-like", float("inf"))),
                "# > ERA-like": int(float(row["full_validation_top10_mean_auc_cNBI"]) > method_mean_thresholds().get("ERA-like", float("inf"))),
                "conclusion": "Stage 3 fixed final candidate; full validation only",
            }
        )

    table = pool_summary.copy()
    table["full_validation_top10_mean_auc_cNBI"] = float("nan")
    table["full_validation_top10_mean_R"] = float("nan")
    table["full_validation_top10_mean_time_s"] = float("nan")
    table["rank_score"] = table["proxy_top10_rank_score_mean"]
    conclusion_map = {
        "HAST-free search": "Stage 1 free tree search pool from current run",
        "HAST bounded search": "Stage 3 bounded tree search after Stage 2 policy",
        "mean HAST": "Candidate-weighted Stage 1+3 generated pool",
        "independent sampling": "Independent LLM sampling without tree lineage",
        "no-time-awareness search": "Prompt/search control without explicit runtime pressure",
        "Stage3 LLM free exploration": "Stage3 control without Stage2 bounded prompt contract",
    }
    table["conclusion"] = table["setting"].map(conclusion_map).fillna("Section 5.3 ablation pool")
    if not validation_agg.empty:
        compact = validation_agg[validation_agg["criterion"].isin(["proxy auc-cNBI top10", "proxy rank_score top10", "quality+R+time Pareto top10"])].copy()
        for _, row in compact.iterrows():
            setting = str(row["setting"])
            mask = table["setting"].eq("HAST-free search") if setting.startswith("Stage 1") else table["setting"].eq("HAST bounded search") if setting.startswith("Stage 3") else table["setting"].eq(setting)
            if mask is not None and mask.any():
                table.loc[mask, "full_validation_top10_mean_auc_cNBI"] = row["full_validation_top10_mean_auc_cNBI"]
                table.loc[mask, "full_validation_top10_mean_R"] = row["full_validation_top10_mean_R"]
                table.loc[mask, "full_validation_top10_mean_time_s"] = row["full_validation_top10_mean_time_s"]
                table.loc[mask, "rank_score"] = row["full_validation_top10_rank_score"]
        selection_rows = validation_agg[validation_agg["setting"].isin(["raw proxy score", "parent-relative delta", "root-relative delta", "quality-only selection", "quality+R selection", "quality+R+time Pareto"])].copy()
        selection_rows = selection_rows.rename(
            columns={
                "full_validation_top10_rank_score": "rank_score",
            }
        )
        for _, row in selection_rows.iterrows():
            table = pd.concat(
                [
                    table,
                    pd.DataFrame(
                        [
                            {
                                "group": "Credit/selection",
                                "setting": row["setting"],
                                "budget": "offline re-ranking top10",
                                "valid_rate": float("nan"),
                                "best_proxy_auc_cNBI": float("nan"),
                                "proxy_top10_auc_mean": float("nan"),
                                "full_validation_top10_mean_auc_cNBI": row["full_validation_top10_mean_auc_cNBI"],
                                "full_validation_top10_mean_R": row["full_validation_top10_mean_R"],
                                "full_validation_top10_mean_time_s": row["full_validation_top10_mean_time_s"],
                                "rank_score": row["rank_score"],
                                "# > AlphaEvolve": float("nan"),
                                "# > ERA-like": float("nan"),
                                "conclusion": "Offline re-ranking; does not overwrite Stage 3 Q/S",
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )
    table = pd.concat([table, pd.DataFrame(final_rows)], ignore_index=True, sort=False)
    ordered_cols = [
        "group",
        "setting",
        "budget",
        "valid_rate",
        "best_proxy_auc_cNBI",
        "proxy_top10_auc_mean",
        "full_validation_top10_mean_auc_cNBI",
        "full_validation_top10_mean_R",
        "full_validation_top10_mean_time_s",
        "rank_score",
        "# > AlphaEvolve",
        "# > ERA-like",
        "conclusion",
    ]
    table = table[[col for col in ordered_cols if col in table.columns]]
    save_csv(table, out_dir / "table_5_3_ablation_summary.csv")
    save_csv(table, SOURCE_DIR / "table_5_3_ablation_summary.csv")
    save_csv(pool_summary, SOURCE_DIR / "pool_summary_proxy.csv")
    if not validation_agg.empty:
        save_csv(validation_agg, SOURCE_DIR / "top_candidate_full_validation_setting_summary.csv")

    fig_stem = FIG_DIR / "fig_5_3_hast_ablation_search_curves"
    draw_ablation_figure(stage1, stage3, fig_stem, extra_pools=extra_pools)

    summary = {
        "run_dir": str(run_dir),
        "out_dir": str(out_dir),
        "source_table_dir": str(SOURCE_DIR),
        "figure": str(fig_stem.with_suffix(".png")),
        "stage1_candidates": int(len(stage1)),
        "stage3_candidates": int(len(stage3)),
        "extra_pool_candidates": {name: int(len(frame)) for name, frame in extra_pools},
        "unique_top_candidates": int(len(unique)),
        "top_candidate_full_validation_dir": str(validation_dir) if validation_dir else "",
        "llm_experiments_executed": False,
        "llm_api_key_available": bool(os.environ.get("HAST_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")),
    }
    (out_dir / "ablation_5_3_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def independent_prompt(index: int, context: dict[str, Any], no_time_awareness: bool = False) -> str:
    time_text = (
        "Runtime is not part of this ablation prompt; focus on proxy fragmentation quality."
        if no_time_awareness
        else "Keep runtime lightweight and avoid slow global scans."
    )
    return f"""
You are generating candidate #{index} for a HAST 5.3 ablation.

Start from the HDA-original idea below, but generate one independent candidate.
Do not use parent lineage, previous candidates, external data, files, network calls, or test labels.
{time_text}

Root code:
```python
{HDA_ROOT_CODE}
```

Candidate contract:
def degree_order(G):
    return removal_order

Rules:
- Return executable Python only.
- Use deterministic NetworkX-compatible code.
- Allowed imports: math, heapq, random, itertools, collections, networkx, numpy.
- Do not use all-pairs shortest paths, betweenness/PageRank per step, subprocess, eval/exec, file I/O, or network I/O.

{benchmark_context_text(context)}
""".strip()


def stage3_free_prompt(index: int, parent: CandidateProgram, parent_record: dict[str, Any], branch_role: str, context: dict[str, Any]) -> str:
    return f"""
You are expanding HAST 5.3 Stage3-free ablation node #{index}.

This control uses the same Stage3 seed pool and branch schedule as bounded HAST, but it does NOT receive the Stage2 bound policy.
Branch role: {branch_role or "B"}

Parent metrics:
R={float(parent_record.get("R", float("nan"))):.6f}, AUC-cNBI={float(parent_record.get("auc_cNBI", float("nan"))):.6f}, time_s={float(parent_record.get("time_s", float("nan"))):.6f}

Parent code:
```python
{truncate_text(parent.code, 4500)}
```

Goal:
- Mutate the parent freely under the common candidate interface.
- Do not use Stage2 bounded prompt contract, cap policy JSON, or induced allowed-signal list.
- Keep the result deterministic and lightweight enough for proxy evaluation.

Candidate contract:
def degree_order(G):
    return removal_order

Rules:
- Return Python code only.
- Allowed imports: math, heapq, random, itertools, collections, networkx, numpy.
- Do not read/write files, use subprocess/network calls, eval/exec, or external data.

{benchmark_context_text(context)}
""".strip()


def run_independent_or_no_time(args: argparse.Namespace, no_time_awareness: bool) -> dict[str, Any]:
    run_name = "stage_search_no_time_awareness" if no_time_awareness else "stage_search_independent_sampling"
    config = default_config(run_name, delta_credit_mode="root", run_date=args.run_date)
    config = StageSearchConfig(
        **{
            **asdict(config),
            "run_dir": Path(args.out_run_dir) if args.out_run_dir else config.run_dir,
            "stage1_budget": args.budget,
            "stage2_budget": 0,
            "stage3_budget": 0,
        }
    )
    ensure_dirs(config)
    for extra in ["prompts/independent", "raw_llm/independent", "candidates/independent"]:
        (config.run_dir / extra).mkdir(parents=True, exist_ok=True)
    context = read_benchmark_context()
    manifest = {
        "ablation": "no_time_awareness" if no_time_awareness else "independent_sampling",
        "budget": args.budget,
        "run_dir": str(config.run_dir),
        "will_call_llm": bool(args.execute),
        "api_key_available": bool(os.environ.get("HAST_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")),
        "proxy_datasets": config.proxy_datasets,
    }
    (config.run_dir / "ablation_prepare_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.execute:
        return {"prepared": True, **manifest}
    provider = OpenAICompatibleLLMProvider.from_env()
    graphs = [read_graph(name) for name in config.proxy_datasets]
    root = evaluate_root(graphs, DATASET_RATES.get(config.proxy_datasets[0], 0.30))
    log_path = config.run_dir / "independent_candidate_log.csv"
    if log_path.exists():
        existing = pd.read_csv(log_path, encoding="utf-8-sig")
        records: list[dict[str, Any]] = existing.where(pd.notna(existing), None).to_dict("records")
    else:
        records = []
    if len(records) >= args.budget:
        return {"prepared": False, "run_dir": str(config.run_dir), "candidate_rows": len(records), "resumed": True}
    for idx in range(len(records) + 1, args.budget + 1):
        prompt = independent_prompt(idx, context, no_time_awareness=no_time_awareness)
        prompt_path = config.run_dir / f"prompts/independent/{idx:04d}.txt"
        raw_path = config.run_dir / f"raw_llm/independent/{idx:04d}.txt"
        code_path = config.run_dir / f"candidates/independent/{idx:04d}.py"
        prompt_path.write_text(prompt, encoding="utf-8")
        response, llm_elapsed = request_llm_one(provider, prompt, 1)
        raw_path.write_text(response, encoding="utf-8")
        code = extract_code(response)
        code_path.write_text(code, encoding="utf-8")
        try:
            program = make_program(code, family="hast-5.3-independent", source_stage="independent")
            record = evaluate_candidate_with_timeout(program, graphs, rate=0.30, timeout_s=config.candidate_timeout_s)
        except Exception as exc:
            record = invalid_row(f"independent-{idx:04d}", "hast-5.3-independent", "independent", str(exc), len(graphs))
        record.update(
            {
                "node_id": f"independent-{idx:04d}",
                "stage_index": idx,
                "parent_node_id": "",
                "parent_candidate_id": "",
                "parent_auc_cNBI": root["auc_cNBI"],
                "depth": 1,
                "llm_elapsed_s": llm_elapsed,
                "prompt_path": str(prompt_path),
                "raw_response_path": str(raw_path),
                "code_path": str(code_path),
                "tree_role": "independent",
            }
        )
        records.append(record)
        records = refresh_generated_scores(records, STAGE1_WEIGHTS, root["auc_cNBI"], "root")
        pd.DataFrame(records).to_csv(log_path, index=False, encoding="utf-8-sig")
    return {"prepared": False, "run_dir": str(config.run_dir), "candidate_rows": len(records)}


def run_stage3_free(args: argparse.Namespace) -> dict[str, Any]:
    source_run = Path(args.source_run_dir)
    run_name = "stage_search_stage3_free_exploration"
    config = default_config(run_name, delta_credit_mode="root", run_date=args.run_date)
    config = StageSearchConfig(
        **{
            **asdict(config),
            "run_dir": Path(args.out_run_dir) if args.out_run_dir else config.run_dir,
            "stage1_budget": 0,
            "stage2_budget": 0,
            "stage3_budget": args.budget,
            "parent_priority_mode": "legacy",
        }
    )
    ensure_dirs(config)
    (config.run_dir / "prompts/stage3_free").mkdir(parents=True, exist_ok=True)
    (config.run_dir / "raw_llm/stage3_free").mkdir(parents=True, exist_ok=True)
    (config.run_dir / "candidates/stage3_free").mkdir(parents=True, exist_ok=True)
    manifest = {
        "ablation": "stage3_free_exploration_without_stage2_bounds",
        "budget": args.budget,
        "source_run_dir": str(source_run),
        "run_dir": str(config.run_dir),
        "will_call_llm": bool(args.execute),
        "api_key_available": bool(os.environ.get("HAST_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")),
        "uses_stage2_bounds": False,
        "parent_priority_mode": "legacy",
    }
    (config.run_dir / "ablation_prepare_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.execute:
        return {"prepared": True, **manifest}
    provider = OpenAICompatibleLLMProvider.from_env()
    context = read_benchmark_context()
    graphs = [read_graph(name) for name in config.proxy_datasets]
    root_metrics = evaluate_root(graphs, DATASET_RATES.get(config.proxy_datasets[0], 0.30))
    root_program = make_program(HDA_ROOT_CODE, family="HDA-original", source_stage="stage1-root")
    fallback = {
        "candidate_id": root_program.candidate_id,
        "family": root_program.family,
        "source_stage": root_program.source_stage,
        "valid": True,
        **root_metrics,
        "rank_score": 0.0,
        "delta_root_auc_cNBI": 0.0,
        "delta_auc_cNBI": 0.0,
        "code_path": str(source_run / "candidates/stage1/root_hda_original.py"),
    }
    stage1 = pd.read_csv(source_run / "stage1_candidate_log.csv", encoding="utf-8-sig")
    seed_records, seed_programs = select_stage3_seed_nodes(stage1, config.stage3_parent_limit, fallback, root_program)
    stage3, _programs, tree = generate_and_evaluate_tree_stage(
        config=config,
        provider=provider,
        stage="stage3_free",
        budget=args.budget,
        prompt_builder=lambda idx, parent, parent_record, branch_role="B": stage3_free_prompt(
            idx, parent, parent_record, branch_role or "B", context
        ),
        family_default="stage3-free-local",
        graphs=graphs,
        root_auc_cNBI=root_metrics["auc_cNBI"],
        initial_records=seed_records,
        initial_programs=seed_programs,
        weights=STAGE3_WEIGHTS,
        branch_for_index=stage3_branch_for_index,
        static_guard=None,
        parent_priority_mode="legacy",
    )
    return {"prepared": False, "run_dir": str(config.run_dir), "candidate_rows": len(stage3), "tree_rows": len(tree)}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("offline")
    p.add_argument("--run-dir", default=str(MAIN_RUN))
    p.add_argument("--out-dir", default="")
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--evaluate-top", action="store_true")
    p.add_argument("--candidate-timeout-s", type=float, default=90.0)
    p.add_argument("--independent-run-dir", default="")
    p.add_argument("--no-time-run-dir", default="")
    p.add_argument("--stage3-free-run-dir", default="")

    for name in ["independent", "no-time", "stage3-free"]:
        q = sub.add_parser(name)
        q.add_argument("--budget", type=int, default=100 if name != "stage3-free" else 200)
        q.add_argument("--run-date", default="")
        q.add_argument("--out-run-dir", default="")
        q.add_argument("--execute", action="store_true")
        q.add_argument("--source-run-dir", default=str(MAIN_RUN))

    args = parser.parse_args()
    if args.cmd == "offline":
        run_dir = Path(args.run_dir)
        out_dir = Path(args.out_dir) if args.out_dir else run_dir / "ablation_5_3"
        result = offline_analysis(
            run_dir,
            out_dir,
            args.top_k,
            args.evaluate_top,
            args.candidate_timeout_s,
            independent_run_dir=args.independent_run_dir,
            no_time_run_dir=args.no_time_run_dir,
            stage3_free_run_dir=args.stage3_free_run_dir,
        )
    elif args.cmd == "independent":
        result = run_independent_or_no_time(args, no_time_awareness=False)
    elif args.cmd == "no-time":
        result = run_independent_or_no_time(args, no_time_awareness=True)
    elif args.cmd == "stage3-free":
        result = run_stage3_free(args)
    else:
        raise SystemExit(f"unknown command: {args.cmd}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

