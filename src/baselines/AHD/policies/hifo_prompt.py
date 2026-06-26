# -*- coding: utf-8 -*-
"""HiFo-Prompt policy."""

from __future__ import annotations

import json

from .common import AHDPolicy, display_name

METHOD_SLUG = "hifo_prompt"
METHOD_DISPLAY_NAME = display_name(METHOD_SLUG)
OFFICIAL_SOURCE = "https://github.com/Challenger-XJTU/HiFo-Prompt"
MECHANISM_NOTES = "Hindsight insight pool plus foresight navigator for exploration-exploitation control."


class Policy(AHDPolicy):
    slug = METHOD_SLUG
    display_name = METHOD_DISPLAY_NAME
    source = "official-structure HiFo-Prompt adapter"
    official_source = OFFICIAL_SOURCE
    core_mechanism = MECHANISM_NOTES
    approximation_notes = "Keeps insight-pool/navigator control while using local task logs and evaluator."
    default_fallback_family = "private_coverage"

    def _insight_pool(self) -> str:
        top = self.examples(limit=4)
        if not top:
            return "No hindsight insights yet."
        insights = [
            {
                "score": row.get("rank_score"),
                "feature": row.get("generic_clade") or row.get("map_bin") or row.get("operator"),
                "valid": row.get("valid"),
            }
            for row in top
        ]
        return json.dumps(insights, ensure_ascii=False)

    def prompt_guidance(self, index: int) -> str:
        mode = ["exploit", "explore", "balance"][(index - 1) % 3]
        return (
            f"Use HiFo-Prompt with foresight mode={mode}. Hindsight insight pool: {self._insight_pool()}. "
            "Choose whether to exploit the strongest signal or explore a contrasting bounded local signal, then code one candidate."
        )

    def fallback_family(self, index: int) -> str:
        return "private_coverage" if index % 2 else "two_hop"

    def update(self, record):
        record.setdefault("operator", "hindsight-foresight")
        super().update(record)
