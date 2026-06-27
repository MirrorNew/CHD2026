# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import importlib.util
from dataclasses import replace
from pathlib import Path

import networkx as nx
import pandas as pd
import pytest

from experiments import im_12graph_benchmark as bench


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_im_12graph_benchmark.py"
SPEC = importlib.util.spec_from_file_location("run_im_12graph_benchmark_for_test", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
SCRIPT_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT_MODULE)
build_parser = SCRIPT_MODULE.build_parser


def _write_native_source(root: Path, rows: list[dict]) -> None:
    native_dir = root / "native"
    native_dir.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(native_dir / "per_graph_metrics.csv", index=False, encoding="utf-8-sig")
    (root / "run_manifest.json").write_text(
        json.dumps({"simulations": 4096, "base_seed": 20260626}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_im_benchmark_cli_defaults_use_formal_native_and_1024_online() -> None:
    args = build_parser().parse_args([])
    config = bench.config_from_args(args)

    assert config.online_live_edge_worlds == 1024
    assert config.online_rr_sets == 1024
    assert config.native_eval_mode == "formal4096"
    assert str(config.native_source_run_dir).endswith("src\\runs\\20260626-020000-IM-IM-lt-common-worlds-4096")


def test_formal_native_mode_loads_4096_rows_without_simplified_methods(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "native-source"
    _write_native_source(
        source,
        [
            {
                "dataset": "tiny",
                "method": "DegreeDiscountIC",
                "method_group": "native",
                "model_type": "LT_RandomThreshold",
                "k": 3,
                "valid": True,
                "spread": 2.0,
                "normalized_spread": 0.5,
                "spread_std": 0.1,
                "spread_ci95": 0.01,
                "simulations": 4096,
                "time_s": 0.2,
                "evaluation_time_s": 0.1,
                "seed_nodes": "[0, 1, 2]",
                "error": "",
            },
            {
                "dataset": "tiny",
                "method": "DebugOnly",
                "method_group": "native",
                "model_type": "LT",
                "k": 3,
                "valid": True,
                "spread": 3.0,
                "normalized_spread": 0.75,
                "spread_std": 0.1,
                "spread_ci95": 0.01,
                "simulations": 4,
                "time_s": 0.2,
                "evaluation_time_s": 0.1,
                "seed_nodes": "[0, 1, 2]",
                "error": "",
            },
        ],
    )
    args = build_parser().parse_args([])
    config = replace(
        bench.config_from_args(args),
        run_dir=tmp_path / "out",
        native_source_run_dir=source,
    )
    monkeypatch.setattr(
        bench,
        "NATIVE_METHODS",
        [("ShouldNotRun", lambda _g, _k: (_ for _ in ()).throw(AssertionError("debug native method called")))],
    )

    rows, mean = bench.evaluate_all(
        {"tiny": nx.path_graph(4)},
        config,
        native_enabled=True,
        ahd_fns=[],
        chd_fns=[],
    )

    assert len(rows) == 1
    assert rows[0]["method"] == "DegreeDiscountIC"
    assert rows[0]["model_type"] == "LT_RandomThreshold"
    assert rows[0]["simulations"] == 4096
    assert len(mean) == 1


def test_formal_native_loader_rejects_non_4096_source(tmp_path: Path) -> None:
    source = tmp_path / "native-source"
    _write_native_source(
        source,
        [
            {
                "dataset": "tiny",
                "method": "DegreeDiscountIC",
                "method_group": "native",
                "model_type": "LT_RandomThreshold",
                "k": 3,
                "valid": True,
                "spread": 2.0,
                "normalized_spread": 0.5,
                "simulations": 1024,
                "time_s": 0.2,
                "error": "",
            }
        ],
    )
    args = build_parser().parse_args([])
    config = replace(bench.config_from_args(args), native_source_run_dir=source)

    with pytest.raises(ValueError, match="4096"):
        bench.load_formal_native_rows(config)


def test_chd_im_config_payload_records_full_online_contract() -> None:
    args = build_parser().parse_args(
        [
            "--mode",
            "full",
            "--chd-stage1-budget",
            "300",
            "--chd-stage2-budget",
            "10",
            "--chd-stage3-budget",
            "200",
        ]
    )
    payload = bench.chd_im_config_payload(bench.config_from_args(args))

    assert payload["task"] == "im"
    assert payload["root"] == "DegreeDiscountIC"
    assert payload["candidate_interface"] == "def seed_order(G, k)"
    assert payload["online_graph"] == "network/12main_network/Powerlaw_500.edgelist"
    assert payload["online_live_edge_worlds"] == 1024
    assert payload["online_rr_sets"] == 1024
    assert payload["p"] == 0.1
    assert payload["base_seed"] == 20260626
    assert (payload["stage1"], payload["stage2"], payload["stage3"]) == (300, 10, 200)
    assert payload["ranking_formula"] == "0.7 spread_ic + 0.1 relative_spread_ic + 0.1 rr_coverage + 0.1 time_s"
