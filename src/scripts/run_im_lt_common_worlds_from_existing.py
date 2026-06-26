# -*- coding: utf-8 -*-
"""Re-evaluate recorded IM seed sets with the fixed LT common-world evaluator."""

from __future__ import annotations

import argparse
import ast
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from model.config import PROJECT_ROOT, make_run_dir  # noqa: E402
from model.im_lt_evaluator import evaluate_lt_spread_many  # noqa: E402


DATASETS_12 = [
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
    "Powerlaw_500",
    "Yeast",
]


def resolve_project_path(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed-source",
        default="src/runs/20260626-011940-IM-im12-real-smoke/summary/all_methods_lt_per_graph.csv",
        help="CSV with recorded method seed_nodes and timeout rows.",
    )
    parser.add_argument("--graph-dir", default="network/12main_network")
    parser.add_argument("--run-name", default="im-lt-common-worlds-4096")
    parser.add_argument("--run-date", default="")
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--simulations", type=int, default=4096)
    parser.add_argument("--base-seed", type=int, default=20260626)
    parser.add_argument("--disabled-methods", default="MIA-PMIA-family")
    parser.add_argument("--model-type", default="LT_RandomThreshold")
    return parser.parse_args()


def read_graph(path: Path) -> nx.Graph:
    graph = nx.read_edgelist(path, nodetype=int, comments="#", data=False, create_using=nx.Graph())
    graph.remove_edges_from(nx.selfloop_edges(graph))
    return nx.convert_node_labels_to_integers(graph)


def parse_seed_nodes(value: Any) -> list[int]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    parsed = ast.literal_eval(text)
    return [int(node) for node in list(parsed)]


def bool_from_cell(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def summarize(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    valid = df["valid"].astype(str).str.lower().isin(["true", "1"])
    df_valid = df[valid].copy()
    out: list[dict[str, Any]] = []
    for (method, group_name, model_type), group in df.groupby(["method", "method_group", "model_type"], dropna=False):
        group_valid = df_valid[
            df_valid["method"].eq(method)
            & df_valid["method_group"].eq(group_name)
            & df_valid["model_type"].eq(model_type)
        ]
        out.append(
            {
                "method": method,
                "method_group": group_name,
                "model_type": model_type,
                "mean_spread": float(pd.to_numeric(group_valid["spread"], errors="coerce").mean()) if len(group_valid) else float("nan"),
                "mean_normalized_spread": float(pd.to_numeric(group_valid["normalized_spread"], errors="coerce").mean()) if len(group_valid) else float("nan"),
                "mean_spread_ci95": float(pd.to_numeric(group_valid["spread_ci95"], errors="coerce").mean()) if len(group_valid) else float("nan"),
                "mean_time_s": float(pd.to_numeric(group["time_s"], errors="coerce").mean()),
                "valid_rate": float(group["valid"].astype(str).str.lower().isin(["true", "1"]).mean()),
                "graph_count": int(len(group)),
            }
        )
    return pd.DataFrame(out).sort_values(["model_type", "mean_normalized_spread"], ascending=[True, False])


def add_ranks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows
    df = pd.DataFrame(rows)
    df["rank_spread"] = float("nan")
    df["rank_tie_group"] = ""
    valid = df["valid"].astype(str).str.lower().isin(["true", "1"])
    for dataset, group in df[valid].groupby("dataset"):
        ordered = group.sort_values("spread", ascending=False)
        df.loc[ordered.index, "rank_spread"] = pd.to_numeric(ordered["spread"], errors="coerce").rank(
            method="average",
            ascending=False,
        )
        tie_group = 1
        previous_mean = None
        previous_ci = None
        for idx, row in ordered.iterrows():
            mean = float(row["spread"])
            ci = float(row.get("spread_ci95", 0.0))
            if previous_mean is not None and abs(previous_mean - mean) > (previous_ci or 0.0) + ci:
                tie_group += 1
            df.loc[idx, "rank_tie_group"] = f"{dataset}-G{tie_group}"
            previous_mean = mean
            previous_ci = ci
    return df.where(pd.notna(df), "").to_dict("records")


def output_paths(run_dir: Path) -> dict[str, Path]:
    return {
        "native_per_graph": run_dir / "native" / "per_graph_metrics.csv",
        "native_mean": run_dir / "native" / "method_mean_metrics.csv",
        "summary_per_graph": run_dir / "summary" / "all_methods_lt_per_graph.csv",
        "summary_mean": run_dir / "summary" / "all_methods_lt_mean.csv",
        "manifest": run_dir / "run_manifest.json",
    }


def write_outputs(run_dir: Path, rows: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    rows = add_ranks(rows)
    mean_df = summarize(rows)
    paths = output_paths(run_dir)
    write_csv(paths["native_per_graph"], rows)
    write_csv(paths["summary_per_graph"], rows)
    paths["native_mean"].parent.mkdir(parents=True, exist_ok=True)
    mean_df.to_csv(paths["native_mean"], index=False, encoding="utf-8-sig")
    paths["summary_mean"].parent.mkdir(parents=True, exist_ok=True)
    mean_df.to_csv(paths["summary_mean"], index=False, encoding="utf-8-sig")
    paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    source_path = resolve_project_path(args.seed_source)
    graph_dir = resolve_project_path(args.graph_dir)
    run_dir = resolve_project_path(args.run_dir) if args.run_dir else make_run_dir("IM", args.run_name, args.run_date or None)
    disabled = {item.strip() for item in args.disabled_methods.split(",") if item.strip()}
    source_df = pd.read_csv(source_path, encoding="utf-8-sig")
    source_df = source_df[source_df["dataset"].isin(DATASETS_12)].copy()
    source_df = source_df.sort_values(["dataset", "method"])

    manifest: dict[str, Any] = {
        "run_dir": str(run_dir),
        "seed_source": str(source_path),
        "graph_dir": str(graph_dir),
        "model_type": args.model_type,
        "evaluator": "LT_random_threshold_common_worlds",
        "threshold_distribution": "Uniform(0,1) per node per simulation",
        "edge_weight": "1/degree(v) for each active neighbor of v",
        "simulations": int(args.simulations),
        "base_seed": int(args.base_seed),
        "disabled_methods": sorted(disabled),
        "api_key_saved": False,
        "status": "running",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    rows: list[dict[str, Any]] = []
    total_eval_time = 0.0
    for dataset in DATASETS_12:
        graph_path = graph_dir / f"{dataset}.edgelist"
        graph = read_graph(graph_path)
        sub = source_df[source_df["dataset"].eq(dataset)]
        runnable: dict[str, list[int]] = {}
        source_rows_by_method: dict[str, dict[str, Any]] = {}
        for _, row in sub.iterrows():
            method = str(row["method"])
            source_rows_by_method[method] = row.to_dict()
            if method in disabled:
                rows.append(
                    {
                        "dataset": dataset,
                        "method": method,
                        "method_group": row.get("method_group", "native"),
                        "model_type": args.model_type,
                        "k": int(row.get("k", 0) or 0),
                        "valid": False,
                        "spread": float("nan"),
                        "normalized_spread": float("nan"),
                        "spread_std": float("nan"),
                        "spread_ci95": float("nan"),
                        "simulations": int(args.simulations),
                        "time_s": 0.0,
                        "seed_generation_time_s": row.get("time_s", float("nan")),
                        "evaluation_time_s": 0.0,
                        "seed_nodes": "[]",
                        "error": "disabled_by_policy",
                        "source_error": row.get("error", ""),
                    }
                )
            elif bool_from_cell(row.get("valid")):
                runnable[method] = parse_seed_nodes(row.get("seed_nodes"))
            else:
                rows.append(
                    {
                        "dataset": dataset,
                        "method": method,
                        "method_group": row.get("method_group", "native"),
                        "model_type": args.model_type,
                        "k": int(row.get("k", 0) or 0),
                        "valid": False,
                        "spread": float("nan"),
                        "normalized_spread": float("nan"),
                        "spread_std": float("nan"),
                        "spread_ci95": float("nan"),
                        "simulations": int(args.simulations),
                        "time_s": row.get("time_s", float("nan")),
                        "seed_generation_time_s": row.get("time_s", float("nan")),
                        "evaluation_time_s": 0.0,
                        "seed_nodes": "[]",
                        "error": row.get("error", "skipped_unavailable_from_seed_source"),
                        "source_error": row.get("error", ""),
                    }
                )

        started = time.perf_counter()
        results = evaluate_lt_spread_many(graph, runnable, simulations=args.simulations, base_seed=args.base_seed)
        graph_eval_time = time.perf_counter() - started
        total_eval_time += graph_eval_time
        for method, result in results.items():
            source = source_rows_by_method[method]
            seed_generation_time = float(source.get("time_s", 0.0) or 0.0)
            rows.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "method_group": source.get("method_group", "native"),
                    "model_type": args.model_type,
                    "k": int(source.get("k", len(runnable[method])) or len(runnable[method])),
                    "valid": True,
                    "spread": result.spread_mean,
                    "normalized_spread": result.normalized_spread,
                    "spread_std": result.spread_std,
                    "spread_ci95": result.spread_ci95,
                    "simulations": result.simulations,
                    "time_s": seed_generation_time + result.time_s,
                    "seed_generation_time_s": seed_generation_time,
                    "evaluation_time_s": result.time_s,
                    "seed_nodes": json.dumps(runnable[method], ensure_ascii=False),
                    "error": "",
                    "source_error": source.get("error", ""),
                }
            )
        manifest["last_completed_dataset"] = dataset
        manifest["rows_so_far"] = len(rows)
        write_outputs(run_dir, rows, manifest)
        print(f"[im-lt] {dataset} runnable={len(runnable)} elapsed={graph_eval_time:.3f}s", flush=True)

    manifest.update(
        {
            "status": "completed",
            "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "per_graph_rows": len(rows),
            "valid_rows": int(sum(1 for row in rows if row["valid"])),
            "skipped_rows": int(sum(1 for row in rows if not row["valid"])),
            "total_evaluation_time_s": float(total_eval_time),
        }
    )
    write_outputs(run_dir, rows, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
