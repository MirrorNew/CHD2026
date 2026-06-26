# -*- coding: utf-8 -*-

from __future__ import annotations

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


def test_im_native_baselines_return_valid_seed_prefixes() -> None:
    graph = nx.read_edgelist(Path("src/dataset/smoke.edgelist"), nodetype=int, create_using=nx.Graph())
    methods = [
        degree_discount_ic_seed_order(graph, 3, p=0.1),
        greedy_mc_seed_order(graph, 3, p=0.1, simulations=8, seed=1),
        celf_seed_order(graph, 3, p=0.1, simulations=8, seed=1),
        celfpp_seed_order(graph, 3, p=0.1, simulations=8, seed=1),
        mia_seed_order(graph, 3, p=0.1, theta=0.001),
        rr_greedy_seed_order(graph, 3, p=0.1, rr_sets=64, seed=1),
        imm_seed_order(graph, 3, p=0.1, epsilon=0.5, seed=1, max_rr_sets=128),
        domim_seed_order(graph, 3, p=0.1, simulations=8, seed=1),
        cluster_greedy_lt_seed_order(graph, 3, simulations=8, seed=1),
    ]

    nodes = set(graph.nodes())
    for order in methods:
        assert len(order) == graph.number_of_nodes()
        assert set(order) == nodes
        assert len(set(order[:3])) == 3
