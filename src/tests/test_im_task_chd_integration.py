# -*- coding: utf-8 -*-

from __future__ import annotations

import networkx as nx

from metrics.IM_IC_evaluator import build_fixed_live_edge_worlds, build_fixed_rr_sets, fixed_live_edge_spread, rr_coverage
from metrics.IM_LT_evaluator import evaluate_lt_spread_many
from metrics.ND_fragmentation import compute_metrics
from model.candidate import extract_code, make_program
from model.im_task import (
    IM_FUNCTION_NAME,
    IM_ROOT_CODE,
    im_seed_budget,
    rank_ahd_online_records,
    rank_im_records,
)
from model.im_lt_evaluator import evaluate_lt_spread as compat_evaluate_lt_spread
from metrics.IM_LT_evaluator import evaluate_lt_spread
from model.stage1_stage3_search import default_config, task_function_name, task_root_code


def test_im_task_root_is_degree_discount_seed_order() -> None:
    assert "def seed_order" in IM_ROOT_CODE
    assert "discount" in IM_ROOT_CODE
    program = make_program(IM_ROOT_CODE, function_name=IM_FUNCTION_NAME)
    assert program.candidate_id


def test_candidate_extraction_supports_seed_order_without_breaking_default() -> None:
    response = "```python\ndef seed_order(G, k):\n    return list(G.nodes())[:k]\n```"
    assert extract_code(response, function_name="seed_order").startswith("def seed_order")
    nd = default_config("unit")
    im = default_config("unit", task="im")
    assert task_function_name(nd) == "degree_order"
    assert task_function_name(im) == "seed_order"
    assert "def degree_order" in task_root_code(nd)
    assert "def seed_order" in task_root_code(im)


def test_im_seed_budget_and_fixed_samples_are_reproducible() -> None:
    graph = nx.path_graph(20)
    assert im_seed_budget(20) == 3
    assert im_seed_budget(500) == 12
    assert build_fixed_live_edge_worlds(graph, 4, seed=7) == build_fixed_live_edge_worlds(graph, 4, seed=7)
    assert build_fixed_rr_sets(graph, 8, seed=7) == build_fixed_rr_sets(graph, 8, seed=7)


def test_im_rank_score_formula_and_ahd_spread_only() -> None:
    rows = [
        {"candidate_id": "a", "valid": True, "spread_ic": 0.4, "relative_spread_ic": 0.1, "rr_coverage": 0.2, "time_s": 2.0},
        {"candidate_id": "b", "valid": True, "spread_ic": 0.5, "relative_spread_ic": 0.0, "rr_coverage": 0.1, "time_s": 1.0},
    ]
    chd = rank_im_records(rows)
    by_id = {row["candidate_id"]: row for row in chd}
    expected_b = 0.7 * 1.0 + 0.1 * 0.0 + 0.1 * 0.0 + 0.1 * 1.0
    assert abs(by_id["b"]["rank_score"] - expected_b) < 1e-12
    ahd = rank_ahd_online_records(rows)
    by_id = {row["candidate_id"]: row for row in ahd}
    assert by_id["b"]["rank_score"] == by_id["b"]["rank_spread_ic"]


def test_canonical_metric_imports_and_compatibility_wrapper() -> None:
    graph = nx.path_graph(6)
    worlds = build_fixed_live_edge_worlds(graph, 3, seed=11)
    rr_sets = build_fixed_rr_sets(graph, 5, seed=11)
    assert fixed_live_edge_spread(graph, [0], worlds) >= 0.0
    assert rr_coverage([0], rr_sets) >= 0.0
    assert evaluate_lt_spread_many(graph, {"a": [0]}, simulations=4, base_seed=11)["a"].simulations == 4
    assert compat_evaluate_lt_spread is evaluate_lt_spread
    rows = compute_metrics(graph, [0, 1, 2], rate=0.5)
    assert not rows.empty
