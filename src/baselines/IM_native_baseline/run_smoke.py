# -*- coding: utf-8 -*-
"""Smoke runner for Python3 influence-maximization reproductions."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import networkx as nx

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from baselines.IM_native_baseline import (  # noqa: E402
    celf_seed_order,
    celfpp_seed_order,
    cluster_greedy_lt_seed_order,
    degree_discount_ic_seed_order,
    estimate_ic_spread,
    estimate_lt_spread,
    greedy_mc_seed_order,
    imm_seed_order,
    make_ic_adjacency,
    mia_seed_order,
    rr_greedy_seed_order,
    domim_seed_order,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", default=str(PROJECT_ROOT / "src" / "dataset" / "smoke.edgelist"))
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--p", type=float, default=0.1)
    parser.add_argument("--simulations", type=int, default=64)
    parser.add_argument("--eval-simulations", type=int, default=512)
    parser.add_argument("--rr-sets", type=int, default=512)
    parser.add_argument("--max-rr-sets", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    graph_path = Path(args.graph)
    graph = nx.read_edgelist(graph_path, nodetype=int, create_using=nx.Graph())
    adj = make_ic_adjacency(graph, p=args.p)
    methods = {
        "DegreeDiscountIC": degree_discount_ic_seed_order(graph, args.k, p=args.p)[: args.k],
        "MCGreedy": greedy_mc_seed_order(graph, args.k, p=args.p, simulations=args.simulations, seed=args.seed)[: args.k],
        "CELF": celf_seed_order(graph, args.k, p=args.p, simulations=args.simulations, seed=args.seed)[: args.k],
        "CELF++": celfpp_seed_order(graph, args.k, p=args.p, simulations=args.simulations, seed=args.seed)[: args.k],
        "MIA-PMIA-family": mia_seed_order(graph, args.k, p=args.p, theta=0.001)[: args.k],
        "RRGreedy": rr_greedy_seed_order(graph, args.k, p=args.p, rr_sets=args.rr_sets, seed=args.seed)[: args.k],
        "IMM-style": imm_seed_order(
            graph,
            args.k,
            p=args.p,
            epsilon=0.5,
            ell=1.0,
            seed=args.seed,
            max_rr_sets=args.max_rr_sets,
        )[: args.k],
        "DomIM-2021": domim_seed_order(graph, args.k, p=args.p, simulations=args.simulations, seed=args.seed)[: args.k],
    }

    rows = []
    print(
        f"graph={graph_path} nodes={graph.number_of_nodes()} edges={graph.number_of_edges()} "
        f"k={args.k} p={args.p} eval_sims={args.eval_simulations}"
    )
    for name, seeds in methods.items():
        spread = estimate_ic_spread(adj, seeds, simulations=args.eval_simulations, seed=123)
        row = {"method": name, "seeds": " ".join(map(str, seeds)), "spread": f"{spread:.6f}"}
        rows.append(row)
        print(f"{name}: seeds={seeds} spread={spread:.3f}")

    lt_seeds = cluster_greedy_lt_seed_order(graph, args.k, simulations=args.simulations, seed=args.seed)[: args.k]
    lt_spread = estimate_lt_spread(graph, lt_seeds, simulations=args.eval_simulations, seed=123)
    rows.append({"method": "ClusterGreedy-LT-2024", "seeds": " ".join(map(str, lt_seeds)), "spread": f"{lt_spread:.6f}"})
    print(f"ClusterGreedy-LT-2024: seeds={lt_seeds} lt_spread={lt_spread:.3f}")

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["method", "seeds", "spread"])
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
