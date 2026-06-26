# -*- coding: utf-8 -*-
"""Native influence-maximization baselines under the IC model.

The algorithms here are intentionally small and dependency-light, but they are
real IM baselines: Monte-Carlo greedy, CELF, DegreeDiscount-IC, and fixed-sample
reverse-reachable-set greedy.  They are not network-dismantling proxies.
"""

from __future__ import annotations

import heapq
import math
import random
from collections import defaultdict
from collections.abc import Hashable, Iterable
from typing import Any

import networkx as nx


Node = Hashable
Adj = dict[Node, list[tuple[Node, float]]]


def _stable_key(node: Any) -> str:
    return f"{type(node).__name__}:{node!r}"


def _edge_probability(data: dict[str, Any], fallback: float) -> float:
    for key in ("p", "prob", "probability", "weight"):
        if key in data:
            try:
                value = float(data[key])
            except (TypeError, ValueError):
                continue
            return min(1.0, max(0.0, value))
    return fallback


def _constant_adjacency(graph: nx.Graph, p: float) -> Adj:
    if graph.is_directed():
        return {
            u: [(v, _edge_probability(data, p)) for _, v, data in graph.out_edges(u, data=True)]
            for u in graph.nodes()
        }
    adj: Adj = {u: [] for u in graph.nodes()}
    for u, v, data in graph.edges(data=True):
        prob = _edge_probability(data, p)
        adj[u].append((v, prob))
        adj[v].append((u, prob))
    return adj


def _weighted_cascade_adjacency(graph: nx.Graph) -> Adj:
    if graph.is_directed():
        indeg = dict(graph.in_degree())
        return {
            u: [
                (v, _edge_probability(data, 1.0 / max(1, indeg.get(v, 1))))
                for _, v, data in graph.out_edges(u, data=True)
            ]
            for u in graph.nodes()
        }
    degree = dict(graph.degree())
    adj: Adj = {u: [] for u in graph.nodes()}
    for u, v, data in graph.edges(data=True):
        adj[u].append((v, _edge_probability(data, 1.0 / max(1, degree.get(v, 1)))))
        adj[v].append((u, _edge_probability(data, 1.0 / max(1, degree.get(u, 1)))))
    return adj


def make_ic_adjacency(graph: nx.Graph, p: float = 0.1, weighted_cascade: bool = False) -> Adj:
    """Return directed IC adjacency with edge activation probabilities."""
    return _weighted_cascade_adjacency(graph) if weighted_cascade else _constant_adjacency(graph, p)


def run_independent_cascade(adj: Adj, seeds: list[Node], rng: random.Random) -> set[Node]:
    active = set(seeds)
    frontier = list(seeds)
    while frontier:
        nxt: list[Node] = []
        for u in frontier:
            for v, prob in adj.get(u, []):
                if v not in active and rng.random() <= prob:
                    active.add(v)
                    nxt.append(v)
        frontier = nxt
    return active


def estimate_ic_spread(adj: Adj, seeds: list[Node], simulations: int = 256, seed: int = 0) -> float:
    if not seeds:
        return 0.0
    total = 0
    for idx in range(max(1, simulations)):
        rng = random.Random(seed + idx)
        total += len(run_independent_cascade(adj, seeds, rng))
    return total / float(max(1, simulations))


def _lt_incoming(graph: nx.Graph) -> dict[Node, list[tuple[Node, float]]]:
    if graph.is_directed():
        incoming: dict[Node, list[tuple[Node, float]]] = {u: [] for u in graph.nodes()}
        indeg = dict(graph.in_degree())
        for u, v, data in graph.edges(data=True):
            weight = _edge_probability(data, 1.0 / max(1, indeg.get(v, 1)))
            incoming.setdefault(v, []).append((u, weight))
            incoming.setdefault(u, incoming.get(u, []))
        return incoming

    degree = dict(graph.degree())
    incoming = {u: [] for u in graph.nodes()}
    for u, v, data in graph.edges(data=True):
        incoming[u].append((v, _edge_probability(data, 1.0 / max(1, degree.get(u, 1)))))
        incoming[v].append((u, _edge_probability(data, 1.0 / max(1, degree.get(v, 1)))))
    return incoming


def run_linear_threshold(
    incoming: dict[Node, list[tuple[Node, float]]],
    seeds: list[Node],
    thresholds: dict[Node, float],
) -> set[Node]:
    active = set(seeds)
    changed = True
    while changed:
        changed = False
        for node, nbrs in incoming.items():
            if node in active:
                continue
            pressure = sum(weight for nbr, weight in nbrs if nbr in active)
            if pressure >= thresholds.get(node, 1.0):
                active.add(node)
                changed = True
    return active


def estimate_lt_spread(graph: nx.Graph, seeds: list[Node], simulations: int = 256, seed: int = 0) -> float:
    incoming = _lt_incoming(graph)
    if not seeds:
        return 0.0
    total = 0
    nodes = list(graph.nodes())
    for idx in range(max(1, simulations)):
        rng = random.Random(seed + idx)
        thresholds = {node: rng.random() for node in nodes}
        total += len(run_linear_threshold(incoming, seeds, thresholds))
    return total / float(max(1, simulations))


def _complete_order(graph: nx.Graph, selected: list[Node]) -> list[Node]:
    seen = set()
    order: list[Node] = []
    for node in selected:
        if node in graph and node not in seen:
            seen.add(node)
            order.append(node)
    rest = sorted((u for u in graph.nodes() if u not in seen), key=_stable_key)
    return order + rest


def greedy_mc_seed_order(
    graph: nx.Graph,
    k: int | None = None,
    *,
    p: float = 0.1,
    simulations: int = 256,
    weighted_cascade: bool = False,
    seed: int = 0,
) -> list[Node]:
    """Kempe-style greedy selection using Monte-Carlo IC spread estimates."""
    target = graph.number_of_nodes() if k is None else max(0, min(int(k), graph.number_of_nodes()))
    adj = make_ic_adjacency(graph, p=p, weighted_cascade=weighted_cascade)
    selected: list[Node] = []
    remaining = set(graph.nodes())
    current_spread = 0.0
    for step in range(target):
        best_node = None
        best_gain = float("-inf")
        for node in sorted(remaining, key=_stable_key):
            spread = estimate_ic_spread(adj, selected + [node], simulations=simulations, seed=seed + 1009 * step)
            gain = spread - current_spread
            if gain > best_gain:
                best_gain = gain
                best_node = node
        if best_node is None:
            break
        selected.append(best_node)
        remaining.remove(best_node)
        current_spread += best_gain
    return _complete_order(graph, selected)


def celf_seed_order(
    graph: nx.Graph,
    k: int | None = None,
    *,
    p: float = 0.1,
    simulations: int = 256,
    weighted_cascade: bool = False,
    seed: int = 0,
) -> list[Node]:
    """CELF lazy-forward greedy under the IC model."""
    target = graph.number_of_nodes() if k is None else max(0, min(int(k), graph.number_of_nodes()))
    adj = make_ic_adjacency(graph, p=p, weighted_cascade=weighted_cascade)
    heap: list[tuple[float, str, Node, int]] = []
    for node in graph.nodes():
        spread = estimate_ic_spread(adj, [node], simulations=simulations, seed=seed)
        heapq.heappush(heap, (-spread, _stable_key(node), node, 0))

    selected: list[Node] = []
    selected_set: set[Node] = set()
    current_spread = 0.0
    while heap and len(selected) < target:
        _, _, node, last_updated = heapq.heappop(heap)
        if node in selected_set:
            continue
        if last_updated == len(selected):
            selected.append(node)
            selected_set.add(node)
            current_spread = estimate_ic_spread(adj, selected, simulations=simulations, seed=seed)
            continue
        spread = estimate_ic_spread(adj, selected + [node], simulations=simulations, seed=seed)
        gain = spread - current_spread
        heapq.heappush(heap, (-gain, _stable_key(node), node, len(selected)))
    return _complete_order(graph, selected)


def celfpp_seed_order(
    graph: nx.Graph,
    k: int | None = None,
    *,
    p: float = 0.1,
    simulations: int = 256,
    weighted_cascade: bool = False,
    seed: int = 0,
) -> list[Node]:
    """CELF++-style lazy greedy under IC.

    This implementation follows the CELF++ idea of caching the currently best
    second node for each candidate.  It keeps the same selected seeds as greedy
    on small graphs when the Monte-Carlo estimator is fixed, but it is written
    for clarity rather than speed.
    """
    target = graph.number_of_nodes() if k is None else max(0, min(int(k), graph.number_of_nodes()))
    adj = make_ic_adjacency(graph, p=p, weighted_cascade=weighted_cascade)
    nodes = sorted(graph.nodes(), key=_stable_key)
    if target <= 0:
        return _complete_order(graph, [])

    first_spread = {u: estimate_ic_spread(adj, [u], simulations=simulations, seed=seed) for u in nodes}
    first = max(nodes, key=lambda u: (first_spread[u], _stable_key(u)))
    selected = [first]
    selected_set = {first}
    current_spread = first_spread[first]

    if target == 1:
        return _complete_order(graph, selected)

    heap: list[tuple[float, str, Node, int, Node | None, float]] = []
    for node in nodes:
        if node == first:
            continue
        spread = estimate_ic_spread(adj, selected + [node], simulations=simulations, seed=seed)
        heapq.heappush(heap, (-(spread - current_spread), _stable_key(node), node, 1, first, spread))

    while heap and len(selected) < target:
        neg_gain, _, node, last_updated, prev_best, pair_spread = heapq.heappop(heap)
        if node in selected_set:
            continue
        if last_updated == len(selected) and prev_best == selected[-1]:
            selected.append(node)
            selected_set.add(node)
            current_spread = pair_spread if len(selected) == 2 else current_spread - neg_gain
            continue

        spread = estimate_ic_spread(adj, selected + [node], simulations=simulations, seed=seed)
        gain = spread - current_spread
        heapq.heappush(heap, (-gain, _stable_key(node), node, len(selected), selected[-1], spread))
    return _complete_order(graph, selected)


def degree_discount_ic_seed_order(graph: nx.Graph, k: int | None = None, *, p: float = 0.01) -> list[Node]:
    """Chen et al. DegreeDiscount-IC heuristic for small uniform IC probability."""
    h = nx.DiGraph(graph) if graph.is_directed() else nx.Graph(graph)
    target = h.number_of_nodes() if k is None else max(0, min(int(k), h.number_of_nodes()))
    degree = dict(h.out_degree() if h.is_directed() else h.degree())
    selected: list[Node] = []
    selected_set: set[Node] = set()
    t = {u: 0 for u in h.nodes()}
    dd = {u: float(degree.get(u, 0)) for u in h.nodes()}
    for _ in range(target):
        candidates = [u for u in h.nodes() if u not in selected_set]
        if not candidates:
            break
        node = max(candidates, key=lambda u: (dd[u], degree.get(u, 0), _stable_key(u)))
        selected.append(node)
        selected_set.add(node)
        neighbors = h.successors(node) if h.is_directed() else h.neighbors(node)
        for v in neighbors:
            if v in selected_set:
                continue
            t[v] += 1
            d = degree.get(v, 0)
            dd[v] = d - 2 * t[v] - (d - t[v]) * t[v] * p
    return _complete_order(graph, selected)


def _maximum_probability_paths(adj: Adj, source: Node, theta: float, blocked: set[Node]) -> dict[Node, tuple[float, list[Node]]]:
    best: dict[Node, float] = {source: 1.0}
    paths: dict[Node, list[Node]] = {source: [source]}
    heap: list[tuple[float, str, Node]] = [(-1.0, _stable_key(source), source)]
    while heap:
        neg_prob, _, node = heapq.heappop(heap)
        prob = -neg_prob
        if prob < best.get(node, 0.0):
            continue
        for nbr, edge_prob in adj.get(node, []):
            if nbr in blocked or edge_prob <= 0.0:
                continue
            candidate = prob * edge_prob
            if candidate < theta:
                continue
            if candidate > best.get(nbr, 0.0):
                best[nbr] = candidate
                paths[nbr] = paths[node] + [nbr]
                heapq.heappush(heap, (-candidate, _stable_key(nbr), nbr))
    return {node: (prob, paths[node]) for node, prob in best.items()}


def _mia_expected_spread(adj: Adj, seeds: Iterable[Node], theta: float) -> float:
    seed_set = set(seeds)
    total = float(len(seed_set))
    all_nodes = set(adj)
    for nbrs in adj.values():
        for v, _ in nbrs:
            all_nodes.add(v)
    for target in all_nodes - seed_set:
        inactive_prob = 1.0
        for source in seed_set:
            paths = _maximum_probability_paths(adj, source, theta, seed_set - {source})
            if target in paths:
                inactive_prob *= 1.0 - paths[target][0]
        total += 1.0 - inactive_prob
    return total


def mia_seed_order(
    graph: nx.Graph,
    k: int | None = None,
    *,
    p: float = 0.1,
    theta: float = 1e-3,
    weighted_cascade: bool = False,
) -> list[Node]:
    """MIA/PMIA-family maximum-influence-arborescence greedy reproduction.

    This is a clear Python3 reproduction of the Chen et al. MIA idea: approximate
    spread through maximum-probability paths above a threshold, then greedily
    select by marginal MIA spread.  It is slower than optimized PMIA but follows
    the same native IC approximation family.
    """
    target = graph.number_of_nodes() if k is None else max(0, min(int(k), graph.number_of_nodes()))
    adj = make_ic_adjacency(graph, p=p, weighted_cascade=weighted_cascade)
    selected: list[Node] = []
    remaining = set(graph.nodes())
    current = 0.0
    for _ in range(target):
        best_node = None
        best_gain = float("-inf")
        for node in sorted(remaining, key=_stable_key):
            spread = _mia_expected_spread(adj, selected + [node], theta)
            gain = spread - current
            if gain > best_gain:
                best_node = node
                best_gain = gain
        if best_node is None:
            break
        selected.append(best_node)
        remaining.remove(best_node)
        current += best_gain
    return _complete_order(graph, selected)


def _sample_rr_set(reverse_adj: Adj, nodes: list[Node], rng: random.Random) -> set[Node]:
    root = rng.choice(nodes)
    rr = {root}
    frontier = [root]
    while frontier:
        nxt: list[Node] = []
        for v in frontier:
            for u, prob in reverse_adj.get(v, []):
                if u not in rr and rng.random() <= prob:
                    rr.add(u)
                    nxt.append(u)
        frontier = nxt
    return rr


def rr_greedy_seed_order(
    graph: nx.Graph,
    k: int | None = None,
    *,
    p: float = 0.1,
    rr_sets: int = 2048,
    weighted_cascade: bool = False,
    seed: int = 0,
) -> list[Node]:
    """Fixed-sample RIS/RR-set greedy baseline for IC influence maximization."""
    target = graph.number_of_nodes() if k is None else max(0, min(int(k), graph.number_of_nodes()))
    adj = make_ic_adjacency(graph, p=p, weighted_cascade=weighted_cascade)
    reverse_adj: Adj = {u: [] for u in graph.nodes()}
    for u, nbrs in adj.items():
        for v, prob in nbrs:
            reverse_adj.setdefault(v, []).append((u, prob))
            reverse_adj.setdefault(u, reverse_adj.get(u, []))

    nodes = list(graph.nodes())
    rng = random.Random(seed)
    samples = [_sample_rr_set(reverse_adj, nodes, rng) for _ in range(max(1, rr_sets))]
    uncovered = set(range(len(samples)))
    selected: list[Node] = []
    selected_set: set[Node] = set()
    for _ in range(target):
        best_node = None
        best_cover: set[int] = set()
        for node in sorted((u for u in nodes if u not in selected_set), key=_stable_key):
            cover = {idx for idx in uncovered if node in samples[idx]}
            if len(cover) > len(best_cover):
                best_node = node
                best_cover = cover
        if best_node is None:
            break
        selected.append(best_node)
        selected_set.add(best_node)
        uncovered -= best_cover
    return _complete_order(graph, selected)


def _log_binom(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    k = min(k, n - k)
    return sum(math.log(n - i) - math.log(i + 1) for i in range(k))


def _node_selection_from_rr(samples: list[set[Node]], nodes: list[Node], k: int) -> tuple[list[Node], int]:
    node_to_rr: dict[Node, set[int]] = defaultdict(set)
    for idx, rr in enumerate(samples):
        for node in rr:
            node_to_rr[node].add(idx)

    selected: list[Node] = []
    covered: set[int] = set()
    for _ in range(max(0, min(k, len(nodes)))):
        best = None
        best_gain_set: set[int] = set()
        for node in sorted((u for u in nodes if u not in selected), key=_stable_key):
            gain_set = node_to_rr.get(node, set()) - covered
            if len(gain_set) > len(best_gain_set):
                best = node
                best_gain_set = gain_set
        if best is None:
            break
        selected.append(best)
        covered.update(best_gain_set)
    return selected, len(covered)


def imm_seed_order(
    graph: nx.Graph,
    k: int | None = None,
    *,
    p: float = 0.1,
    epsilon: float = 0.5,
    ell: float = 1.0,
    weighted_cascade: bool = False,
    seed: int = 0,
    max_rr_sets: int = 20000,
) -> list[Node]:
    """Python3 IMM-style reproduction using RR sets.

    This keeps the IMM two-phase shape and sample-size formulas, but caps the
    number of RR sets so it remains usable in a local research harness.  Use
    official C++ IMM/OPIM-C for theorem-level large-scale comparisons.
    """
    n = graph.number_of_nodes()
    target = n if k is None else max(0, min(int(k), n))
    if n == 0 or target == 0:
        return _complete_order(graph, [])

    adj = make_ic_adjacency(graph, p=p, weighted_cascade=weighted_cascade)
    reverse_adj: Adj = {u: [] for u in graph.nodes()}
    for u, nbrs in adj.items():
        reverse_adj.setdefault(u, reverse_adj.get(u, []))
        for v, prob in nbrs:
            reverse_adj.setdefault(v, []).append((u, prob))

    nodes = list(graph.nodes())
    rng = random.Random(seed)
    logn = math.log(max(2, n))
    logcnk = _log_binom(n, target)
    eps = max(0.05, float(epsilon))
    eps_prime = math.sqrt(2.0) * eps
    lambda_prime = (2.0 + 2.0 * eps_prime / 3.0) * (logcnk + ell * logn + math.log(max(2.0, math.log(max(3, n), 2)))) * n / (eps_prime**2)

    lower_bound = 1.0
    samples: list[set[Node]] = []
    for i in range(1, max(2, int(math.log(max(2, n), 2))) + 1):
        x = n / (2**i)
        theta_i = min(max_rr_sets, int(math.ceil(lambda_prime / max(x, 1e-9))))
        while len(samples) < theta_i:
            samples.append(_sample_rr_set(reverse_adj, nodes, rng))
        _, covered = _node_selection_from_rr(samples, nodes, target)
        spread_est = n * covered / float(max(1, len(samples)))
        if spread_est >= (1.0 + eps_prime) * x:
            lower_bound = max(1.0, spread_est / (1.0 + eps_prime))
            break

    alpha = math.sqrt(ell * logn + math.log(2.0))
    beta = math.sqrt((1.0 - 1.0 / math.e) * (logcnk + ell * logn + math.log(2.0)))
    lambda_star = 2.0 * n * ((1.0 - 1.0 / math.e) * alpha + beta) ** 2 / (eps**2)
    theta = min(max_rr_sets, int(math.ceil(lambda_star / lower_bound)))
    while len(samples) < theta:
        samples.append(_sample_rr_set(reverse_adj, nodes, rng))
    selected, _ = _node_selection_from_rr(samples, nodes, target)
    return _complete_order(graph, selected)


def _greedy_dominating_set(graph: nx.Graph) -> list[Node]:
    dominated: set[Node] = set()
    selected: list[Node] = []
    nodes = set(graph.nodes())
    while dominated != nodes:
        best = max(
            (u for u in nodes if u not in selected),
            key=lambda u: (len(({u} | set(graph.neighbors(u))) - dominated), graph.degree[u], _stable_key(u)),
        )
        selected.append(best)
        dominated.add(best)
        dominated.update(graph.neighbors(best))
    return selected


def _uncorrelated_degree(graph: nx.Graph, node: Node, selected: set[Node]) -> int:
    return sum(1 for nbr in graph.neighbors(node) if nbr not in selected)


def domim_seed_order(
    graph: nx.Graph,
    k: int | None = None,
    *,
    p: float = 0.1,
    simulations: int = 128,
    alpha: float = 0.15,
    iterations: int = 128,
    seed: int = 0,
) -> list[Node]:
    """DomIM-style dominating-set local search reproduction.

    Based on Zhu, Yang, and Xu, Frontiers in Physics 2021.  The original paper
    starts from a dominating-set heuristic, constructs a candidate set via
    uncorrelated degree, and improves the seed set with local exchanges.
    """
    h = nx.Graph(graph)
    target = h.number_of_nodes() if k is None else max(0, min(int(k), h.number_of_nodes()))
    if target == 0:
        return _complete_order(h, [])

    dom = _greedy_dominating_set(h)
    if len(dom) < target:
        selected = list(dom)
        selected_set = set(selected)
        rest = sorted(
            (u for u in h.nodes() if u not in selected_set),
            key=lambda u: (_uncorrelated_degree(h, u, selected_set), h.degree[u], _stable_key(u)),
            reverse=True,
        )
        selected.extend(rest[: target - len(selected)])
    else:
        selected = sorted(dom, key=lambda u: (_uncorrelated_degree(h, u, set(dom)), h.degree[u], _stable_key(u)), reverse=True)[:target]

    selected_set = set(selected)
    candidate_size = max(target, int(alpha * h.number_of_nodes()))
    candidates = sorted(
        (u for u in h.nodes() if u not in selected_set),
        key=lambda u: (_uncorrelated_degree(h, u, selected_set), h.degree[u], _stable_key(u)),
        reverse=True,
    )[:candidate_size]
    candidate_set = set(candidates)

    adj = make_ic_adjacency(h, p=p)
    best = list(selected)
    best_score = estimate_ic_spread(adj, best, simulations=simulations, seed=seed)
    current = list(selected)
    current_score = best_score
    rng = random.Random(seed)

    for it in range(max(0, iterations)):
        if not candidate_set:
            break
        current_set = set(current)
        remove_node = min(current, key=lambda u: (_uncorrelated_degree(h, u, current_set), _stable_key(u)))
        add_node = rng.choice(sorted(candidate_set, key=_stable_key))
        trial = [u for u in current if u != remove_node] + [add_node]
        trial_score = estimate_ic_spread(adj, trial, simulations=simulations, seed=seed + 1009 + it)
        if trial_score >= current_score:
            current = trial
            current_score = trial_score
            candidate_set.discard(add_node)
            candidate_set.add(remove_node)
            if trial_score > best_score:
                best = list(trial)
                best_score = trial_score
    return _complete_order(h, best)


def cluster_greedy_lt_seed_order(
    graph: nx.Graph,
    k: int | None = None,
    *,
    simulations: int = 128,
    seed: int = 0,
) -> list[Node]:
    """ClusterGreedy-style LT reproduction.

    Based on Agra and Samuco, Information 2024.  The framework partitions the
    graph, runs greedy inside each induced cluster, then combines cluster-level
    seed budgets through a knapsack/ILP-equivalent dynamic program.
    """
    h = nx.Graph(graph)
    target = h.number_of_nodes() if k is None else max(0, min(int(k), h.number_of_nodes()))
    if target == 0:
        return _complete_order(h, [])

    if h.number_of_edges() == 0:
        clusters = [{u} for u in sorted(h.nodes(), key=_stable_key)]
    else:
        try:
            clusters = [set(c) for c in nx.community.greedy_modularity_communities(h)]
        except Exception:
            clusters = [set(c) for c in nx.connected_components(h)]
    clusters = [c for c in clusters if c]

    options: list[list[tuple[float, list[Node]]]] = []
    for idx, cluster in enumerate(clusters):
        sub = h.subgraph(cluster).copy()
        limit = min(target, sub.number_of_nodes())
        local_options: list[tuple[float, list[Node]]] = [(0.0, [])]
        selected: list[Node] = []
        current_score = 0.0
        for budget in range(1, limit + 1):
            remaining = [u for u in sub.nodes() if u not in selected]
            best_node = max(
                remaining,
                key=lambda u: (
                    estimate_lt_spread(sub, selected + [u], simulations=simulations, seed=seed + idx * 1009 + budget),
                    sub.degree[u],
                    _stable_key(u),
                ),
            )
            selected.append(best_node)
            current_score = estimate_lt_spread(sub, selected, simulations=simulations, seed=seed + idx * 1009 + budget)
            local_options.append((current_score, list(selected)))
        options.append(local_options)

    dp: list[tuple[float, list[Node]]] = [(0.0, [])] + [(-1.0, []) for _ in range(target)]
    for local_options in options:
        nxt = list(dp)
        for used in range(target + 1):
            if dp[used][0] < 0:
                continue
            for extra, (score, nodes) in enumerate(local_options):
                if used + extra > target:
                    break
                value = dp[used][0] + score
                if value > nxt[used + extra][0]:
                    nxt[used + extra] = (value, dp[used][1] + nodes)
        dp = nxt

    selected = dp[target][1]
    if len(selected) < target:
        selected_set = set(selected)
        rest = sorted((u for u in h.nodes() if u not in selected_set), key=lambda u: (h.degree[u], _stable_key(u)), reverse=True)
        selected.extend(rest[: target - len(selected)])
    return _complete_order(h, selected[:target])


__all__ = [
    "make_ic_adjacency",
    "run_independent_cascade",
    "estimate_ic_spread",
    "run_linear_threshold",
    "estimate_lt_spread",
    "greedy_mc_seed_order",
    "celf_seed_order",
    "celfpp_seed_order",
    "degree_discount_ic_seed_order",
    "mia_seed_order",
    "rr_greedy_seed_order",
    "imm_seed_order",
    "domim_seed_order",
    "cluster_greedy_lt_seed_order",
]
