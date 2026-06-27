# -*- coding: utf-8 -*-
"""Reusable Linear Threshold evaluator for influence maximization.

The main evaluator follows the standard LT experimental setup used by IM
papers: each Monte-Carlo world samples one threshold per node from U[0, 1],
and all methods on the same graph can share the same worlds through the same
``base_seed`` and simulation index. For undirected unweighted graphs, each
active neighbor contributes 1 / degree(v) pressure to node v.
"""

from __future__ import annotations

import math
import random
import statistics
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable

import networkx as nx


@dataclass(frozen=True)
class LTSpreadResult:
    spread_mean: float
    spread_std: float
    spread_ci95: float
    normalized_spread: float
    simulations: int
    time_s: float


def _stable_key(node: Any) -> tuple[str, str]:
    return (type(node).__name__, repr(node))


def normalize_seed_order(graph: nx.Graph, raw: Iterable[Any] | None, k: int) -> tuple[list[Any], bool, int]:
    """Return up to k valid seeds, filling short outputs deterministically."""

    nodes = set(graph.nodes())
    out: list[Any] = []
    seen: set[Any] = set()
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
    valid_raw = 0 < len(out) <= k
    if len(out) < k:
        out.extend(sorted((node for node in nodes if node not in seen), key=_stable_key)[: k - len(out)])
    return out, valid_raw, len(raw_list)


def _indexed_graph(graph: nx.Graph) -> tuple[list[Any], dict[Any, int], list[list[int]], list[int]]:
    nodes = list(graph.nodes())
    index = {node: pos for pos, node in enumerate(nodes)}
    adj_sets: list[set[int]] = [set() for _ in nodes]
    for u, v in graph.edges():
        if u == v:
            continue
        iu = index[u]
        iv = index[v]
        adj_sets[iu].add(iv)
        adj_sets[iv].add(iu)
    adj = [list(values) for values in adj_sets]
    degree = [len(values) for values in adj]
    return nodes, index, adj, degree


def _spread_one_world(seed_idx: list[int], adj: list[list[int]], degree: list[int], thresholds: list[float]) -> int:
    active = bytearray(len(adj))
    active_neighbor_count = [0] * len(adj)
    queue: deque[int] = deque()
    total = 0
    for seed in seed_idx:
        if not active[seed]:
            active[seed] = 1
            queue.append(seed)
            total += 1
    while queue:
        node = queue.popleft()
        for nbr in adj[node]:
            if active[nbr]:
                continue
            active_neighbor_count[nbr] += 1
            if degree[nbr] and (active_neighbor_count[nbr] / degree[nbr]) >= thresholds[nbr]:
                active[nbr] = 1
                queue.append(nbr)
                total += 1
    return total


def evaluate_lt_spread(
    graph: nx.Graph,
    seeds: Iterable[Any],
    *,
    simulations: int = 4096,
    base_seed: int = 20260626,
) -> LTSpreadResult:
    """Estimate expected LT spread with random thresholds and common worlds."""

    started = time.perf_counter()
    n = graph.number_of_nodes()
    if n == 0:
        return LTSpreadResult(0.0, 0.0, 0.0, 0.0, max(1, int(simulations)), time.perf_counter() - started)

    _nodes, node_index, adj, degree = _indexed_graph(graph)
    seed_idx = [node_index[node] for node in seeds if node in node_index]
    if not seed_idx:
        elapsed = time.perf_counter() - started
        return LTSpreadResult(0.0, 0.0, 0.0, 0.0, max(1, int(simulations)), elapsed)

    runs = max(1, int(simulations))
    values: list[int] = []
    for sim in range(runs):
        rng = random.Random(base_seed + sim)
        thresholds = [rng.random() for _ in range(n)]
        values.append(_spread_one_world(seed_idx, adj, degree, thresholds))

    mean = statistics.fmean(values)
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    ci95 = 1.96 * std / math.sqrt(len(values)) if values else 0.0
    elapsed = time.perf_counter() - started
    return LTSpreadResult(
        spread_mean=float(mean),
        spread_std=float(std),
        spread_ci95=float(ci95),
        normalized_spread=float(mean / n),
        simulations=runs,
        time_s=float(elapsed),
    )


def evaluate_lt_spread_many(
    graph: nx.Graph,
    seeds_by_method: dict[str, Iterable[Any]],
    *,
    simulations: int = 4096,
    base_seed: int = 20260626,
) -> dict[str, LTSpreadResult]:
    """Evaluate many seed sets on the same graph with shared threshold worlds."""

    started = time.perf_counter()
    n = graph.number_of_nodes()
    runs = max(1, int(simulations))
    if not seeds_by_method:
        return {}
    if n == 0:
        elapsed = time.perf_counter() - started
        return {
            method: LTSpreadResult(0.0, 0.0, 0.0, 0.0, runs, elapsed / max(1, len(seeds_by_method)))
            for method in seeds_by_method
        }

    _nodes, node_index, adj, degree = _indexed_graph(graph)
    indexed_seeds = {
        method: [node_index[node] for node in seeds if node in node_index]
        for method, seeds in seeds_by_method.items()
    }
    values_by_method: dict[str, list[int]] = {method: [] for method in seeds_by_method}

    for sim in range(runs):
        rng = random.Random(base_seed + sim)
        thresholds = [rng.random() for _ in range(n)]
        for method, seed_idx in indexed_seeds.items():
            if seed_idx:
                values_by_method[method].append(_spread_one_world(seed_idx, adj, degree, thresholds))
            else:
                values_by_method[method].append(0)

    elapsed = time.perf_counter() - started
    per_method_time = elapsed / max(1, len(seeds_by_method))
    results: dict[str, LTSpreadResult] = {}
    for method, values in values_by_method.items():
        mean = statistics.fmean(values)
        std = statistics.pstdev(values) if len(values) > 1 else 0.0
        ci95 = 1.96 * std / math.sqrt(len(values)) if values else 0.0
        results[method] = LTSpreadResult(
            spread_mean=float(mean),
            spread_std=float(std),
            spread_ci95=float(ci95),
            normalized_spread=float(mean / n),
            simulations=runs,
            time_s=float(per_method_time),
        )
    return results
