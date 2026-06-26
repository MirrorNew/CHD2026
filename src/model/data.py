# -*- coding: utf-8 -*-
"""Graph loading and synthetic graph generation."""

from __future__ import annotations

import math
from pathlib import Path

import networkx as nx
import numpy as np

from .config import BENCHMARK_ROOT


def generate_powerlaw_network(n: int, gamma: float = 2.5, seed: int = 42, k_min: int = 2) -> nx.Graph:
    rng = np.random.default_rng(seed)
    k_max = max(k_min + 1, int(math.sqrt(n) * 4))
    degree_values = np.arange(k_min, k_max + 1)
    weights = np.array([k ** (-gamma) for k in degree_values], dtype=float)
    weights /= weights.sum()
    degrees = rng.choice(degree_values, size=n, replace=True, p=weights).astype(int).tolist()
    if sum(degrees) % 2 == 1:
        degrees[0] += 1
    graph = nx.configuration_model(degrees, seed=seed)
    graph = nx.Graph(graph)
    graph.remove_edges_from(nx.selfloop_edges(graph))
    graph = nx.convert_node_labels_to_integers(graph)
    if graph.number_of_nodes() > 0 and not nx.is_connected(graph):
        comps = [list(c) for c in nx.connected_components(graph)]
        for a, b in zip(comps[:-1], comps[1:]):
            graph.add_edge(a[0], b[0])
    return graph


def _connect_components(graph: nx.Graph) -> nx.Graph:
    graph = nx.Graph(graph)
    graph.remove_edges_from(nx.selfloop_edges(graph))
    graph = nx.convert_node_labels_to_integers(graph)
    if graph.number_of_nodes() > 0 and not nx.is_connected(graph):
        comps = [list(c) for c in nx.connected_components(graph)]
        for a, b in zip(comps[:-1], comps[1:]):
            graph.add_edge(a[0], b[0])
    return graph


def generate_community_proxy(n: int = 1000, seed: int = 23) -> nx.Graph:
    sizes = [250, 250, 250, 250]
    probs = [
        [0.028, 0.0015, 0.0008, 0.0010],
        [0.0015, 0.024, 0.0012, 0.0008],
        [0.0008, 0.0012, 0.026, 0.0015],
        [0.0010, 0.0008, 0.0015, 0.022],
    ]
    graph = nx.stochastic_block_model(sizes, probs, seed=seed)
    if graph.number_of_nodes() != n:
        graph = nx.convert_node_labels_to_integers(graph)
    return _connect_components(graph)


def generate_grid_small_world_proxy(n: int = 1200, seed: int = 31) -> nx.Graph:
    rows = 30
    cols = max(1, n // rows)
    graph = nx.grid_2d_graph(rows, cols)
    graph = nx.convert_node_labels_to_integers(graph)
    rng = np.random.default_rng(seed)
    target_shortcuts = max(1, n // 25)
    attempts = 0
    while target_shortcuts > 0 and attempts < n * 10:
        attempts += 1
        u = int(rng.integers(0, graph.number_of_nodes()))
        v = int(rng.integers(0, graph.number_of_nodes()))
        if u == v or graph.has_edge(u, v):
            continue
        graph.add_edge(u, v)
        target_shortcuts -= 1
    return _connect_components(graph)


def read_graph(dataset: str, benchmark_root: Path = BENCHMARK_ROOT) -> nx.Graph:
    if dataset == "Powerlaw_500":
        return generate_powerlaw_network(500, 2.5, seed=42)
    if dataset == "SynthPL500_g25_s11":
        return generate_powerlaw_network(500, 2.5, seed=11)
    if dataset == "SynthPL1000_g22_s17":
        return generate_powerlaw_network(1000, 2.2, seed=17)
    if dataset == "SynthComm1000_s23":
        return generate_community_proxy(1000, seed=23)
    if dataset == "SynthGridSW1200_s31":
        return generate_grid_small_world_proxy(1200, seed=31)
    candidates = [
        benchmark_root / f"{dataset}.txt",
        benchmark_root / "network" / f"{dataset}.edgelist",
        benchmark_root / f"{dataset}.edgelist",
    ]
    for path in candidates:
        if path.exists():
            graph = nx.read_edgelist(path, nodetype=int)
            graph = nx.Graph(graph)
            graph.remove_edges_from(nx.selfloop_edges(graph))
            return graph
    raise FileNotFoundError(f"No graph file found for {dataset} under {benchmark_root}")
