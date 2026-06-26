# -*- coding: utf-8 -*-
"""Reflective Evolution policy."""

from __future__ import annotations

import json

from .common import AHDPolicy, display_name

METHOD_SLUG = "reevo"
METHOD_DISPLAY_NAME = display_name(METHOD_SLUG)
OFFICIAL_SOURCE = "https://github.com/ai4co/reevo"
MECHANISM_NOTES = "Short-term and long-term reflection guide evolutionary mutation and crossover."


class Policy(AHDPolicy):
    slug = METHOD_SLUG
    display_name = METHOD_DISPLAY_NAME
    source = "official-structure ReEvo adapter"
    official_source = OFFICIAL_SOURCE
    core_mechanism = MECHANISM_NOTES
    approximation_notes = "Keeps reflection-guided revision but uses local task prompts and evaluator."
    default_fallback_family = "redundancy_prune"

    def _reflection_summary(self) -> str:
        top = self.examples(limit=3)
        if not top:
            return "No prior reflection. Start from the task root and explain one likely weakness before coding."
        view = [
            {
                "score": row.get("rank_score"),
                "valid": row.get("valid"),
                "operator": row.get("operator"),
                "error": row.get("error", ""),
            }
            for row in top
        ]
        return json.dumps(view, ensure_ascii=False)

    def prompt_guidance(self, index: int) -> str:
        return (
            "Use ReEvo-style reflection. Short-term reflection: identify one concrete parent weakness. "
            "Long-term reflection from prior candidates: "
            f"{self._reflection_summary()}. Then revise the heuristic with one bounded mutation or crossover."
        )

    def fallback_family(self, index: int) -> str:
        return "redundancy_prune"

    def update(self, record):
        record.setdefault("operator", "reflective-mutation")
        super().update(record)
