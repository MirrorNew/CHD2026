# -*- coding: utf-8 -*-

from __future__ import annotations

import networkx as nx

from model.candidate import extract_code, make_program
from model.im_task import (
    IM_FUNCTION_NAME,
    IM_ROOT_CODE,
    build_fixed_live_edge_worlds,
    build_fixed_rr_sets,
    im_seed_budget,
    rank_ahd_online_records,
    rank_im_records,
)
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
