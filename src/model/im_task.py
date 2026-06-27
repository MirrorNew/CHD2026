# -*- coding: utf-8 -*-
"""Influence-maximization task adapter for CHD stage search."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from metrics.IM_IC_evaluator import build_fixed_live_edge_worlds, build_fixed_rr_sets, fixed_live_edge_spread, rr_coverage

from .candidate import CandidateProgram, compile_candidate, make_program
from .config import PROJECT_ROOT


IM_FUNCTION_NAME = "seed_order"
IM_INTERFACE = "def seed_order(G, k):\n    return up_to_k_seed_nodes"

IM_ROOT_CODE = r"""
def seed_order(G, k):
    p = 0.1
    H = G.copy()
    target = max(0, min(int(k), H.number_of_nodes()))
    degree = dict(H.degree())
    selected = []
    selected_set = set()
    touched = {u: 0 for u in H.nodes()}
    discount = {u: float(degree.get(u, 0)) for u in H.nodes()}
    for _ in range(target):
        candidates = [u for u in H.nodes() if u not in selected_set]
        if not candidates:
            break
        node = max(candidates, key=lambda u: (discount.get(u, 0.0), degree.get(u, 0), str(u)))
        selected.append(node)
        selected_set.add(node)
        for nbr in H.neighbors(node):
            if nbr in selected_set:
                continue
            touched[nbr] = touched.get(nbr, 0) + 1
            d = degree.get(nbr, 0)
            t = touched[nbr]
            discount[nbr] = d - 2 * t - (d - t) * t * p
    return selected
""".strip()


IM_TASK_GUIDANCE = """
Influence maximization task:
- Write a deterministic NetworkX-compatible heuristic.
- Candidate contract: def seed_order(G, k): return up to k seed nodes.
- Seeds are evaluated on a fixed independent-cascade live-edge proxy graph.
- Improve normalized IC spread and RR coverage while keeping runtime low.
- Root reference is DegreeDiscount-IC.
""".strip()


IM_FORBIDDEN_GUIDANCE = """
Implementation guards:
- Do not read/write files, use subprocess/network calls, eval/exec, or external data.
- Avoid all-subset enumeration and repeated full Monte-Carlo simulation inside seed selection.
- Avoid all-pairs shortest paths, betweenness/PageRank, and unbounded BFS/DFS loops.
- Keep scans bounded on high-degree neighborhoods; use deterministic tie-breakers.
""".strip()


@dataclass
class IMOnlineArtifacts:
    graph: nx.Graph
    graph_source: str
    k: int
    live_edge_worlds: list[dict[Any, list[Any]]]
    rr_sets: list[set[Any]]
    p: float = 0.1
    seed: int = 20260626
    root_spread_ic: float = 0.0


def im_seed_budget(n: int) -> int:
    return max(3, min(12, int(round(0.05 * max(1, n)))))


def _stable_key(node: Any) -> str:
    return f"{type(node).__name__}:{node!r}"


def _resolve_graph_path(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def load_im_online_graph(path_text: str | None = None) -> tuple[nx.Graph, str]:
    path = _resolve_graph_path(path_text)
    if path is not None and path.exists():
        graph = nx.read_edgelist(path, nodetype=int, create_using=nx.Graph())
        graph.remove_edges_from(nx.selfloop_edges(graph))
        return nx.convert_node_labels_to_integers(graph), str(path)
    graph = nx.barabasi_albert_graph(500, 3, seed=20260626)
    return graph, "generated_barabasi_albert_graph(500,3,seed=20260626)"


def normalize_seed_order(graph: nx.Graph, raw: Any, k: int) -> tuple[list[Any], bool, int]:
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
        out.extend([node for node in sorted(nodes - seen, key=_stable_key)][: k - len(out)])
    return out, valid_raw, len(raw_list)


def prepare_im_online_artifacts(
    online_graph: str | None = None,
    live_edge_worlds: int = 1024,
    rr_sets: int = 1024,
    p: float = 0.1,
    seed: int = 20260626,
) -> IMOnlineArtifacts:
    graph, source = load_im_online_graph(online_graph)
    artifacts = IMOnlineArtifacts(
        graph=graph,
        graph_source=source,
        k=im_seed_budget(graph.number_of_nodes()),
        live_edge_worlds=build_fixed_live_edge_worlds(graph, live_edge_worlds, p, seed),
        rr_sets=build_fixed_rr_sets(graph, rr_sets, p, seed),
        p=p,
        seed=seed,
    )
    root = evaluate_im_root(artifacts)
    return replace(artifacts, root_spread_ic=float(root["spread_ic"]))


def _base_im_row(program: CandidateProgram, artifacts: IMOnlineArtifacts) -> dict[str, Any]:
    return {
        "candidate_id": program.candidate_id,
        "family": program.family,
        "source_stage": program.source_stage,
        "valid": False,
        "error": "",
        "spread_ic": float("nan"),
        "relative_spread_ic": float("nan"),
        "rr_coverage": float("nan"),
        "time_s": float("nan"),
        "seed_size": 0,
        "raw_seed_size": 0,
        "seed_nodes": "",
        "graph_count": 1,
        "online_nodes": artifacts.graph.number_of_nodes(),
        "online_edges": artifacts.graph.number_of_edges(),
        "seed_budget": artifacts.k,
        "rank_score": -1.0,
    }


def evaluate_im_candidate(program: CandidateProgram, artifacts: IMOnlineArtifacts) -> dict[str, Any]:
    row = _base_im_row(program, artifacts)
    try:
        fn = compile_candidate(program, function_name=IM_FUNCTION_NAME)
        started = time.perf_counter()
        raw = fn(artifacts.graph.copy(), artifacts.k)
        elapsed = time.perf_counter() - started
        seeds, valid_raw, raw_size = normalize_seed_order(artifacts.graph, raw, artifacts.k)
        spread = fixed_live_edge_spread(artifacts.graph, seeds, artifacts.live_edge_worlds)
        row.update(
            {
                "valid": bool(valid_raw),
                "spread_ic": spread,
                "relative_spread_ic": spread - artifacts.root_spread_ic,
                "rr_coverage": rr_coverage(seeds, artifacts.rr_sets),
                "time_s": float(elapsed),
                "seed_size": len(seeds),
                "raw_seed_size": raw_size,
                "seed_nodes": json.dumps(seeds, ensure_ascii=False),
            }
        )
    except Exception as exc:  # noqa: BLE001
        row["error"] = str(exc)
    return row


def evaluate_im_root(artifacts: IMOnlineArtifacts) -> dict[str, Any]:
    program = make_program(IM_ROOT_CODE, family="DegreeDiscount-IC-root", source_stage="stage1-root", function_name=IM_FUNCTION_NAME)
    row = evaluate_im_candidate(program, replace(artifacts, root_spread_ic=0.0))
    row["relative_spread_ic"] = 0.0
    return row


def invalid_im_row(candidate_id: str, family: str, source_stage: str, error: str, artifacts: IMOnlineArtifacts | None) -> dict[str, Any]:
    dummy_graph = nx.Graph()
    dummy = artifacts or IMOnlineArtifacts(dummy_graph, "missing", 0, [], [])
    row = _base_im_row(CandidateProgram(candidate_id, "", family, source_stage), dummy)
    row["error"] = error
    return row


def _rank01(series: pd.Series, higher_is_better: bool) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    finite = numeric[numeric.notna() & numeric.map(math.isfinite)]
    out = pd.Series(0.0, index=series.index)
    if len(finite) == 0:
        return out
    if len(finite) == 1:
        out.loc[finite.index] = 1.0
        return out
    ranks = finite.rank(method="average", ascending=not higher_is_better)
    out.loc[finite.index] = 1.0 - (ranks - 1.0) / (len(finite) - 1.0)
    return out


def rank_im_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return []
    df = pd.DataFrame(records)
    df["rank_spread_ic"] = 0.0
    df["rank_relative_spread_ic"] = 0.0
    df["rank_rr_coverage"] = 0.0
    df["rank_time_s"] = 0.0
    df["rank_score"] = -1.0
    valid = df["valid"].astype(bool) if "valid" in df else pd.Series([False] * len(df), index=df.index)
    if valid.sum() > 0:
        idx = df.index[valid]
        df.loc[idx, "rank_spread_ic"] = _rank01(df.loc[idx, "spread_ic"], True)
        df.loc[idx, "rank_relative_spread_ic"] = _rank01(df.loc[idx, "relative_spread_ic"], True)
        df.loc[idx, "rank_rr_coverage"] = _rank01(df.loc[idx, "rr_coverage"], True)
        df.loc[idx, "rank_time_s"] = _rank01(df.loc[idx, "time_s"], False)
        df.loc[idx, "rank_score"] = (
            0.7 * df.loc[idx, "rank_spread_ic"]
            + 0.1 * df.loc[idx, "rank_relative_spread_ic"]
            + 0.1 * df.loc[idx, "rank_rr_coverage"]
            + 0.1 * df.loc[idx, "rank_time_s"]
        )
    return df.where(pd.notna(df), None).to_dict("records")


def rank_ahd_online_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = rank_im_records(records)
    if not ranked:
        return ranked
    df = pd.DataFrame(ranked)
    valid = df["valid"].astype(bool) if "valid" in df else pd.Series([False] * len(df), index=df.index)
    df["rank_score"] = -1.0
    if valid.sum() > 0:
        df.loc[df.index[valid], "rank_score"] = df.loc[df.index[valid], "rank_spread_ic"]
    return df.where(pd.notna(df), None).to_dict("records")


def select_im_final_candidates(records: list[dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    valid = [row for row in records if row.get("valid") and math.isfinite(float(row.get("spread_ic", float("nan"))))]
    if not valid:
        return {"CHD-Final-Best": None, "CHD-Final-Fast": None}
    best = max(valid, key=lambda row: float(row.get("rank_score", -1.0)))
    spreads = sorted(float(row["spread_ic"]) for row in valid)
    q75 = spreads[max(0, math.ceil(0.75 * len(spreads)) - 1)]
    fast_pool = [row for row in valid if float(row["spread_ic"]) >= q75] or valid
    fast = min(fast_pool, key=lambda row: (float(row.get("time_s", float("inf"))), -float(row.get("spread_ic", 0.0))))
    return {"CHD-Final-Best": best, "CHD-Final-Fast": fast}


def metric_brief(record: dict[str, Any]) -> str:
    return (
        f"node_id={record.get('node_id', '')}, "
        f"candidate_id={record.get('candidate_id', '')}, "
        f"spread_ic={float(record.get('spread_ic', float('nan'))):.6f}, "
        f"relative_spread_ic={float(record.get('relative_spread_ic', float('nan'))):.6f}, "
        f"rr_coverage={float(record.get('rr_coverage', float('nan'))):.6f}, "
        f"time_s={float(record.get('time_s', float('nan'))):.6f}, "
        f"rank_score={float(record.get('rank_score', -1.0)):.6f}"
    )


def build_stage1_prompt(index: int, parent: CandidateProgram, parent_record: dict[str, Any]) -> str:
    return f"""
You are expanding CHD Stage 1 free-search tree node #{index} for Influence Maximization.

{IM_TASK_GUIDANCE}

Online ranking:
Score = 0.7*rank(spread_ic) + 0.1*rank(relative_spread_ic) + 0.1*rank(rr_coverage) + 0.1*rank(time_s lower better).

Parent metrics:
{metric_brief(parent_record)}

Parent code:
```python
{parent.code[:4500]}
```

Candidate contract:
{IM_INTERFACE}

Rules:
- Return only Python code, preferably in one code block.
- Allowed imports: math, heapq, random, itertools, collections, networkx, numpy.
{IM_FORBIDDEN_GUIDANCE}
""".strip()


def build_stage3_prompt(index: int, parent: CandidateProgram, parent_record: dict[str, Any], policy: Any, branch_role: str = "B") -> str:
    return f"""
You are expanding CHD Stage 3 bounded-search tree node #{index} for Influence Maximization.
Stage 3 branch: {branch_role}

Use the Stage 2 policy as bounded guidance, but emit one complete deterministic seed-selection implementation.

Parent metrics:
{metric_brief(parent_record)}

Parent code:
```python
{parent.code[:4500]}
```

Bound policy JSON:
{json.dumps(policy.to_dict(), ensure_ascii=False, indent=2)}

Candidate contract:
{IM_INTERFACE}

Scoring:
0.7*rank(spread_ic) + 0.1*rank(relative_spread_ic) + 0.1*rank(rr_coverage) + 0.1*rank(time_s lower better).

Rules:
- Return only Python code, preferably in one code block.
- Use bounded local coverage, degree-discount, RR-style, diversity, or hybrid signals.
- Allowed imports: math, heapq, random, itertools, collections, networkx, numpy.
{IM_FORBIDDEN_GUIDANCE}
""".strip()


def static_contract_violation(code: str) -> str:
    lowered = code.lower()
    forbidden = ["all_pairs", "betweenness", "pagerank", "shortest_path", "while true"]
    for token in forbidden:
        if token in lowered:
            return f"static contract violation: {token}"
    return ""
