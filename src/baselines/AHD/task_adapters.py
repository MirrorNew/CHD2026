# -*- coding: utf-8 -*-
"""Network-dismantling task adapter for AHD baseline policies.

Policies describe search behavior only. This adapter fixes the CHD-ND task:
all generated programs start from the HDA-style ``degree_order(G)`` interface
and are evaluated as node-removal orders.
"""

from __future__ import annotations

import ast
import hashlib
import math
import re
import textwrap
import time
from dataclasses import dataclass
from typing import Any, Iterable

import networkx as nx
import numpy as np
import pandas as pd


HDA_ROOT_CODE = r"""
def degree_order(G):
    H = G.copy()
    order = []
    while H.number_of_nodes() > 0:
        node = max(H.nodes(), key=lambda u: (H.degree[u], str(u)))
        order.append(node)
        H.remove_node(node)
    return order
""".strip()


HDA_HEAP_CODE = r"""
def degree_order(G):
    import heapq
    H = G.copy()
    alive = set(H.nodes())
    degree = {u: H.degree[u] for u in H.nodes()}
    heap = [(-degree[u], str(u), u) for u in H.nodes()]
    heapq.heapify(heap)
    order = []
    while alive:
        while heap:
            _, _, u = heapq.heappop(heap)
            if u in alive:
                break
        else:
            u = max(alive, key=lambda x: (degree.get(x, 0), str(x)))
        order.append(u)
        alive.remove(u)
        for v in list(H.neighbors(u)):
            if v in alive:
                degree[v] -= 1
                heapq.heappush(heap, (-degree[v], str(v), v))
        if H.has_node(u):
            H.remove_node(u)
    return order
""".strip()


CORE_FOCUS_CODE = r"""
def degree_order(G):
    H = G.copy()
    order = []
    while H.number_of_nodes() > 0:
        core = nx.core_number(H) if H.number_of_edges() else {u: 0 for u in H.nodes()}
        node = max(H.nodes(), key=lambda u: (core.get(u, 0), H.degree[u], str(u)))
        order.append(node)
        H.remove_node(node)
    return order
""".strip()


COMPONENT_FOCUS_CODE = r"""
def degree_order(G):
    H = G.copy()
    order = []
    while H.number_of_nodes() > 0:
        if H.number_of_edges() == 0:
            node = max(H.nodes(), key=lambda u: (H.degree[u], str(u)))
        else:
            comp = max(nx.connected_components(H), key=len)
            sub = H.subgraph(comp)
            node = max(sub.nodes(), key=lambda u: (sub.degree[u], H.degree[u], str(u)))
        order.append(node)
        H.remove_node(node)
    return order
""".strip()


LOCAL_BOUNDARY_CODE = r"""
def degree_order(G):
    H = G.copy()
    order = []
    while H.number_of_nodes() > 0:
        def score(u):
            nbrs = list(H.neighbors(u))
            degree = len(nbrs)
            boundary = 0
            two_hop = set()
            for v in nbrs[:24]:
                for w in H.neighbors(v):
                    if w != u and w not in nbrs:
                        two_hop.add(w)
                        if len(two_hop) >= 80:
                            break
                if len(two_hop) >= 80:
                    break
            for v in nbrs:
                if H.degree[v] <= 2:
                    boundary += 1
            return (degree, 0.15 * len(two_hop) + 0.4 * boundary, str(u))
        node = max(H.nodes(), key=score)
        order.append(node)
        H.remove_node(node)
    return order
""".strip()


IM_DEGREE_CODE = r"""
def seed_order(G, k):
    return sorted(G.nodes(), key=lambda u: (G.degree[u], str(u)), reverse=True)[:k]
""".strip()


IM_NEIGHBOR_COVER_CODE = r"""
def seed_order(G, k):
    selected = []
    covered = set()
    remaining = set(G.nodes())
    while remaining and len(selected) < k:
        def score(u):
            nbrs = set(G.neighbors(u))
            two = set()
            for v in list(nbrs)[:24]:
                two.update(G.neighbors(v))
                if len(two) > 120:
                    break
            gain = len(({u} | nbrs | two) - covered)
            return (gain, G.degree[u], str(u))
        node = max(remaining, key=score)
        selected.append(node)
        covered.add(node)
        covered.update(G.neighbors(node))
        remaining.remove(node)
    return selected
""".strip()


IM_DIVERSITY_CODE = r"""
def seed_order(G, k):
    selected = []
    covered = set()
    order = sorted(G.nodes(), key=lambda u: (G.degree[u], str(u)), reverse=True)
    for node in order:
        if len(selected) >= k:
            break
        nbrs = set(G.neighbors(node))
        if node not in covered or len(selected) < max(1, k // 2):
            selected.append(node)
            covered.add(node)
            covered.update(nbrs)
    return selected
""".strip()


@dataclass
class AdapterProgram:
    candidate_id: str
    code: str
    family: str = "unknown"
    source_stage: str = "unknown"


class BaseTaskAdapter:
    slug = "nd"
    task_name = "Network Dismantling"
    function_name = "degree_order"
    candidate_interface = "def degree_order(G):\n    return full_node_removal_order"
    task_guidance = (
        "Return a full deterministic node-removal order for an undirected NetworkX graph. "
        "The evaluator simulates removals and rewards lower average largest-component ratio, "
        "higher residual fragmentation, and lower runtime. The root is HDA: repeatedly remove "
        "the current highest residual-degree node."
    )
    forbidden_guidance = (
        "- file/network/subprocess/os/sys/pathlib operations;\n"
        "- exact branch-and-bound or all-subset enumeration;\n"
        "- unbounded BFS/DFS/random loops;\n"
        "- global centrality recomputation such as betweenness/PageRank/community detection."
    )
    root_code = HDA_ROOT_CODE
    fallback_codes: dict[str, str] = {
        "root": HDA_ROOT_CODE,
        "private_coverage": LOCAL_BOUNDARY_CODE,
        "redundancy_prune": COMPONENT_FOCUS_CODE,
        "two_hop": LOCAL_BOUNDARY_CODE,
        "harmony": CORE_FOCUS_CODE,
        "fast_archive": HDA_HEAP_CODE,
    }

    def make_proxy_graphs(self) -> dict[str, nx.Graph]:
        return make_nd_proxy_graphs()

    def manifest_rows(self, graphs: dict[str, nx.Graph]) -> list[dict[str, Any]]:
        return nd_manifest_rows(graphs)

    def fallback_code(self, method_slug: str, index: int, family: str = "root") -> str:
        del method_slug, index
        return self.fallback_codes.get(family) or self.root_code

    def evaluate_code(
        self,
        code: str,
        *,
        method_slug: str,
        method_name: str,
        graphs: dict[str, nx.Graph],
        index: int,
        source: str,
    ) -> tuple[dict[str, Any], AdapterProgram | None]:
        started = time.perf_counter()
        try:
            clean = extract_task_code(code, self.function_name)
            program = make_adapter_program(clean, self.function_name, method_name, f"ahd-{method_slug}")
            row = self._evaluate_program(program, graphs)
            row.update(
                {
                    "method": method_name,
                    "method_slug": method_slug,
                    "candidate_index": index,
                    "source": source,
                    "task": self.slug,
                    "elapsed_wall_s": time.perf_counter() - started,
                    "code": program.code,
                }
            )
            return row, program
        except Exception as exc:  # noqa: BLE001
            return (
                {
                    "method": method_name,
                    "method_slug": method_slug,
                    "candidate_index": index,
                    "source": source,
                    "task": self.slug,
                    "candidate_id": f"invalid-{method_slug}-{index}",
                    "valid": False,
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "rank_score": -1.0,
                    "elapsed_wall_s": time.perf_counter() - started,
                    "code": code,
                },
                None,
            )

    def _evaluate_program(self, program: AdapterProgram, graphs: dict[str, nx.Graph]) -> dict[str, Any]:
        runner = compile_task_program(program.code, self.function_name)
        rows = [evaluate_nd_graph(graph, runner) for graph in graphs.values()]
        numeric = {
            key: float(sum(float(row[key]) for row in rows) / max(1, len(rows)))
            for key in ["R", "cNBI", "Time", "raw_order_size"]
        }
        return {
            "candidate_id": program.candidate_id,
            "family": program.family,
            "source_stage": program.source_stage,
            "valid": all(bool(row["valid"]) for row in rows),
            "ok": True,
            "error": "",
            "graph_count": len(rows),
            **numeric,
        }

    def rank_records(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return rows
        df = pd.DataFrame(rows)
        df["rank_score"] = -1.0
        valid = df["ok"].astype(bool) if "ok" in df else pd.Series([False] * len(df), index=df.index)
        if valid.sum() > 0:
            idx = df.index[valid]
            r_rank = pd.to_numeric(df.loc[idx, "R"], errors="coerce").rank(ascending=True, method="average")
            cnbi_rank = pd.to_numeric(df.loc[idx, "cNBI"], errors="coerce").rank(ascending=False, method="average")
            time_rank = pd.to_numeric(df.loc[idx, "Time"], errors="coerce").rank(ascending=True, method="average")
            denom = max(1.0, float(len(idx) - 1))
            df.loc[idx, "rank_R"] = 1.0 - (r_rank - 1.0) / denom
            df.loc[idx, "rank_cNBI"] = 1.0 - (cnbi_rank - 1.0) / denom
            df.loc[idx, "rank_Time"] = 1.0 - (time_rank - 1.0) / denom
            df.loc[idx, "rank_score"] = (
                0.42 * df.loc[idx, "rank_R"]
                + 0.38 * df.loc[idx, "rank_cNBI"]
                + 0.20 * df.loc[idx, "rank_Time"]
            )
        return df.where(pd.notna(df), None).to_dict("records")


class NDTaskAdapter(BaseTaskAdapter):
    """Explicit alias kept for older callers."""


class IMTaskAdapter(BaseTaskAdapter):
    slug = "im"
    task_name = "Influence Maximization"
    function_name = "seed_order"
    candidate_interface = "def seed_order(G, k):\n    return up_to_k_seed_nodes"
    task_guidance = (
        "Return a deterministic list of up to k seed nodes for an undirected NetworkX graph. "
        "The evaluator estimates influence spread with a fixed independent-cascade proxy and "
        "rewards larger spread, better two-hop coverage, and lower runtime."
    )
    forbidden_guidance = (
        "- file/network/subprocess/os/sys/pathlib operations;\n"
        "- exact all-subset seed enumeration;\n"
        "- unbounded BFS/DFS/random loops;\n"
        "- expensive global algorithms inside repeated marginal-gain loops."
    )
    root_code = IM_DEGREE_CODE
    fallback_codes: dict[str, str] = {
        "root": IM_DEGREE_CODE,
        "private_coverage": IM_NEIGHBOR_COVER_CODE,
        "redundancy_prune": IM_DIVERSITY_CODE,
        "two_hop": IM_NEIGHBOR_COVER_CODE,
        "harmony": IM_DIVERSITY_CODE,
        "fast_archive": IM_DEGREE_CODE,
    }

    def make_proxy_graphs(self) -> dict[str, nx.Graph]:
        return make_im_proxy_graphs()

    def manifest_rows(self, graphs: dict[str, nx.Graph]) -> list[dict[str, Any]]:
        rows = nd_manifest_rows(graphs)
        for row in rows:
            row["seed_budget"] = im_seed_budget(int(row["nodes"]))
            row["task"] = self.slug
        return rows

    def _evaluate_program(self, program: AdapterProgram, graphs: dict[str, nx.Graph]) -> dict[str, Any]:
        runner = compile_task_program(program.code, self.function_name)
        rows = [evaluate_im_graph(graph, runner) for graph in graphs.values()]
        numeric = {
            key: float(sum(float(row[key]) for row in rows) / max(1, len(rows)))
            for key in ["spread", "coverage", "Time", "raw_seed_size"]
        }
        return {
            "candidate_id": program.candidate_id,
            "family": program.family,
            "source_stage": program.source_stage,
            "valid": all(bool(row["valid"]) for row in rows),
            "ok": True,
            "error": "",
            "graph_count": len(rows),
            **numeric,
        }

    def rank_records(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return rows
        df = pd.DataFrame(rows)
        df["rank_score"] = -1.0
        valid = df["ok"].astype(bool) if "ok" in df else pd.Series([False] * len(df), index=df.index)
        if valid.sum() > 0:
            idx = df.index[valid]
            spread_rank = pd.to_numeric(df.loc[idx, "spread"], errors="coerce").rank(ascending=False, method="average")
            coverage_rank = pd.to_numeric(df.loc[idx, "coverage"], errors="coerce").rank(ascending=False, method="average")
            time_rank = pd.to_numeric(df.loc[idx, "Time"], errors="coerce").rank(ascending=True, method="average")
            denom = max(1.0, float(len(idx) - 1))
            df.loc[idx, "rank_spread"] = 1.0 - (spread_rank - 1.0) / denom
            df.loc[idx, "rank_coverage"] = 1.0 - (coverage_rank - 1.0) / denom
            df.loc[idx, "rank_Time"] = 1.0 - (time_rank - 1.0) / denom
            df.loc[idx, "rank_score"] = (
                0.55 * df.loc[idx, "rank_spread"]
                + 0.30 * df.loc[idx, "rank_coverage"]
                + 0.15 * df.loc[idx, "rank_Time"]
            )
        return df.where(pd.notna(df), None).to_dict("records")


def get_task_adapter(slug: str = "nd") -> BaseTaskAdapter:
    normalized = slug.strip().lower()
    if normalized in {"", "nd", "network_dismantling", "network-dismantling", "chd-nd"}:
        return NDTaskAdapter()
    if normalized in {"im", "influence_maximization", "influence-maximization", "chd-im"}:
        return IMTaskAdapter()
    raise ValueError("task must be nd or im")


def make_nd_proxy_graphs() -> dict[str, nx.Graph]:
    graphs = {
        "powerlaw_120": nx.barabasi_albert_graph(120, 2, seed=20260603),
        "er_120": nx.gnp_random_graph(120, 0.035, seed=20260604),
        "ws_120": nx.watts_strogatz_graph(120, 4, 0.08, seed=20260605),
        "community_128": nx.stochastic_block_model(
            [32, 32, 32, 32],
            [
                [0.11, 0.008, 0.006, 0.006],
                [0.008, 0.10, 0.007, 0.006],
                [0.006, 0.007, 0.11, 0.008],
                [0.006, 0.006, 0.008, 0.10],
            ],
            seed=20260606,
        ),
    }
    return {name: _connect_components(nx.convert_node_labels_to_integers(graph)) for name, graph in graphs.items()}


def make_im_proxy_graphs() -> dict[str, nx.Graph]:
    graphs = {
        "im_powerlaw_160": nx.barabasi_albert_graph(160, 3, seed=20260611),
        "im_er_160": nx.gnp_random_graph(160, 0.03, seed=20260612),
        "im_ws_160": nx.watts_strogatz_graph(160, 6, 0.12, seed=20260613),
        "im_community_160": nx.stochastic_block_model(
            [40, 40, 40, 40],
            [
                [0.09, 0.012, 0.006, 0.006],
                [0.012, 0.09, 0.010, 0.006],
                [0.006, 0.010, 0.09, 0.012],
                [0.006, 0.006, 0.012, 0.09],
            ],
            seed=20260614,
        ),
    }
    return {name: _connect_components(nx.convert_node_labels_to_integers(graph)) for name, graph in graphs.items()}


def nd_manifest_rows(graphs: dict[str, nx.Graph]) -> list[dict[str, Any]]:
    rows = []
    for name, graph in graphs.items():
        degrees = [degree for _, degree in graph.degree()]
        rows.append(
            {
                "dataset": name,
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "avg_degree": float(np.mean(degrees)) if degrees else 0.0,
                "max_degree": int(max(degrees)) if degrees else 0,
                "connected": nx.is_connected(graph) if graph.number_of_nodes() else True,
            }
        )
    return rows


def im_seed_budget(n: int) -> int:
    return max(3, min(12, int(round(0.05 * max(1, n)))))


def _connect_components(graph: nx.Graph) -> nx.Graph:
    graph = nx.Graph(graph)
    graph.remove_edges_from(nx.selfloop_edges(graph))
    if graph.number_of_nodes() > 0 and not nx.is_connected(graph):
        comps = [list(comp) for comp in nx.connected_components(graph)]
        for left, right in zip(comps[:-1], comps[1:]):
            graph.add_edge(left[0], right[0])
    return graph


def stable_hash(text: str, n: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def extract_task_code(response_text: str, function_name: str) -> str:
    pattern = rf"def\s+{re.escape(function_name)}\s*\("
    blocks = re.findall(r"```(?:python)?\s*(.*?)```", response_text, flags=re.DOTALL | re.IGNORECASE)
    for block in blocks:
        if re.search(pattern, block):
            return block.strip()
    match = re.search(pattern, response_text)
    if match:
        return response_text[match.start() :].strip()
    return response_text.strip()


FORBIDDEN_TOKENS = [
    "__import__",
    "open(",
    "exec(",
    "eval(",
    "compile(",
    "input(",
    "globals(",
    "locals(",
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "shutil",
    "pathlib",
    "pickle",
    "marshal",
    "ctypes",
    "multiprocessing",
    "threading",
    "os.",
    "sys.",
    "write(",
    "rmdir(",
    "unlink(",
]
FORBIDDEN_CALL_NAMES = {"open", "exec", "eval", "compile", "input", "globals", "locals"}
FORBIDDEN_NX_CALLS = {
    "all_pairs_shortest_path",
    "all_pairs_shortest_path_length",
    "betweenness_centrality",
    "edge_betweenness_centrality",
    "pagerank",
}
ALLOWED_IMPORT_ROOTS = {"math", "heapq", "random", "itertools", "collections", "networkx", "numpy"}


def make_adapter_program(code: str, function_name: str, family: str, source_stage: str) -> AdapterProgram:
    clean = validate_task_code(code, function_name)
    return AdapterProgram(candidate_id=stable_hash(clean), code=clean, family=family, source_stage=source_stage)


def validate_task_code(code: str, function_name: str) -> str:
    code = textwrap.dedent(code).strip()
    if f"def {function_name}" not in code:
        raise ValueError(f"missing {function_name}(G)")
    lowered = code.lower()
    for token in FORBIDDEN_TOKENS:
        if token.lower() in lowered:
            raise ValueError(f"forbidden token: {token}")
    tree = ast.parse(code)
    has_target = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALL_NAMES:
                raise ValueError(f"forbidden call: {func.id}")
            if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_NX_CALLS:
                raise ValueError(f"forbidden NetworkX call: {func.attr}")
        if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
            raise ValueError("forbidden unbounded while True loop")
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                root = name.split(".")[0]
                if root not in ALLOWED_IMPORT_ROOTS:
                    raise ValueError(f"import not allowed: {name}")
        elif isinstance(node, ast.FunctionDef):
            if node.name == function_name:
                has_target = True
        elif isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
            continue
        elif isinstance(node, ast.Assign):
            continue
        else:
            raise ValueError(f"forbidden top-level statement: {type(node).__name__}")
    if not has_target:
        raise ValueError(f"missing {function_name} function")
    return code


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    del globals, locals, level
    root = name.split(".")[0]
    if root not in ALLOWED_IMPORT_ROOTS:
        raise ImportError(f"import not allowed: {name}")
    return __import__(name, fromlist=fromlist)


def compile_task_program(code: str, function_name: str):
    clean = validate_task_code(code, function_name)
    namespace: dict[str, Any] = {
        "math": math,
        "np": np,
        "numpy": np,
        "nx": nx,
        "networkx": nx,
        "__builtins__": {
            "__import__": _safe_import,
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "int": int,
            "iter": iter,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "next": next,
            "range": range,
            "reversed": reversed,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
        },
    }
    exec(compile(clean, f"<ahd-task:{function_name}>", "exec"), namespace, namespace)
    fn = namespace.get(function_name)
    if not callable(fn):
        raise ValueError(f"{function_name} is not callable")
    return fn


def normalize_order(graph: nx.Graph, order: Iterable[Any]) -> tuple[list[Any], bool]:
    nodes = set(graph.nodes())
    out: list[Any] = []
    seen: set[Any] = set()
    for node in order or []:
        if node in nodes and node not in seen:
            seen.add(node)
            out.append(node)
    valid_raw = len(out) == graph.number_of_nodes()
    out.extend([node for node in graph.nodes if node not in seen])
    return out, valid_raw


def normalize_seed_order(graph: nx.Graph, seeds: Iterable[Any], k: int) -> tuple[list[Any], bool]:
    nodes = set(graph.nodes())
    out: list[Any] = []
    seen: set[Any] = set()
    for node in seeds or []:
        if node in nodes and node not in seen:
            seen.add(node)
            out.append(node)
        if len(out) >= k:
            break
    valid_raw = 0 < len(out) <= k
    if len(out) < k:
        out.extend([node for node in graph.nodes if node not in seen][: k - len(out)])
    return out, valid_raw


def evaluate_nd_graph(graph: nx.Graph, runner) -> dict[str, Any]:
    h = nx.Graph(graph)
    started = time.perf_counter()
    raw = runner(h.copy())
    elapsed = time.perf_counter() - started
    order, valid_raw = normalize_order(h, raw)
    n0 = max(1, h.number_of_nodes())
    largest_fracs = []
    component_counts = []
    for node in order:
        if h.has_node(node):
            h.remove_node(node)
        components = [len(component) for component in nx.connected_components(h)]
        largest = max(components, default=0)
        largest_fracs.append(largest / n0)
        component_counts.append(len(components) / n0)
    r_value = float(sum(largest_fracs) / max(1, len(largest_fracs)))
    cnbi_proxy = float(sum(component_counts) / max(1, len(component_counts)))
    return {
        "valid": valid_raw,
        "R": r_value,
        "cNBI": cnbi_proxy,
        "Time": float(elapsed),
        "raw_order_size": float(len(list(raw or []))),
    }


def independent_cascade_spread(graph: nx.Graph, seeds: list[Any], p: float = 0.05, trials: int = 24) -> float:
    if graph.number_of_nodes() == 0:
        return 0.0
    total = 0
    nodes = list(graph.nodes())
    seed_set = set(seeds)
    for trial in range(trials):
        rng = np.random.default_rng(20260625 + trial)
        active = set(seed_set)
        frontier = set(seed_set)
        while frontier:
            nxt = set()
            for node in frontier:
                for nbr in graph.neighbors(node):
                    if nbr not in active and rng.random() < p:
                        nxt.add(nbr)
            nxt -= active
            active |= nxt
            frontier = nxt
        total += len(active)
    return float(total / max(1, trials) / max(1, len(nodes)))


def two_hop_seed_coverage(graph: nx.Graph, seeds: list[Any]) -> float:
    covered = set(seeds)
    frontier = set(seeds)
    for _ in range(2):
        nxt = set()
        for node in frontier:
            nxt.update(graph.neighbors(node))
        nxt -= covered
        covered |= nxt
        frontier = nxt
    return float(len(covered) / max(1, graph.number_of_nodes()))


def evaluate_im_graph(graph: nx.Graph, runner) -> dict[str, Any]:
    h = nx.Graph(graph)
    k = im_seed_budget(h.number_of_nodes())
    started = time.perf_counter()
    raw = runner(h.copy(), k)
    elapsed = time.perf_counter() - started
    raw_list = list(raw or [])
    seeds, valid_raw = normalize_seed_order(h, raw_list, k)
    return {
        "valid": valid_raw,
        "spread": independent_cascade_spread(h, seeds),
        "coverage": two_hop_seed_coverage(h, seeds),
        "Time": float(elapsed),
        "raw_seed_size": float(len(raw_list)),
    }
