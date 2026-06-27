# -*- coding: utf-8 -*-
"""Run native IM heuristics under random-threshold Linear Threshold evaluation.

This runner intentionally uses one subprocess per graph/method task so a slow
heuristic can be killed after ``--timeout-s`` without poisoning the worker pool.
It writes checkpoints after every completed/skipped task.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd


CHILD_CODE = r'''
import json
import math
import sys
import time
from pathlib import Path

import networkx as nx

from baselines.IM_native_baseline import (
    celf_seed_order,
    celfpp_seed_order,
    cluster_greedy_lt_seed_order,
    degree_discount_ic_seed_order,
    domim_seed_order,
    greedy_mc_seed_order,
    imm_seed_order,
    mia_seed_order,
    rr_greedy_seed_order,
)
from metrics.IM_LT_evaluator import evaluate_lt_spread
from model.im_task import im_seed_budget


def normalize_seeds(graph, raw, k):
    nodes = set(graph.nodes())
    out = []
    seen = set()
    try:
        raw_list = list(raw or [])
    except TypeError:
        raw_list = []
    for node in raw_list:
        if node in nodes and node not in seen:
            seen.add(node)
            out.append(node)
        if len(out) >= k:
            break
    valid = 0 < len(out) <= k
    if len(out) < k:
        out.extend([node for node in graph.nodes() if node not in seen][: k - len(out)])
    return out, valid


graph_path = Path(sys.argv[1])
method = sys.argv[2]
p = float(sys.argv[3])
seed = int(sys.argv[4])
generation_simulations = int(sys.argv[5])
rr_sets = int(sys.argv[6])
max_rr_sets = int(sys.argv[7])
eval_simulations = int(sys.argv[8])

graph = nx.read_edgelist(graph_path, nodetype=int, create_using=nx.Graph())
graph.remove_edges_from(nx.selfloop_edges(graph))
graph = nx.convert_node_labels_to_integers(graph)
k = im_seed_budget(graph.number_of_nodes())

fns = {
    "DegreeDiscountIC": lambda: degree_discount_ic_seed_order(graph, k, p=p),
    "MCGreedy": lambda: greedy_mc_seed_order(graph, k, p=p, simulations=generation_simulations, seed=seed),
    "CELF": lambda: celf_seed_order(graph, k, p=p, simulations=generation_simulations, seed=seed),
    "CELF++": lambda: celfpp_seed_order(graph, k, p=p, simulations=generation_simulations, seed=seed),
    "MIA-PMIA-family": lambda: mia_seed_order(graph, k, p=p, theta=0.001),
    "RRGreedy": lambda: rr_greedy_seed_order(graph, k, p=p, rr_sets=rr_sets, seed=seed),
    "IMM-style": lambda: imm_seed_order(graph, k, p=p, epsilon=0.5, ell=1.0, seed=seed, max_rr_sets=max_rr_sets),
    "DomIM-2021": lambda: domim_seed_order(graph, k, p=p, simulations=generation_simulations, seed=seed),
    "ClusterGreedy-LT-2024": lambda: cluster_greedy_lt_seed_order(graph, k, simulations=generation_simulations, seed=seed),
}

started = time.perf_counter()
error = ""
seeds = []
valid = False
spread = float("nan")
spread_std = float("nan")
spread_ci95 = float("nan")
evaluation_time_s = float("nan")
try:
    raw = fns[method]()
    seeds, valid = normalize_seeds(graph, raw, k)
    if valid:
        result = evaluate_lt_spread(graph, seeds, simulations=eval_simulations, base_seed=20260626)
        spread = result.spread_mean
        spread_std = result.spread_std
        spread_ci95 = result.spread_ci95
        evaluation_time_s = result.time_s
except Exception as exc:
    error = f"{type(exc).__name__}: {exc}"
elapsed = time.perf_counter() - started

print(json.dumps({
    "k": k,
    "valid": bool(valid and not error),
    "spread": float(spread),
    "normalized_spread": float(spread / max(1, graph.number_of_nodes())) if math.isfinite(spread) else float("nan"),
    "spread_std": float(spread_std),
    "spread_ci95": float(spread_ci95),
    "simulations": int(eval_simulations),
    "time_s": float(elapsed),
    "evaluation_time_s": float(evaluation_time_s),
    "seed_nodes": json.dumps(seeds, ensure_ascii=False),
    "error": error,
}, ensure_ascii=False))
'''


METHOD_REPRODUCTION_REVIEW = [
    {
        "method": "DegreeDiscountIC",
        "status": "usable_heuristic_reproduction",
        "notes": "Matches the standard DegreeDiscount-IC scoring shape for uniform IC probability; cheap and suitable as a root/native heuristic. It is IC-oriented but can be evaluated under LT.",
    },
    {
        "method": "MCGreedy",
        "status": "conceptually_correct_but_not_scalable",
        "notes": "Naive Kempe-style Monte-Carlo greedy. On large graphs it is O(k*n*simulations*diffusion_cost), so multi-hour runtime on condmat is expected, not a hardware fault.",
    },
    {
        "method": "CELF",
        "status": "conceptually_correct_but_python_slow",
        "notes": "Lazy-forward greedy shape is present, but spread estimates are still pure Python Monte-Carlo. Large graphs may exceed timeout.",
    },
    {
        "method": "CELF++",
        "status": "approximate_reproduction_but_python_slow",
        "notes": "Implements CELF++-style caching, not an optimized official implementation. Large graph runs may exceed timeout.",
    },
    {
        "method": "MIA-PMIA-family",
        "status": "idea_level_reproduction_not_practical_here",
        "notes": "Maximum-probability-path approximation is implemented directly and is too slow for large graphs; keep timeout/skip behavior.",
    },
    {
        "method": "RRGreedy",
        "status": "usable_fixed_sample_rr_baseline",
        "notes": "Fixed RR-set greedy is a reasonable scalable Python baseline, though not a theorem-level IMM/OPIM implementation.",
    },
    {
        "method": "IMM-style",
        "status": "approximate_reproduction_with_sample_cap",
        "notes": "Keeps IMM two-phase RR shape but caps samples. Good engineering baseline, not official IMM C++ equivalence.",
    },
    {
        "method": "DomIM-2021",
        "status": "heuristic_reproduction",
        "notes": "Dominating-set/local-search style heuristic. Can be evaluated under LT, but its internal objective is IC-like.",
    },
    {
        "method": "ClusterGreedy-LT-2024",
        "status": "lt_oriented_but_python_slow",
        "notes": "Most aligned with LT, using cluster-local LT greedy and budget combination. Pure Python/NDlib-like simulation can be slow.",
    },
]


NETWORKX_BASELINE_REVIEW = [
    {
        "name": "degree centrality / high degree",
        "usable": True,
        "notes": "NetworkX exposes graph.degree directly; this is a simple native baseline/root, not an LT propagation algorithm.",
    },
    {
        "name": "approximation.dominating_set",
        "usable": True,
        "notes": "Relevant as a coverage-style seed heuristic; not an influence-maximization algorithm.",
    },
    {
        "name": "approximation.min_weighted_vertex_cover",
        "usable": True,
        "notes": "Can serve as structural coverage baseline, but not a diffusion-model baseline.",
    },
    {
        "name": "community.greedy_modularity_communities",
        "usable": True,
        "notes": "Useful for cluster-aware seed allocation; not a propagation model.",
    },
    {
        "name": "LT/IC diffusion",
        "usable": False,
        "notes": "NetworkX 3.4.2 does not provide built-in LT/IC diffusion evaluation; NDlib is the appropriate library here.",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", default="src/runs/20260626-011940-IM-im12-real-smoke")
    parser.add_argument("--graph-dir", default="network/12main_network")
    parser.add_argument("--workers", type=int, default=max(1, min(8, (os.cpu_count() or 4) - 1)))
    parser.add_argument("--timeout-s", type=int, default=200)
    parser.add_argument("--p", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=20260626)
    parser.add_argument("--generation-simulations", type=int, default=64)
    parser.add_argument("--rr-sets", type=int, default=2048)
    parser.add_argument("--max-rr-sets", type=int, default=20000)
    parser.add_argument("--eval-simulations", type=int, default=4096)
    parser.add_argument("--methods", default="DegreeDiscountIC,MCGreedy,CELF,CELF++,MIA-PMIA-family,RRGreedy,IMM-style,DomIM-2021,ClusterGreedy-LT-2024")
    return parser.parse_args()


def check_gpu() -> dict[str, Any]:
    out = {"cupy": False, "cugraph": False, "gpu_acceleration_used": False}
    for name in ["cupy", "cugraph"]:
        try:
            __import__(name)
            out[name] = True
        except Exception:
            out[name] = False
    out["notes"] = "NDlib and NetworkX execute on CPU in this environment; no GPU backend is available."
    return out


def graph_paths(graph_dir: Path) -> dict[str, Path]:
    return {path.stem: path for path in sorted(graph_dir.glob("*.edgelist"))}


def existing_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = pd.read_csv(path, encoding="utf-8-sig").to_dict("records")
    return [row for row in rows if str(row.get("model_type")) == "LT_RandomThreshold"]


def summarize(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=["method", "method_group", "model_type", "mean_spread", "mean_normalized_spread", "mean_time_s", "valid_rate", "graph_count"]
        )
    df = pd.DataFrame(rows)
    out = []
    for (method, group_name, model_type), group in df.groupby(["method", "method_group", "model_type"], dropna=False):
        valid = group[group["valid"].astype(str).str.lower().isin(["true", "1"])]
        out.append(
            {
                "method": method,
                "method_group": group_name,
                "model_type": model_type,
                "mean_spread": float(pd.to_numeric(valid["spread"], errors="coerce").mean()) if len(valid) else float("nan"),
                "mean_normalized_spread": float(pd.to_numeric(valid["normalized_spread"], errors="coerce").mean()) if len(valid) else float("nan"),
                "mean_time_s": float(pd.to_numeric(group["time_s"], errors="coerce").mean()),
                "valid_rate": float(group["valid"].astype(str).str.lower().isin(["true", "1"]).mean()),
                "graph_count": int(len(group)),
            }
        )
    return pd.DataFrame(out).sort_values(["model_type", "mean_spread"], ascending=[True, False])


def write_outputs(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    native_dir = run_dir / "native"
    summary_dir = run_dir / "summary"
    native_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["dataset", "method", "model_type"], keep="last")
        df = df.sort_values(["dataset", "method"])
    df.to_csv(native_dir / "per_graph_metrics.csv", index=False, encoding="utf-8-sig")
    mean_df = summarize(df.to_dict("records") if not df.empty else [])
    mean_df.to_csv(native_dir / "method_mean_metrics.csv", index=False, encoding="utf-8-sig")
    df.to_csv(summary_dir / "all_methods_lt_per_graph.csv", index=False, encoding="utf-8-sig")
    mean_df.to_csv(summary_dir / "all_methods_lt_mean.csv", index=False, encoding="utf-8-sig")


def run_one(task: tuple[str, str, Path, argparse.Namespace]) -> dict[str, Any]:
    dataset, method, graph_path, args = task
    started = time.perf_counter()
    cmd = [
        sys.executable,
        "-c",
        CHILD_CODE,
        str(graph_path),
        method,
        str(args.p),
        str(args.seed),
        str(args.generation_simulations),
        str(args.rr_sets),
        str(args.max_rr_sets),
        str(args.eval_simulations),
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout_s)
        elapsed = time.perf_counter() - started
        if completed.returncode != 0:
            return timeout_or_error_row(dataset, method, graph_path, elapsed, "subprocess_failed: " + (completed.stderr or completed.stdout)[-600:])
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        return {"dataset": dataset, "method": method, "method_group": "native", "model_type": "LT_RandomThreshold", **payload}
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - started
        return timeout_or_error_row(dataset, method, graph_path, elapsed, f"skipped_timeout_{args.timeout_s}s")


def timeout_or_error_row(dataset: str, method: str, graph_path: Path, elapsed: float, error: str) -> dict[str, Any]:
    import networkx as nx

    from model.im_task import im_seed_budget

    graph = nx.read_edgelist(graph_path, nodetype=int, create_using=nx.Graph())
    return {
        "dataset": dataset,
        "method": method,
        "method_group": "native",
        "model_type": "LT_RandomThreshold",
        "k": im_seed_budget(graph.number_of_nodes()),
        "valid": False,
        "spread": float("nan"),
        "normalized_spread": float("nan"),
        "spread_std": float("nan"),
        "spread_ci95": float("nan"),
        "simulations": 0,
        "time_s": float(elapsed),
        "evaluation_time_s": float("nan"),
        "seed_nodes": "[]",
        "error": error,
    }


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir)
    native_dir = run_dir / "native"
    native_dir.mkdir(parents=True, exist_ok=True)
    methods = [item.strip() for item in args.methods.split(",") if item.strip()]
    paths = graph_paths(Path(args.graph_dir))
    rows = existing_rows(native_dir / "per_graph_metrics.csv")
    done = {
        (str(row["dataset"]), str(row["method"]))
        for row in rows
        if not str(row.get("error", "")).startswith("skipped_timeout_")
    }
    tasks = [
        (dataset, method, graph_path, args)
        for dataset, graph_path in paths.items()
        for method in methods
        if (dataset, method) not in done
    ]
    manifest = {
        "run_dir": str(run_dir),
        "model_type": "LT_RandomThreshold",
        "evaluator": "LT_random_threshold_common_worlds",
        "threshold_distribution": "Uniform(0,1) per node per simulation",
        "edge_weight": "1/degree(v) for each active neighbor of v",
        "workers": args.workers,
        "timeout_s": args.timeout_s,
        "methods": methods,
        "graph_count": len(paths),
        "target_rows": len(paths) * len(methods),
        "existing_rows": len(rows),
        "gpu": check_gpu(),
        "method_reproduction_review": METHOD_REPRODUCTION_REVIEW,
        "networkx_baseline_review": NETWORKX_BASELINE_REVIEW,
        "status": "running",
        "started_or_updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (native_dir / "lt_ndlib_parallel_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_outputs(run_dir, rows)
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)

    with futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_map = {executor.submit(run_one, task): task for task in tasks}
        for future in futures.as_completed(future_map):
            dataset, method, _graph_path, _args = future_map[future]
            try:
                row = future.result()
            except Exception as exc:  # noqa: BLE001
                row = {
                    "dataset": dataset,
                    "method": method,
                    "method_group": "native",
                    "model_type": "LT_RandomThreshold",
                    "k": 0,
                    "valid": False,
                    "spread": float("nan"),
                    "normalized_spread": float("nan"),
                    "spread_std": float("nan"),
                    "spread_ci95": float("nan"),
                    "simulations": 0,
                    "time_s": 0.0,
                    "evaluation_time_s": float("nan"),
                    "seed_nodes": "[]",
                    "error": f"runner_exception: {type(exc).__name__}: {exc}",
                }
            rows.append(row)
            write_outputs(run_dir, rows)
            print(
                f"[lt-random] {row['dataset']} {row['method']} valid={row['valid']} "
                f"spread={row['spread']} error={row['error']}",
                flush=True,
            )

    final_rows = pd.read_csv(native_dir / "per_graph_metrics.csv", encoding="utf-8-sig")
    final_mean = pd.read_csv(native_dir / "method_mean_metrics.csv", encoding="utf-8-sig")
    manifest.update(
        {
            "status": "completed",
            "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "per_graph_rows": int(len(final_rows)),
            "mean_rows": int(len(final_mean)),
            "timeouts": int(final_rows["error"].astype(str).str.contains("skipped_timeout", na=False).sum()),
        }
    )
    (native_dir / "lt_ndlib_parallel_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
