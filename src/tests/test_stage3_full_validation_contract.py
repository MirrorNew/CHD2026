# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pandas as pd

from model.reference_check import ReferenceTarget, write_reference_check
from model.data import read_graph
from model.ranking import select_final_q_s_by_mode
from experiments.full_validation import load_stage3_final_programs


def test_load_stage3_final_programs_uses_fixed_labels(tmp_path: Path) -> None:
    final_dir = tmp_path / "final"
    final_dir.mkdir()
    code = "def degree_order(G):\n    return list(G.nodes())\n"
    (final_dir / "HAST-Final-Q.py").write_text(code, encoding="utf-8")
    (final_dir / "HAST-Final-S.py").write_text(code, encoding="utf-8")

    programs, method_names = load_stage3_final_programs(final_dir)

    assert method_names == ["HAST-Final-Q", "HAST-Final-S"]
    assert [program.source_stage for program in programs] == ["HAST-Final-Q", "HAST-Final-S"]


def test_reference_check_gate_passes_only_stage3_fixed_labels(tmp_path: Path) -> None:
    out_dir = tmp_path / "full_validation"
    out_dir.mkdir()
    pd.DataFrame(
        [
            {
                "method": "HAST-Final-Q",
                "candidate_id": "q",
                "mean_auc_cNBI": 10.0,
                "mean_R": 0.2,
                "mean_time_s": 1.0,
            },
            {
                "method": "HAST-Final-S",
                "candidate_id": "s",
                "mean_auc_cNBI": 8.0,
                "mean_R": 0.3,
                "mean_time_s": 0.5,
            },
        ]
    ).to_csv(out_dir / "method_mean_metrics.csv", index=False, encoding="utf-8-sig")

    payload = write_reference_check(
        out_dir,
        references=[
            ReferenceTarget("legacy_q", "q-old", auc_cNBI=9.0, R=0.25, time_s=1.2),
            ReferenceTarget("legacy_s", "s-old", auc_cNBI=7.0, R=None, time_s=0.6),
        ],
    )

    assert payload["gate"]["paper_refresh_allowed"] is True
    written = json.loads((out_dir / "legacy_reference_check.json").read_text(encoding="utf-8"))
    assert written["gate"]["legacy_q_passed_by_hast_final_q"] is True
    assert written["gate"]["legacy_s_passed_by_hast_final_s"] is True


def test_synthetic_proxy_graphs_are_readable_and_connected() -> None:
    expected_nodes = {
        "SynthPL500_g25_s11": 500,
        "SynthPL1000_g22_s17": 1000,
        "SynthComm1000_s23": 1000,
        "SynthGridSW1200_s31": 1200,
    }
    for dataset, nodes in expected_nodes.items():
        graph = read_graph(dataset)
        assert graph.number_of_nodes() == nodes
        assert graph.number_of_edges() >= nodes - 1
        assert nx.is_connected(graph)


def test_target_guard_final_selection_avoids_low_auc_slow_r_trap() -> None:
    frontier = [
        {"candidate_id": "low-r-trap", "valid": True, "auc_cNBI": 320.0, "R": 0.340, "time_s": 2.0},
        {"candidate_id": "balanced-target", "valid": True, "auc_cNBI": 370.0, "R": 0.368, "time_s": 0.7},
        {"candidate_id": "fast-support", "valid": True, "auc_cNBI": 360.0, "R": 0.380, "time_s": 0.3},
        {"candidate_id": "quality-slow", "valid": True, "auc_cNBI": 380.0, "R": 0.390, "time_s": 1.8},
    ]

    selected = select_final_q_s_by_mode(frontier, "target_guard")

    assert selected["HAST-Final-Q"]["candidate_id"] == "balanced-target"
    assert selected["HAST-Final-S"]["candidate_id"] == "fast-support"
    assert selected["selection_metadata"]["guard_status"] == "relaxed_auc_median_time_q75"

