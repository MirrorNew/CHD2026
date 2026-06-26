# -*- coding: utf-8 -*-
"""FunSearch policy."""

from __future__ import annotations

from typing import Any

from .common import AHDPolicy, display_name, valid_records

METHOD_SLUG = "funsearch"
METHOD_DISPLAY_NAME = display_name(METHOD_SLUG)
OFFICIAL_SOURCE = "https://github.com/google-deepmind/funsearch"
MECHANISM_NOTES = "Program database with island-style elite examples and repeated standalone mutations."


class Policy(AHDPolicy):
    slug = METHOD_SLUG
    display_name = METHOD_DISPLAY_NAME
    source = "official-structure FunSearch adapter"
    official_source = OFFICIAL_SOURCE
    core_mechanism = MECHANISM_NOTES
    approximation_notes = "Keeps island/elite pressure without vendoring the original distributed infrastructure."
    default_fallback_family = "fast_archive"

    def __init__(self, task_adapter, rng=None, islands: int = 4):
        super().__init__(task_adapter, rng)
        self.islands = islands
        self.next_island = 0

    def select_parent(self) -> dict[str, Any] | None:
        pool = valid_records(self.records)
        if not pool:
            return None
        island = self.next_island % self.islands
        self.next_island += 1
        island_pool = [row for row in pool if int(row.get("island", 0)) == island]
        ranked = sorted(island_pool or pool, key=lambda row: float(row.get("rank_score", -1.0)), reverse=True)
        return self.rng.choice(ranked[: min(4, len(ranked))])

    def prompt_guidance(self, index: int) -> str:
        island = index % self.islands
        return (
            f"Use FunSearch-style program database pressure for island {island}. Produce a short standalone program, "
            "recombining elite ideas without long explanatory text or complex infrastructure."
        )

    def fallback_family(self, index: int) -> str:
        return "fast_archive"

    def update(self, record):
        record.setdefault("operator", "island-elite-mutation")
        island = record.get("island", len(self.records))
        try:
            if island != island:  # NaN after CSV resume
                raise ValueError
            island_index = int(float(island))
        except (TypeError, ValueError):
            island_index = len(self.records)
        record["island"] = island_index % self.islands
        super().update(record)
