# -*- coding: utf-8 -*-
"""HSEvo policy."""

from __future__ import annotations

from .common import AHDPolicy, display_name

METHOD_SLUG = "hsevo"
METHOD_DISPLAY_NAME = display_name(METHOD_SLUG)
OFFICIAL_SOURCE = "https://github.com/datphamvn/HSEvo"
MECHANISM_NOTES = "Diversity-driven harmony memory combined with GA-style update operators."


class Policy(AHDPolicy):
    slug = METHOD_SLUG
    display_name = METHOD_DISPLAY_NAME
    source = "official-structure HSEvo adapter"
    official_source = OFFICIAL_SOURCE
    core_mechanism = MECHANISM_NOTES
    approximation_notes = "Keeps harmony memory, crossover, and pitch-adjustment pressure with a local evaluator."
    default_fallback_family = "harmony"

    def prompt_guidance(self, index: int) -> str:
        operator = ["harmony memory consideration", "pitch adjustment", "diversity crossover"][(index - 1) % 3]
        return (
            f"Use HSEvo-style {operator}. Preserve useful elite structure, blend one diverse scoring idea, "
            "and make a small bounded parameter change."
        )

    def fallback_family(self, index: int) -> str:
        return "harmony"

    def update(self, record):
        record.setdefault("operator", "harmony-search")
        record.setdefault("lineage", "harmony-memory")
        super().update(record)
