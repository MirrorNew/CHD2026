# -*- coding: utf-8 -*-
"""Recompute classic full-sequence R for CI, MinSum, BPD, CoreHD, and GND.

Metric:
    classic_R_percent = 100 * sum_{k=1..N} GCC_k / N

The 12 benchmark graphs are read from network/12main_network. Trusted native
strong-baseline deletion sequences are used when present; missing sequences are
filled by the local clean-room Python implementations in src/baselines.
"""

from __future__ import annotations

import csv
import json
import math
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import networkx as nx
import pandas as pd


PROJECT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT / "src"
NETWORK_DIR = PROJECT / "network" / "12main_network"
OUT_DIR = PROJECT / "src" / "runs" / "classic_r_recomputed_20260624"
GCC_DIR = OUT_DIR / "gcc_sequences"
NATIVE_ROOT = (
    PROJECT
    / "src"
    / "runs"
    / "runs_paper_evidence_20260616"
    / "02_12graph_benchmark_quality_runtime"
    / "native-strong-baseline"
)

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

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from baselines import bpd_order, ci_order, corehd_fast_order, gnd_order, minsum_order  # noqa: E402


def node_key(node: Any) -> tuple[int, Any]:
    try:
        return (0, int(node))
    except (TypeError, ValueError):
        return (1, str(node))


def read_graph(dataset: str) -> nx.Graph:
    path = NETWORK_DIR / f"{dataset}.edgelist"
    graph = nx.read_edgelist(path, nodetype=int, comments="#", data=False)
    graph = nx.Graph(graph)
    graph.remove_edges_from(nx.selfloop_edges(graph))
    return graph


def parse_order_file(path: Path) -> list[int]:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, encoding="utf-8-sig")
        if "node" in df.columns:
            values = df["node"].dropna().tolist()
        else:
            values = df.iloc[:, 0].dropna().tolist()
    else:
        values = []
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                text = line.strip()
                if text:
                    values.append(text.split()[0].strip(","))
    out: list[int] = []
    for value in values:
        text = str(value).strip()
        if text:
            out.append(int(float(text)))
    return out


def validate_order(graph: nx.Graph, order: Iterable[Any]) -> tuple[list[Any], dict[str, Any], str]:
    raw = list(order)
    nodes = set(graph.nodes())
    seen: set[Any] = set()
    clean: list[Any] = []
    duplicates: list[Any] = []
    extras: list[Any] = []
    for node in raw:
        if node not in nodes:
            extras.append(node)
            continue
        if node in seen:
            duplicates.append(node)
            continue
        seen.add(node)
        clean.append(node)
    missing = sorted((node for node in nodes if node not in seen), key=node_key)
    ok = not missing and not extras and not duplicates and len(clean) == graph.number_of_nodes()
    info = {
        "raw_len": len(raw),
        "clean_len": len(clean),
        "unique_valid_nodes": len(seen),
        "graph_nodes": graph.number_of_nodes(),
        "missing_count": len(missing),
        "extra_count": len(extras),
        "duplicate_count": len(duplicates),
        "missing_preview": " ".join(map(str, missing[:10])),
        "extra_preview": " ".join(map(str, extras[:10])),
        "duplicate_preview": " ".join(map(str, duplicates[:10])),
    }
    return clean, info, "ok" if ok else "rejected"


class DSU:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.size = [1] * n
        self.active = [False] * n
        self.largest = 0

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def activate(self, x: int) -> None:
        self.active[x] = True
        self.parent[x] = x
        self.size[x] = 1
        self.largest = max(self.largest, 1)

    def union(self, a: int, b: int) -> None:
        if not self.active[a] or not self.active[b]:
            return
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        self.largest = max(self.largest, self.size[ra])


def classic_gcc_curve(graph: nx.Graph, order: list[Any]) -> tuple[float, list[dict[str, Any]]]:
    n = graph.number_of_nodes()
    nodes = list(graph.nodes())
    idx = {node: i for i, node in enumerate(nodes)}
    adj = [[] for _ in nodes]
    for u, v in graph.edges():
        iu, iv = idx[u], idx[v]
        adj[iu].append(iv)
        adj[iv].append(iu)

    dsu = DSU(n)
    gcc_after = [0.0] * (n + 1)
    largest_after = [0] * (n + 1)
    for pos in range(n - 1, -1, -1):
        ii = idx[order[pos]]
        dsu.activate(ii)
        for jj in adj[ii]:
            dsu.union(ii, jj)
        largest_after[pos] = dsu.largest
        gcc_after[pos] = dsu.largest / n if n else 0.0

    r_percent = 100.0 * sum(gcc_after[1:]) / n if n else 0.0
    rows = [
        {
            "step": step,
            "removal_ratio": step / n if n else 0.0,
            "GCC": gcc_after[step],
            "largest_component_nodes": largest_after[step],
        }
        for step in range(1, n + 1)
    ]
    return r_percent, rows


def native_candidates(method: str, dataset: str) -> list[Path]:
    folders = {
        "CI": NATIVE_ROOT / "CI",
        "CoreHD": NATIVE_ROOT / "CoreHD",
        "MinSum": NATIVE_ROOT / "MinSum",
        "BPD": NATIVE_ROOT / "BPD" / "uniform_cost",
        "GND": NATIVE_ROOT / "GND" / "uniform_cost",
    }
    aliases = {"Powerlaw_500": ["Powerlaw_500", "Powerlaw"]}
    names = [dataset, *aliases.get(dataset, [])]
    folder = folders[method]
    return [folder / f"{name}.txt" for name in names]


@dataclass(frozen=True)
class MethodSpec:
    method: str
    order_func: Callable[[nx.Graph], list[Any]]


METHODS = [
    MethodSpec("CI", lambda graph: ci_order(graph, rate=None)),
    MethodSpec("MinSum", lambda graph: minsum_order(graph, rate=None)),
    MethodSpec("BPD", lambda graph: bpd_order(graph, rate=None)),
    MethodSpec("CoreHD", lambda graph: corehd_fast_order(graph, rate=None)),
    MethodSpec("GND", lambda graph: gnd_order(graph, rate=None)),
]


def load_order(spec: MethodSpec, dataset: str, graph: nx.Graph) -> tuple[list[Any], str, str]:
    for path in native_candidates(spec.method, dataset):
        if path.exists():
            raw = parse_order_file(path)
            _clean, info, status = validate_order(graph, raw)
            if status == "ok":
                return raw, "external_complete_sequence", str(path)
            detail = (
                f"{path}; rejected_native_sequence "
                f"missing={info['missing_count']} extra={info['extra_count']} duplicates={info['duplicate_count']}"
            )
            break
    else:
        detail = ""
    suffix = f"; {detail}" if detail else ""
    return list(spec.order_func(graph.copy())), "local_clean_room_algorithm", f"baselines.{spec.method}{suffix}"
    return list(spec.order_func(graph.copy())), "local_clean_room_algorithm", f"baselines.{spec.order_func}"


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def reset_output_dir() -> None:
    resolved = OUT_DIR.resolve()
    project = PROJECT.resolve()
    if project not in resolved.parents:
        raise RuntimeError(f"refusing to clear output outside project: {resolved}")
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    GCC_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    reset_output_dir()
    graphs = {name: read_graph(name) for name in DATASETS_12}
    per_graph: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for spec in METHODS:
        print(f"[method] {spec.method}", flush=True)
        for dataset, graph in graphs.items():
            print(f"  [dataset] {dataset}", flush=True)
            started = time.perf_counter()
            status = "ok"
            reason = ""
            source_kind = ""
            source_detail = ""
            validation: dict[str, Any]
            try:
                raw_order, source_kind, source_detail = load_order(spec, dataset, graph)
                order_time_s = time.perf_counter() - started
                clean_order, validation, validation_status = validate_order(graph, raw_order)
                if validation_status != "ok":
                    status = "rejected"
                    reason = "sequence_not_complete_unique_exact_node_set"
                    raise ValueError(reason)
                r_percent, curve = classic_gcc_curve(graph, clean_order)
                curve_rows = [{"dataset": dataset, "method": spec.method, **row} for row in curve]
                curve_path = GCC_DIR / dataset / f"{spec.method}.csv"
                write_csv(curve_path, curve_rows)
            except Exception as exc:
                if status == "ok":
                    status = "unavailable"
                    reason = repr(exc)
                order_time_s = time.perf_counter() - started
                validation = {
                    "raw_len": "",
                    "clean_len": "",
                    "unique_valid_nodes": "",
                    "graph_nodes": graph.number_of_nodes(),
                    "missing_count": "",
                    "extra_count": "",
                    "duplicate_count": "",
                    "missing_preview": "",
                    "extra_preview": "",
                    "duplicate_preview": "",
                }
                r_percent = float("nan")
                curve_path = Path("")
                rejected.append(
                    {
                        "dataset": dataset,
                        "method": spec.method,
                        "status": status,
                        "reason": reason,
                        "source_kind": source_kind,
                        "source_detail": source_detail,
                    }
                )

            per_graph.append(
                {
                    "dataset": dataset,
                    "method": spec.method,
                    "group": "native_strong_baseline" if spec.method in {"MinSum", "BPD", "GND"} else "native_baseline",
                    "status": status,
                    "reason": reason,
                    "nodes": graph.number_of_nodes(),
                    "edges": graph.number_of_edges(),
                    "classic_R_percent": r_percent,
                    "classic_R_fraction": r_percent / 100.0 if status == "ok" else float("nan"),
                    "order_time_s": order_time_s,
                    "gcc_sequence_path": str(curve_path) if status == "ok" else "",
                    "source_kind": source_kind,
                    "source_detail": source_detail,
                    **validation,
                }
            )
            manifest.append(
                {
                    "dataset": dataset,
                    "method": spec.method,
                    "status": status,
                    "source_kind": source_kind,
                    "source_detail": source_detail,
                    "nodes": graph.number_of_nodes(),
                    "raw_len": validation.get("raw_len", ""),
                    "clean_len": validation.get("clean_len", ""),
                    "missing_count": validation.get("missing_count", ""),
                    "extra_count": validation.get("extra_count", ""),
                    "duplicate_count": validation.get("duplicate_count", ""),
                }
            )

    per_graph_df = pd.DataFrame(per_graph)
    per_graph_df.to_csv(OUT_DIR / "per_graph_classic_r.csv", index=False, encoding="utf-8-sig")
    ok = per_graph_df[per_graph_df["status"].eq("ok")].copy()
    mean_df = (
        ok.groupby(["method", "group"], as_index=False)
        .agg(
            datasets=("dataset", "nunique"),
            mean_classic_R_percent=("classic_R_percent", "mean"),
            mean_classic_R_fraction=("classic_R_fraction", "mean"),
            mean_order_time_s=("order_time_s", "mean"),
        )
        .sort_values(["mean_classic_R_percent", "mean_order_time_s"], ascending=[True, True])
    )
    mean_df["complete_12_graphs"] = mean_df["datasets"].eq(len(DATASETS_12))
    mean_df.to_csv(OUT_DIR / "method_mean_classic_r.csv", index=False, encoding="utf-8-sig")
    write_csv(OUT_DIR / "sequence_input_manifest.csv", manifest)
    write_csv(OUT_DIR / "unavailable_or_rejected_inputs.csv", rejected)
    write_csv(
        OUT_DIR / "crime_acceptance_check.csv",
        [
            {
                "method": method,
                "target_prefix": target,
                "classic_R_percent": float(
                    per_graph_df[
                        per_graph_df["dataset"].eq("crime")
                        & per_graph_df["method"].eq(method)
                        & per_graph_df["status"].eq("ok")
                    ]["classic_R_percent"].iloc[0]
                ),
            }
            for method, target in [
                ("CI", "12.43"),
                ("MinSum", "13.83"),
                ("BPD", "13.95"),
                ("CoreHD", "11.33"),
                ("GND", "13.81"),
            ]
        ],
    )
    (OUT_DIR / "run_manifest.json").write_text(
        json.dumps(
            {
                "metric": "classic_R_percent = 100 * sum_{k=1..N} GCC_k / N",
                "datasets": DATASETS_12,
                "methods": [spec.method for spec in METHODS],
                "network_dir": str(NETWORK_DIR),
                "native_sequence_root": str(NATIVE_ROOT),
                "output_policy": "output directory is cleared before recomputation",
                "maxcc_policy": "MaxCCList*.txt files are GCC traces only and are not used as deletion orders",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[done] {OUT_DIR}", flush=True)
    print(mean_df[["method", "datasets", "mean_classic_R_percent", "complete_12_graphs"]].to_string(index=False))


if __name__ == "__main__":
    main()
