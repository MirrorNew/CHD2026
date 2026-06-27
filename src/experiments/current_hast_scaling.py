# -*- coding: utf-8 -*-
"""刷新当前阶段3固定 HAST-Final-Q/S 的 scaling 证据。

该脚本保留已有 baseline 行，只从提供的阶段3 ``final`` 目录重算
HAST-Final-Q/S，并把当前 CHD/HAST raw 表和统一 scaling 表写入
``artifacts/source_tables/scaling``。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import networkx as nx
import numpy as np
import pandas as pd

from model.candidate import CandidateProgram, compile_candidate
from model.config import RUNS_ROOT
from model.data import generate_powerlaw_network
from metrics.ND_fragmentation import compute_metrics, summarize_metrics

SCALING_DIR = ROOT / "artifacts" / "source_tables" / "scaling"
DEFAULT_RUN_DIR = RUNS_ROOT / "runs_HAST_root_target_family_full_ritelt_20260525"

FULL_EVAL_SIZES = [500, 1000, 5000, 10000]
RUNTIME_ONLY_SIZES = [500, 1000, 5000, 10000, 50000, 100000, 1000000]
KINDS = ["powerlaw", "er", "ws", "sbm"]
SEEDS = [42, 43, 44]
HAST_METHODS = ["HAST-Final-Q", "HAST-Final-S"]


def make_full_eval_graph(kind: str, n: int, seed: int) -> nx.Graph:
    if kind == "powerlaw":
        graph = generate_powerlaw_network(n, 2.5, seed=seed)
    elif kind == "er":
        p = min(0.05, 6.0 / max(2, n - 1))
        graph = nx.fast_gnp_random_graph(n, p, seed=seed)
    elif kind == "ws":
        k = min(8, max(2, n // 50 * 2))
        if k % 2 == 1:
            k += 1
        graph = nx.watts_strogatz_graph(n, k, 0.08, seed=seed)
    elif kind == "sbm":
        blocks = 4
        sizes = [n // blocks] * blocks
        sizes[-1] += n - sum(sizes)
        p_in = min(0.08, 10.0 / max(2, n // blocks))
        p_out = p_in * 0.05
        probs = [[p_in if i == j else p_out for j in range(blocks)] for i in range(blocks)]
        graph = nx.stochastic_block_model(sizes, probs, seed=seed)
    else:
        raise ValueError(f"unknown graph kind: {kind}")
    return _clean_connected(graph)


def sparse_sbm_by_edge_sampling(sizes: list[int], p_in: float, p_out: float, seed: int) -> nx.Graph:
    rng = np.random.default_rng(seed)
    offsets = np.cumsum([0] + sizes[:-1]).tolist()
    graph = nx.Graph()
    graph.add_nodes_from(range(sum(sizes)))

    def add_random_edges(src_offset: int, src_size: int, dst_offset: int, dst_size: int, count: int, same_block: bool) -> None:
        remaining = count
        chunk = 500_000
        while remaining > 0:
            take = min(chunk, remaining)
            src = rng.integers(0, src_size, size=take, dtype=np.int64)
            dst = rng.integers(0, dst_size, size=take, dtype=np.int64)
            if same_block:
                mask = src != dst
                src = src[mask]
                dst = dst[mask]
            graph.add_edges_from((int(a + src_offset), int(b + dst_offset)) for a, b in zip(src, dst))
            remaining -= take

    for i, size_i in enumerate(sizes):
        m_in = int(round(p_in * size_i * (size_i - 1) / 2.0))
        add_random_edges(offsets[i], size_i, offsets[i], size_i, m_in, same_block=True)
        for j in range(i + 1, len(sizes)):
            size_j = sizes[j]
            m_out = int(round(p_out * size_i * size_j))
            add_random_edges(offsets[i], size_i, offsets[j], size_j, m_out, same_block=False)
    return graph


def make_runtime_graph(kind: str, n: int, seed: int) -> nx.Graph:
    if kind == "powerlaw":
        graph = nx.barabasi_albert_graph(n, 2, seed=seed)
    elif kind == "er":
        p = min(0.05, 6.0 / max(2, n - 1))
        graph = nx.fast_gnp_random_graph(n, p, seed=seed)
    elif kind == "ws":
        k = min(8, max(2, n // 50 * 2))
        if k % 2 == 1:
            k += 1
        graph = nx.watts_strogatz_graph(n, k, 0.08, seed=seed)
    elif kind == "sbm":
        blocks = 4
        sizes = [n // blocks] * blocks
        sizes[-1] += n - sum(sizes)
        p_in = min(0.08, 10.0 / max(2, n // blocks))
        p_out = p_in * 0.05
        if n >= 100000:
            graph = sparse_sbm_by_edge_sampling(sizes, p_in, p_out, seed)
        else:
            probs = [[p_in if i == j else p_out for j in range(blocks)] for i in range(blocks)]
            graph = nx.stochastic_block_model(sizes, probs, seed=seed)
    else:
        raise ValueError(f"unknown graph kind: {kind}")
    return _clean_connected(graph)


def _clean_connected(graph: nx.Graph) -> nx.Graph:
    graph = nx.Graph(graph)
    graph.remove_edges_from(nx.selfloop_edges(graph))
    if graph.number_of_nodes() and not nx.is_connected(graph):
        components = [list(c) for c in nx.connected_components(graph)]
        for a, b in zip(components[:-1], components[1:]):
            graph.add_edge(a[0], b[0])
    return nx.convert_node_labels_to_integers(graph)


def load_current_programs(final_dir: Path) -> dict[str, Callable[[nx.Graph], list[Any]]]:
    programs: dict[str, Callable[[nx.Graph], list[Any]]] = {}
    for method in HAST_METHODS:
        path = final_dir / f"{method}.py"
        if not path.exists():
            raise FileNotFoundError(f"missing Stage-3 final candidate: {path}")
        program = CandidateProgram(
            candidate_id=method,
            code=path.read_text(encoding="utf-8"),
            family="current-root-relative-HAST",
            source_stage="stage3-final",
        )
        programs[method] = compile_candidate(program)
    return programs


def evaluate_full_one(kind: str, n: int, seed: int, method: str, runner: Callable[[nx.Graph], list[Any]]) -> dict[str, Any]:
    graph = make_full_eval_graph(kind, n, seed)
    start = time.perf_counter()
    try:
        order = runner(graph.copy())
        elapsed = time.perf_counter() - start
        metrics = compute_metrics(graph, order, rate=0.30, method_time=elapsed)
        summary = summarize_metrics(metrics)
        return {
            "kind": kind,
            "n": n,
            "seed": seed,
            "edges": graph.number_of_edges(),
            "method": method,
            "ok": True,
            "time_s": summary["time_s"],
            "R": summary["R"],
            "auc_cNBI": summary["auc_cNBI"],
            "error": "",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "kind": kind,
            "n": n,
            "seed": seed,
            "edges": graph.number_of_edges(),
            "method": method,
            "ok": False,
            "time_s": time.perf_counter() - start,
            "R": math.nan,
            "auc_cNBI": math.nan,
            "error": f"{type(exc).__name__}: {exc}",
        }


def evaluate_runtime_one(kind: str, n: int, seed: int, method: str, runner: Callable[[nx.Graph], list[Any]]) -> dict[str, Any]:
    graph = make_runtime_graph(kind, n, seed)
    start = time.perf_counter()
    try:
        order = runner(graph.copy())
        elapsed = time.perf_counter() - start
        ok = len(set(order)) == graph.number_of_nodes()
        return {
            "kind": kind,
            "n": n,
            "seed": seed,
            "method": method,
            "ok": bool(ok),
            "time_s": elapsed,
            "status": "ok" if ok else "invalid_order",
            "error": "" if ok else f"order_len={len(order)} unique={len(set(order))} n={graph.number_of_nodes()}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "kind": kind,
            "n": n,
            "seed": seed,
            "method": method,
            "ok": False,
            "time_s": time.perf_counter() - start,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }


def refresh_unified_tables(full_hast: pd.DataFrame, runtime_hast: pd.DataFrame) -> None:
    full_path = SCALING_DIR / "full_eval_500_to_10k_unified.csv"
    runtime_path = SCALING_DIR / "runtime_only_500_to_1000k_unified.csv"
    old_full = pd.read_csv(full_path, encoding="utf-8-sig")
    old_runtime = pd.read_csv(runtime_path, encoding="utf-8-sig")
    full_unified = pd.concat([old_full[~old_full["method"].isin(HAST_METHODS)], full_hast], ignore_index=True, sort=False)
    runtime_unified = pd.concat([old_runtime[~old_runtime["method"].isin(HAST_METHODS)], runtime_hast], ignore_index=True, sort=False)
    full_unified = full_unified.sort_values(["kind", "n", "seed", "method"]).reset_index(drop=True)
    runtime_unified = runtime_unified.sort_values(["kind", "n", "seed", "method"]).reset_index(drop=True)
    full_unified.to_csv(full_path, index=False, encoding="utf-8-sig")
    runtime_unified.to_csv(runtime_path, index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--skip-runtime-large", action="store_true", help="Only refresh full-eval and 500-10k runtime rows.")
    args = parser.parse_args()

    final_dir = args.run_dir / "final"
    programs = load_current_programs(final_dir)
    SCALING_DIR.mkdir(parents=True, exist_ok=True)

    full_rows: list[dict[str, Any]] = []
    for n in FULL_EVAL_SIZES:
        for kind in KINDS:
            for seed in SEEDS:
                for method, runner in programs.items():
                    row = evaluate_full_one(kind, n, seed, method, runner)
                    full_rows.append(row)
                    print(
                        f"[full] n={n} kind={kind} seed={seed} method={method} "
                        f"ok={row['ok']} time={float(row['time_s']):.3f}s",
                        flush=True,
                    )
    full_hast = pd.DataFrame(full_rows)
    full_hast.to_csv(SCALING_DIR / "current_hast_full_eval_500_to_10k.csv", index=False, encoding="utf-8-sig")

    runtime_rows: list[dict[str, Any]] = []
    for _, row in full_hast.iterrows():
        runtime_rows.append(
            {
                "kind": row["kind"],
                "n": int(row["n"]),
                "seed": int(row["seed"]),
                "method": row["method"],
                "ok": bool(row["ok"]),
                "time_s": float(row["time_s"]),
                "status": "ok" if bool(row["ok"]) else "error",
                "error": "" if bool(row["ok"]) else str(row.get("error", "")),
            }
        )
    if not args.skip_runtime_large:
        for n in [x for x in RUNTIME_ONLY_SIZES if x > max(FULL_EVAL_SIZES)]:
            for kind in KINDS:
                for seed in SEEDS:
                    for method, runner in programs.items():
                        row = evaluate_runtime_one(kind, n, seed, method, runner)
                        runtime_rows.append(row)
                        print(
                            f"[runtime] n={n} kind={kind} seed={seed} method={method} "
                            f"status={row['status']} time={float(row['time_s']):.3f}s",
                            flush=True,
                        )
    runtime_hast = pd.DataFrame(runtime_rows)
    runtime_hast.to_csv(SCALING_DIR / "current_hast_runtime_only_500_to_1000k.csv", index=False, encoding="utf-8-sig")
    refresh_unified_tables(full_hast, runtime_hast)

    manifest = {
        "run_dir": str(args.run_dir),
        "final_dir": str(final_dir),
        "methods": HAST_METHODS,
        "full_eval_sizes": FULL_EVAL_SIZES,
        "runtime_only_sizes": RUNTIME_ONLY_SIZES if not args.skip_runtime_large else FULL_EVAL_SIZES,
        "kinds": KINDS,
        "seeds": SEEDS,
        "selection_source": "stage3_final_dir",
    }
    (SCALING_DIR / "current_hast_scaling_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
