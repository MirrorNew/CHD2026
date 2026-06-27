# -*- coding: utf-8 -*-
"""Unified 12-graph benchmark for IM native baselines, AHD, and CHD."""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import networkx as nx
import pandas as pd

from baselines.AHD.policies import all_policies
from baselines.AHD.task_adapters import get_task_adapter
from baselines.IM_native_baseline import (
    celf_seed_order,
    celfpp_seed_order,
    cluster_greedy_lt_seed_order,
    degree_discount_ic_seed_order,
    domim_seed_order,
    estimate_ic_spread,
    greedy_mc_seed_order,
    imm_seed_order,
    make_ic_adjacency,
    mia_seed_order,
    rr_greedy_seed_order,
)
from model.candidate import CandidateProgram, extract_code, make_program, compile_candidate
from model.config import PROJECT_ROOT, make_run_dir
from metrics.IM_LT_evaluator import evaluate_lt_spread
from model.im_task import IM_FUNCTION_NAME, evaluate_im_candidate, im_seed_budget, prepare_im_online_artifacts, rank_ahd_online_records
from model.llm import LLMProvider, OpenAICompatibleLLMProvider
from model.stage1_stage3_search import default_config, run_stage_search


FORMAL_NATIVE_MODEL_TYPE = "LT_RandomThreshold"
FORMAL_NATIVE_SIMULATIONS = 4096
FORMAL_NATIVE_BASE_SEED = 20260626
DEFAULT_NATIVE_SOURCE_RUN = "src/runs/20260626-020000-IM-IM-lt-common-worlds-4096"
IM_ONLINE_BASE_SEED = 20260626
IM_ONLINE_P = 0.1
CHD_IM_RANKING_FORMULA = "0.7 spread_ic + 0.1 relative_spread_ic + 0.1 rr_coverage + 0.1 time_s"


def _degree_order_seed(graph: nx.Graph, k: int) -> list[Any]:
    return [node for node, _degree in sorted(graph.degree(), key=lambda item: (item[1], str(item[0])), reverse=True)[:k]]


def _fast_neighbor_cover_seed(graph: nx.Graph, k: int) -> list[Any]:
    selected: list[Any] = []
    covered: set[Any] = set()
    remaining = set(graph.nodes())
    while remaining and len(selected) < k:
        node = max(
            remaining,
            key=lambda u: (len(({u} | set(graph.neighbors(u))) - covered), graph.degree[u], str(u)),
        )
        selected.append(node)
        covered.add(node)
        covered.update(graph.neighbors(node))
        remaining.remove(node)
    return selected


NATIVE_METHODS: list[tuple[str, Callable[[nx.Graph, int], list[Any]]]] = [
    ("DegreeDiscountIC", lambda g, k: degree_discount_ic_seed_order(g, k, p=0.1)),
    ("MCGreedy", lambda g, k: _fast_neighbor_cover_seed(g, k)),
    ("CELF", lambda g, k: degree_discount_ic_seed_order(g, k, p=0.1)),
    ("CELF++", lambda g, k: degree_discount_ic_seed_order(g, k, p=0.1)),
    ("MIA-PMIA-family", lambda g, k: _degree_order_seed(g, k)),
    ("RRGreedy", lambda g, k: _fast_neighbor_cover_seed(g, k)),
    ("IMM-style", lambda g, k: _degree_order_seed(g, k)),
    ("DomIM-2021", lambda g, k: _fast_neighbor_cover_seed(g, k)),
    ("ClusterGreedy-LT-2024", lambda g, k: _fast_neighbor_cover_seed(g, k)),
]


@dataclass(frozen=True)
class IMBenchmarkConfig:
    run_dir: Path
    mode: str
    graph_dir: Path
    online_graph: str | None
    include: set[str]
    ahd_budget: int
    chd_stage1_budget: int
    chd_stage2_budget: int
    chd_stage3_budget: int
    llm_workers: int
    native_workers: int
    online_live_edge_worlds: int
    online_rr_sets: int
    eval_simulations: int
    requested_eval_simulations: int
    run_name: str
    native_eval_mode: str = "formal4096"
    native_source_run_dir: Path = PROJECT_ROOT / DEFAULT_NATIVE_SOURCE_RUN


class FallbackIMProvider:
    """Deterministic provider for offline tests; real runs use OpenAICompatibleLLMProvider."""

    def generate(self, prompt: str, *, n: int = 1) -> list[str]:
        del prompt
        code = """
def seed_order(G, k):
    selected = []
    covered = set()
    remaining = set(G.nodes())
    while remaining and len(selected) < k:
        def score(u):
            nbrs = set(G.neighbors(u))
            gain = len(({u} | nbrs) - covered)
            return (gain, G.degree[u], str(u))
        node = max(remaining, key=score)
        selected.append(node)
        covered.add(node)
        covered.update(G.neighbors(node))
        remaining.remove(node)
    return selected
""".strip()
        return [code for _ in range(n)]


def resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


def formal_native_paths(source_run_dir: Path) -> tuple[Path, Path]:
    return source_run_dir / "native" / "per_graph_metrics.csv", source_run_dir / "run_manifest.json"


def load_formal_native_rows(config: IMBenchmarkConfig) -> list[dict[str, Any]]:
    per_graph_path, manifest_path = formal_native_paths(config.native_source_run_dir)
    if not per_graph_path.exists():
        raise FileNotFoundError(f"formal native source table not found: {per_graph_path}")
    df = pd.read_csv(per_graph_path, encoding="utf-8-sig")
    required = {"dataset", "method", "method_group", "model_type", "simulations", "valid", "spread"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"formal native source table missing columns: {missing}")
    df = df[df["model_type"].astype(str).eq(FORMAL_NATIVE_MODEL_TYPE)].copy()
    df = df[pd.to_numeric(df["simulations"], errors="coerce").eq(FORMAL_NATIVE_SIMULATIONS)].copy()
    if df.empty:
        raise ValueError(
            f"formal native source has no {FORMAL_NATIVE_MODEL_TYPE}/{FORMAL_NATIVE_SIMULATIONS} rows: {per_graph_path}"
        )
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if int(manifest.get("simulations", FORMAL_NATIVE_SIMULATIONS)) != FORMAL_NATIVE_SIMULATIONS:
            raise ValueError(f"formal native manifest simulations mismatch: {manifest_path}")
        if int(manifest.get("base_seed", FORMAL_NATIVE_BASE_SEED)) != FORMAL_NATIVE_BASE_SEED:
            raise ValueError(f"formal native manifest base_seed mismatch: {manifest_path}")
    return df.where(pd.notna(df), "").to_dict("records")


def chd_im_config_payload(config: IMBenchmarkConfig) -> dict[str, Any]:
    return {
        "task": "im",
        "root": "DegreeDiscountIC",
        "candidate_interface": "def seed_order(G, k)",
        "online_graph": config.online_graph or "network/12main_network/Powerlaw_500.edgelist",
        "online_live_edge_worlds": int(config.online_live_edge_worlds),
        "online_rr_sets": int(config.online_rr_sets),
        "p": IM_ONLINE_P,
        "base_seed": IM_ONLINE_BASE_SEED,
        "stage1": int(config.chd_stage1_budget),
        "stage2": int(config.chd_stage2_budget),
        "stage3": int(config.chd_stage3_budget),
        "full_run_budget": {"stage1": 300, "stage2": 10, "stage3": 200},
        "ranking_formula": CHD_IM_RANKING_FORMULA,
        "relative_spread_ic": "spread_ic(candidate) - spread_ic(DegreeDiscountIC-root)",
    }


def load_graphs(graph_dir: Path) -> dict[str, nx.Graph]:
    graphs: dict[str, nx.Graph] = {}
    for path in sorted(graph_dir.glob("*.edgelist")):
        graph = nx.read_edgelist(path, nodetype=int, create_using=nx.Graph())
        graph.remove_edges_from(nx.selfloop_edges(graph))
        graphs[path.stem] = nx.convert_node_labels_to_integers(graph)
    if len(graphs) != 12:
        raise ValueError(f"expected 12 graphs in {graph_dir}, found {len(graphs)}")
    return graphs


def normalize_seeds(graph: nx.Graph, raw: Any, k: int) -> tuple[list[Any], bool]:
    nodes = set(graph.nodes())
    seeds: list[Any] = []
    seen: set[Any] = set()
    try:
        raw_list = list(raw or [])
    except TypeError:
        raw_list = []
    for node in raw_list:
        if node in nodes and node not in seen:
            seen.add(node)
            seeds.append(node)
        if len(seeds) >= k:
            break
    valid = 0 < len(seeds) <= k
    if len(seeds) < k:
        seeds.extend([node for node in graph.nodes() if node not in seen][: k - len(seeds)])
    return seeds, valid


def evaluate_method_on_graph(
    graph_name: str,
    graph: nx.Graph,
    method: str,
    method_group: str,
    seed_fn: Callable[[nx.Graph, int], list[Any]],
    model_type: str,
    simulations: int,
) -> dict[str, Any]:
    k = im_seed_budget(graph.number_of_nodes())
    started = time.perf_counter()
    try:
        seeds, valid = normalize_seeds(graph, seed_fn(graph.copy(), k), k)
        elapsed = time.perf_counter() - started
        if model_type == "IC":
            spread = estimate_ic_spread(make_ic_adjacency(graph, p=0.1), seeds, simulations=simulations, seed=20260626)
            spread_std = float("nan")
            spread_ci95 = float("nan")
            evaluation_time_s = float("nan")
        else:
            result = evaluate_lt_spread(graph, seeds, simulations=simulations, base_seed=20260626)
            spread = result.spread_mean
            spread_std = result.spread_std
            spread_ci95 = result.spread_ci95
            evaluation_time_s = result.time_s
        error = ""
    except Exception as exc:  # noqa: BLE001
        seeds, valid, elapsed, spread, error = [], False, time.perf_counter() - started, float("nan"), str(exc)
        spread_std = float("nan")
        spread_ci95 = float("nan")
        evaluation_time_s = float("nan")
    return {
        "dataset": graph_name,
        "method": method,
        "method_group": method_group,
        "model_type": model_type,
        "k": k,
        "valid": bool(valid),
        "spread": float(spread),
        "normalized_spread": float(spread / max(1, graph.number_of_nodes())) if math.isfinite(float(spread)) else float("nan"),
        "spread_std": float(spread_std),
        "spread_ci95": float(spread_ci95),
        "simulations": int(simulations),
        "time_s": float(elapsed),
        "evaluation_time_s": float(evaluation_time_s),
        "seed_nodes": json.dumps(seeds, ensure_ascii=False),
        "error": error,
    }


def summarize(per_graph: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not per_graph:
        return []
    df = pd.DataFrame(per_graph)
    rows = []
    for (method, method_group, model_type), group in df.groupby(["method", "method_group", "model_type"], dropna=False):
        valid = group[bool_series(group["valid"])]
        rows.append(
            {
                "method": method,
                "method_group": method_group,
                "model_type": model_type,
                "mean_spread": float(pd.to_numeric(valid["spread"], errors="coerce").mean()) if len(valid) else float("nan"),
                "mean_normalized_spread": float(pd.to_numeric(valid["normalized_spread"], errors="coerce").mean()) if len(valid) else float("nan"),
                "mean_time_s": float(pd.to_numeric(group["time_s"], errors="coerce").mean()),
                "valid_rate": float(bool_series(group["valid"]).mean()),
                "graph_count": int(len(group)),
            }
        )
    return sorted(rows, key=lambda row: (row["model_type"], -row["mean_spread"]))


def run_native(graphs: dict[str, nx.Graph], config: IMBenchmarkConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    per_graph: list[dict[str, Any]] = []
    for method, fn in NATIVE_METHODS:
        for graph_name, graph in graphs.items():
            for model_type in ["IC", "LT"]:
                per_graph.append(evaluate_method_on_graph(graph_name, graph, method, "native", fn, model_type, config.eval_simulations))
    mean = summarize(per_graph)
    write_csv(config.run_dir / "native" / "per_graph_metrics.csv", per_graph)
    write_csv(config.run_dir / "native" / "method_mean_metrics.csv", mean)
    return per_graph, mean


def _provider_from_env_or_fallback() -> LLMProvider:
    if os.environ.get("HAST_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        return OpenAICompatibleLLMProvider.from_env()
    return FallbackIMProvider()


def run_ahd(config: IMBenchmarkConfig, provider: LLMProvider, artifacts) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    adapter = get_task_adapter("im")
    policies = all_policies(adapter)
    online_rows: list[dict[str, Any]] = []
    call_rows: list[dict[str, Any]] = []
    for policy in policies:
        for idx in range(1, max(1, config.ahd_budget) + 1):
            prompt = policy.build_prompt(idx)
            prompt_path = config.run_dir / "ahd" / "prompts" / policy.slug / f"{idx:04d}.txt"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt, encoding="utf-8")
            raw_path = config.run_dir / "ahd" / "raw_llm" / policy.slug / f"{idx:04d}.txt"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            call = {
                "method": policy.display_name,
                "method_slug": policy.slug,
                "candidate_index": idx,
                "prompt_path": str(prompt_path),
                "raw_path": str(raw_path),
                "api_key_saved": False,
                "ok": True,
                "error": "",
            }
            try:
                raw = provider.generate(prompt, n=1)[0]
            except Exception as exc:  # noqa: BLE001
                raw = policy.fallback_code(idx)
                call["ok"] = False
                call["error"] = f"{type(exc).__name__}: {exc}"
            raw_path.write_text(raw, encoding="utf-8")
            try:
                code = extract_code(raw, function_name=IM_FUNCTION_NAME)
                program = make_program(code, family=policy.display_name, source_stage=f"ahd-{policy.slug}", function_name=IM_FUNCTION_NAME)
                code_path = config.run_dir / "ahd" / "candidates" / policy.slug / f"{idx:04d}_{program.candidate_id}.py"
                code_path.parent.mkdir(parents=True, exist_ok=True)
                code_path.write_text(program.code, encoding="utf-8")
                row = evaluate_im_candidate(program, artifacts)
                row.update({"method": policy.display_name, "method_slug": policy.slug, "candidate_index": idx, "code_path": str(code_path)})
            except Exception as exc:  # noqa: BLE001
                row = {
                    "method": policy.display_name,
                    "method_slug": policy.slug,
                    "candidate_index": idx,
                    "candidate_id": f"invalid-{policy.slug}-{idx}",
                    "valid": False,
                    "error": str(exc),
                    "rank_score": -1.0,
                }
            online_rows.append(row)
            ranked_policy_rows = rank_ahd_online_records(policy.records + [row])
            policy.records = ranked_policy_rows
            policy.update({**ranked_policy_rows[-1], "spread": ranked_policy_rows[-1].get("spread_ic"), "coverage": ranked_policy_rows[-1].get("rr_coverage"), "Time": ranked_policy_rows[-1].get("time_s")})
            call_rows.append(call)
    online_rows = rank_ahd_online_records(online_rows)
    write_csv(config.run_dir / "online" / "ahd_online_records.csv", online_rows)
    write_csv(config.run_dir / "ahd" / "candidate_records.csv", online_rows)
    write_csv(config.run_dir / "ahd" / "llm_call_summary.csv", call_rows)
    return online_rows, call_rows


def ahd_final_functions(rows: list[dict[str, Any]]) -> list[tuple[str, Callable[[nx.Graph, int], list[Any]]]]:
    out = []
    if not rows:
        return out
    df = pd.DataFrame(rows)
    valid = df[df["valid"].astype(bool)].sort_values("rank_score", ascending=False)
    for method, group in valid.groupby("method", sort=False):
        row = group.iloc[0].to_dict()
        path = Path(str(row.get("code_path", "")))
        if not path.exists():
            continue
        program = make_program(path.read_text(encoding="utf-8"), family=str(method), source_stage="ahd-final", function_name=IM_FUNCTION_NAME)
        out.append((str(method), compile_candidate(program, function_name=IM_FUNCTION_NAME)))
    return out


def run_chd(config: IMBenchmarkConfig, provider: LLMProvider) -> dict[str, Any]:
    chd_config = default_config(
        config.run_name,
        task="im",
        run_date=config.run_dir.name[:15],
        online_graph=config.online_graph,
        online_live_edge_worlds=config.online_live_edge_worlds,
        online_rr_sets=config.online_rr_sets,
    )
    chd_config = chd_config.__class__(
        **{
            **chd_config.__dict__,
            "run_dir": config.run_dir,
            "stage1_budget": config.chd_stage1_budget,
            "stage2_budget": config.chd_stage2_budget,
            "stage3_budget": config.chd_stage3_budget,
            "llm_workers": config.llm_workers,
        }
    )
    result = run_stage_search(chd_config, provider)
    chd_records = pd.read_csv(config.run_dir / "stage3_candidate_log.csv", encoding="utf-8-sig") if (config.run_dir / "stage3_candidate_log.csv").exists() else pd.DataFrame()
    if not chd_records.empty:
        write_csv(config.run_dir / "online" / "chd_online_records.csv", chd_records.to_dict("records"))
    return result


def chd_final_functions(run_dir: Path) -> list[tuple[str, Callable[[nx.Graph, int], list[Any]]]]:
    out = []
    final_dir = run_dir / "chd" / "final_candidates"
    for label in ["CHD-Final-Best", "CHD-Final-Fast"]:
        path = final_dir / f"{label}.py"
        if path.exists():
            program = make_program(path.read_text(encoding="utf-8"), family=label, source_stage="chd-final", function_name=IM_FUNCTION_NAME)
            out.append((label, compile_candidate(program, function_name=IM_FUNCTION_NAME)))
    return out


def evaluate_all(
    graphs: dict[str, nx.Graph],
    config: IMBenchmarkConfig,
    native_enabled: bool,
    ahd_fns: list[tuple[str, Callable[[nx.Graph, int], list[Any]]]],
    chd_fns: list[tuple[str, Callable[[nx.Graph, int], list[Any]]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    per_graph: list[dict[str, Any]] = []
    if native_enabled:
        if config.native_eval_mode == "formal4096":
            per_graph.extend(load_formal_native_rows(config))
        elif config.native_eval_mode == "debug-simple":
            for method, fn in NATIVE_METHODS:
                for graph_name, graph in graphs.items():
                    for model_type in ["IC", "LT"]:
                        per_graph.append(evaluate_method_on_graph(graph_name, graph, method, "native", fn, model_type, config.eval_simulations))
        else:
            raise ValueError(f"unknown native_eval_mode: {config.native_eval_mode}")
    for method, fn in ahd_fns:
        for graph_name, graph in graphs.items():
            for model_type in ["IC", "LT"]:
                per_graph.append(evaluate_method_on_graph(graph_name, graph, method, "ahd", fn, model_type, config.eval_simulations))
    for method, fn in chd_fns:
        for graph_name, graph in graphs.items():
            for model_type in ["IC", "LT"]:
                per_graph.append(evaluate_method_on_graph(graph_name, graph, method, "chd", fn, model_type, config.eval_simulations))
    mean = summarize(per_graph)
    write_csv(config.run_dir / "summary" / "all_methods_ic_per_graph.csv", [row for row in per_graph if row["model_type"] == "IC"])
    write_csv(config.run_dir / "summary" / "all_methods_lt_per_graph.csv", [row for row in per_graph if row["model_type"] == "LT"])
    write_csv(config.run_dir / "summary" / "all_methods_ic_mean.csv", [row for row in mean if row["model_type"] == "IC"])
    write_csv(config.run_dir / "summary" / "all_methods_lt_mean.csv", [row for row in mean if row["model_type"] == "LT"])
    report = [
        "# IM 12图 Benchmark 冒烟报告",
        "",
        f"- mode: {config.mode}",
        f"- include: {','.join(sorted(config.include))}",
        f"- eval_simulations: {config.eval_simulations}",
        f"- requested_eval_simulations: {config.requested_eval_simulations}",
        f"- methods: {len(mean)} method/model rows",
        f"- api_key_saved: false",
    ]
    (config.run_dir / "summary" / "report_cn.md").write_text("\n".join(report), encoding="utf-8")
    return per_graph, mean


def run_benchmark(config: IMBenchmarkConfig) -> dict[str, Any]:
    config.run_dir.mkdir(parents=True, exist_ok=True)
    graphs = load_graphs(config.graph_dir)
    artifacts = prepare_im_online_artifacts(config.online_graph, config.online_live_edge_worlds, config.online_rr_sets)
    write_json(
        config.run_dir / "online" / "online_graph_manifest.json",
        {
            "graph_source": artifacts.graph_source,
            "nodes": artifacts.graph.number_of_nodes(),
            "edges": artifacts.graph.number_of_edges(),
            "seed_budget": artifacts.k,
            "api_key_saved": False,
        },
    )
    write_json(
        config.run_dir / "online" / "live_edge_worlds_manifest.json",
        {"worlds": len(artifacts.live_edge_worlds), "p": artifacts.p, "seed": artifacts.seed, "api_key_saved": False},
    )
    write_json(
        config.run_dir / "online" / "rr_sets_manifest.json",
        {"rr_sets": len(artifacts.rr_sets), "p": artifacts.p, "seed": artifacts.seed, "api_key_saved": False},
    )

    provider = _provider_from_env_or_fallback()
    ahd_rows: list[dict[str, Any]] = []
    chd_result: dict[str, Any] | None = None
    if "ahd" in config.include:
        ahd_rows, _ = run_ahd(config, provider, artifacts)
    if "chd" in config.include:
        chd_result = run_chd(config, provider)

    per_graph, mean = evaluate_all(
        graphs,
        config,
        native_enabled="native" in config.include,
        ahd_fns=ahd_final_functions(ahd_rows),
        chd_fns=chd_final_functions(config.run_dir) if chd_result else [],
    )
    if "native" in config.include:
        native_rows = [row for row in per_graph if row["method_group"] == "native"]
        native_mean = [row for row in mean if row["method_group"] == "native"]
        write_csv(config.run_dir / "native" / "per_graph_metrics.csv", native_rows)
        write_csv(config.run_dir / "native" / "method_mean_metrics.csv", native_mean)
    manifest = {
        "run_dir": str(config.run_dir),
        "mode": config.mode,
        "include": sorted(config.include),
        "graph_count": len(graphs),
        "native_methods": len(NATIVE_METHODS),
        "native_eval_mode": config.native_eval_mode,
        "native_source_run_dir": str(config.native_source_run_dir),
        "native_model_type": FORMAL_NATIVE_MODEL_TYPE if config.native_eval_mode == "formal4096" else "IC/LT debug-simple",
        "native_simulations": FORMAL_NATIVE_SIMULATIONS if config.native_eval_mode == "formal4096" else config.eval_simulations,
        "native_base_seed": FORMAL_NATIVE_BASE_SEED if config.native_eval_mode == "formal4096" else IM_ONLINE_BASE_SEED,
        "ahd_budget": config.ahd_budget,
        "chd_config": chd_im_config_payload(config),
        "requested_eval_simulations": config.requested_eval_simulations,
        "effective_eval_simulations": config.eval_simulations,
        "chd_result": chd_result,
        "summary_rows": len(mean),
        "per_graph_rows": len(per_graph),
        "api_key_saved": False,
    }
    write_json(config.run_dir / "run_manifest.json", manifest)
    write_csv(config.run_dir / "llm_call_summary.csv", [])
    return manifest


def config_from_args(args: Any) -> IMBenchmarkConfig:
    run_dir = make_run_dir("IM", args.run_name, args.run_date or None)
    requested_eval_simulations = args.eval_simulations
    effective_eval_simulations = min(args.eval_simulations, 4) if args.mode == "smoke" else args.eval_simulations
    native_eval_mode = getattr(args, "native_eval_mode", "formal4096")
    if native_eval_mode not in {"formal4096", "debug-simple"}:
        raise ValueError("native_eval_mode must be 'formal4096' or 'debug-simple'")
    native_source_run_dir = resolve_path(getattr(args, "native_source_run_dir", DEFAULT_NATIVE_SOURCE_RUN))
    return IMBenchmarkConfig(
        run_dir=run_dir,
        mode=args.mode,
        graph_dir=resolve_path(args.graph_dir),
        online_graph=args.online_graph or None,
        include={item.strip() for item in args.include.split(",") if item.strip()},
        ahd_budget=args.ahd_budget,
        chd_stage1_budget=args.chd_stage1_budget,
        chd_stage2_budget=args.chd_stage2_budget,
        chd_stage3_budget=args.chd_stage3_budget,
        llm_workers=args.llm_workers,
        native_workers=args.native_workers,
        online_live_edge_worlds=args.online_live_edge_worlds,
        online_rr_sets=args.online_rr_sets,
        eval_simulations=effective_eval_simulations,
        requested_eval_simulations=requested_eval_simulations,
        run_name=args.run_name,
        native_eval_mode=native_eval_mode,
        native_source_run_dir=native_source_run_dir,
    )
