# -*- coding: utf-8 -*-
"""MCTS-AHD policy."""

from __future__ import annotations

import math
from typing import Any

from .common import AHDPolicy, child_count, depth_of, display_name, record_by_id, valid_records

METHOD_SLUG = "mcts_ahd"
METHOD_DISPLAY_NAME = display_name(METHOD_SLUG)
OFFICIAL_SOURCE = "https://github.com/zz1358m/MCTS-AHD-master"
MECHANISM_NOTES = "Tree expansion with UCT-style parent selection over heuristic-design states."


class Policy(AHDPolicy):
    slug = METHOD_SLUG
    display_name = METHOD_DISPLAY_NAME
    source = "official-structure MCTS-AHD adapter"
    official_source = OFFICIAL_SOURCE
    core_mechanism = MECHANISM_NOTES
    approximation_notes = "Uses UCT parent selection and explicit expansion operators with the injected task evaluator."
    default_fallback_family = "two_hop"

    def select_parent(self) -> dict[str, Any] | None:
        pool = valid_records(self.records)
        if not pool:
            return None
        by_id = record_by_id(self.records)
        counts = child_count(self.records)
        total = max(2, len(self.records))

        def value(record: dict[str, Any]) -> float:
            score = max(0.0, float(record.get("rank_score", 0.0)))
            visits = counts[str(record.get("node_id") or record.get("candidate_id"))]
            depth_bonus = 1.0 / (1.0 + 0.12 * depth_of(record, by_id))
            return score * depth_bonus + 1.1 * math.sqrt(math.log(total) / (1.0 + visits))

        return max(pool, key=value)

    def prompt_guidance(self, index: int) -> str:
        action = ["initialization", "mechanism mutation", "parameter mutation", "crossover"][(index - 1) % 4]
        return (
            f"Use MCTS-AHD style expansion with action={action}. Treat the parent as one heuristic-design state. "
            "Generate exactly one child program with one greedy construction path, capped local scans, at most 80 "
            "post-processing checks, and no internal multi-variant search. This method must stay below the evaluator timeout."
        )

    def fallback_family(self, index: int) -> str:
        return "two_hop"

    def update(self, record):
        record.setdefault("operator", "mcts-expansion")
        super().update(record)
