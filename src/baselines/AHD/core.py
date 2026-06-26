# -*- coding: utf-8 -*-
"""Shared utilities for AHD baseline smoke runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Protocol


METHOD_DISPLAY_NAMES = {
    "era": "ERA",
    "eoh": "Evolution of Heuristics (EoH)",
    "reevo": "Reflective Evolution (ReEvo)",
    "mcts_ahd": "MCTS-AHD",
    "hifo_prompt": "HiFo-Prompt",
    "funsearch": "FunSearch",
    "hsevo": "HSEvo",
    "clade_ahd": "Clade-AHD",
    "alphaevolve": "AlphaEvolve",
}


class TextProvider(Protocol):
    def generate(self, prompt: str, *, n: int = 1) -> list[str]:
        ...


def summarize_records_for_prompt(records: list[dict[str, Any]], limit: int = 4) -> str:
    if not records:
        return "No prior candidates for this method."
    sorted_records = sorted(records, key=lambda row: float(row.get("rank_score", -1.0)), reverse=True)
    view = []
    for row in sorted_records[:limit]:
        view.append(
            {
                "candidate_id": row.get("candidate_id"),
                "valid": row.get("valid"),
                "R": row.get("R"),
                "cNBI": row.get("cNBI"),
                "spread": row.get("spread"),
                "coverage": row.get("coverage"),
                "Time": row.get("Time"),
                "rank_score": row.get("rank_score"),
            }
        )
    return json.dumps(view, ensure_ascii=False)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = fieldnames or sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def rows_without_code(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep CSVs compact and avoid leaking generated source into reports."""
    return [{key: value for key, value in row.items() if key != "code"} for row in rows]


def write_audit(path: Path, policies: list[Any], task_adapter: Any) -> None:
    lines = [f"# {task_adapter.task_name} AHD Baseline Reproduction Audit", ""]
    lines.append(f"- Task slug: {task_adapter.slug}")
    lines.append(f"- Candidate interface: `{task_adapter.function_name}(G)`")
    lines.append("")
    lines.append("All method names below are displayed without the internal adapter suffix.")
    lines.append("")
    for policy in policies:
        lines.extend(
            [
                f"## {policy.display_name}",
                "",
                f"- Implementation source: {policy.source}",
                f"- Official/source reference: {policy.official_source}",
                f"- Core mechanism preserved: {policy.core_mechanism}",
                f"- Known non-identical parts: {policy.approximation_notes}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
