# -*- coding: utf-8 -*-
"""Independent-cascade online proxy metrics for influence maximization."""

from __future__ import annotations

import random
from typing import Any

import networkx as nx


def build_fixed_live_edge_worlds(
    graph: nx.Graph,
    worlds: int = 1024,
    p: float = 0.1,
    seed: int = 20260626,
) -> list[dict[Any, list[Any]]]:
    edges = list(graph.edges())
    out: list[dict[Any, list[Any]]] = []
    for idx in range(max(1, int(worlds))):
        rng = random.Random(seed + idx)
        adj: dict[Any, list[Any]] = {u: [] for u in graph.nodes()}
        for u, v in edges:
            if rng.random() <= p:
                adj[u].append(v)
                adj[v].append(u)
        out.append(adj)
    return out


def _reverse_adjacency(graph: nx.Graph, p: float) -> dict[Any, list[tuple[Any, float]]]:
    adj: dict[Any, list[tuple[Any, float]]] = {u: [] for u in graph.nodes()}
    for u, v in graph.edges():
        adj[u].append((v, p))
        adj[v].append((u, p))
    return adj


def _sample_rr_set(reverse_adj: dict[Any, list[tuple[Any, float]]], nodes: list[Any], rng: random.Random) -> set[Any]:
    root = rng.choice(nodes)
    rr = {root}
    frontier = [root]
    while frontier:
        nxt: list[Any] = []
        for node in frontier:
            for nbr, prob in reverse_adj.get(node, []):
                if nbr not in rr and rng.random() <= prob:
                    rr.add(nbr)
                    nxt.append(nbr)
        frontier = nxt
    return rr


def build_fixed_rr_sets(
    graph: nx.Graph,
    rr_sets: int = 1024,
    p: float = 0.1,
    seed: int = 20260626,
) -> list[set[Any]]:
    nodes = list(graph.nodes())
    if not nodes:
        return []
    rng = random.Random(seed)
    reverse_adj = _reverse_adjacency(graph, p)
    return [_sample_rr_set(reverse_adj, nodes, rng) for _ in range(max(1, int(rr_sets)))]


def fixed_live_edge_spread(graph: nx.Graph, seeds: list[Any], worlds: list[dict[Any, list[Any]]]) -> float:
    if graph.number_of_nodes() == 0:
        return 0.0
    seed_set = set(seeds)
    total = 0
    for adj in worlds:
        active = set(seed_set)
        frontier = list(seed_set)
        while frontier:
            nxt: list[Any] = []
            for node in frontier:
                for nbr in adj.get(node, []):
                    if nbr not in active:
                        active.add(nbr)
                        nxt.append(nbr)
            frontier = nxt
        total += len(active)
    return float(total / max(1, len(worlds)) / max(1, graph.number_of_nodes()))


def rr_coverage(seeds: list[Any], rr_sets: list[set[Any]]) -> float:
    if not rr_sets:
        return 0.0
    seed_set = set(seeds)
    covered = sum(1 for rr in rr_sets if seed_set.intersection(rr))
    return float(covered / len(rr_sets))
