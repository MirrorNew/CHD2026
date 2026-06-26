# -*- coding: utf-8 -*-
"""Evolution of Heuristics policy."""

from __future__ import annotations

from .common import AHDPolicy, display_name

METHOD_SLUG = "eoh"
METHOD_DISPLAY_NAME = display_name(METHOD_SLUG)
OFFICIAL_SOURCE = "https://github.com/FeiLiu36/EoH"
MECHANISM_NOTES = "Co-evolves natural-language heuristic thought and executable code."


class Policy(AHDPolicy):
    slug = METHOD_SLUG
    display_name = METHOD_DISPLAY_NAME
    source = "official-structure EoH adapter"
    official_source = OFFICIAL_SOURCE
    core_mechanism = MECHANISM_NOTES
    approximation_notes = "Keeps thought-code co-evolution operators while using the injected task evaluator."
    default_fallback_family = "private_coverage"

    def prompt_guidance(self, index: int) -> str:
        operator = ["e1 initialization", "e2 crossover", "m1 local mutation", "m2 semantic mutation"][(index - 1) % 4]
        return (
            f"Use EoH-style {operator}. First write one concise heuristic thought, then implement the task function. "
            "Mutate both the natural-language design idea and code-level scoring rule; keep the executable concise."
        )

    def fallback_family(self, index: int) -> str:
        return "private_coverage" if index % 2 else "redundancy_prune"

    def update(self, record):
        record.setdefault("operator", "eoh-thought-code")
        record.setdefault("lineage", "thought-code-coevolution")
        super().update(record)
