# -*- coding: utf-8 -*-
"""Clade-AHD policy."""

from __future__ import annotations

from typing import Any

from .common import AHDPolicy, code_feature_signature, display_name, grouped_records, thompson_sample_group, valid_records

METHOD_SLUG = "clade_ahd"
METHOD_DISPLAY_NAME = display_name(METHOD_SLUG)
OFFICIAL_SOURCE = "https://github.com/Mriya0306/Clade-AHD"
MECHANISM_NOTES = "Clade-level Bayesian belief, Thompson sampling, depth attenuation, and branch freezing."


class Policy(AHDPolicy):
    slug = METHOD_SLUG
    display_name = METHOD_DISPLAY_NAME
    source = "official-structure Clade-AHD adapter"
    official_source = OFFICIAL_SOURCE
    core_mechanism = MECHANISM_NOTES
    approximation_notes = "Implements clade metadata locally rather than vendoring the full official repository."
    default_fallback_family = "two_hop"

    def select_parent(self) -> dict[str, Any] | None:
        pool = valid_records(self.records)
        if not pool:
            return None
        if len(pool) <= 2:
            return pool[-1]
        groups = grouped_records(self.records, "generic_clade")
        scores = [float(row.get("rank_score", 0.0)) for row in pool]
        selected = thompson_sample_group(groups, self.rng, scores)
        ranked = sorted(groups[selected], key=lambda row: float(row.get("rank_score", -1.0)), reverse=True)
        return self.rng.choice(ranked[: min(5, len(ranked))])

    def prompt_guidance(self, index: int) -> str:
        return (
            "Use Clade-AHD style search. Preserve the chosen clade's useful mechanism, test a nearby family, "
            "and freeze unpromising complexity: cache local neighborhoods, cap two-hop scans, and avoid all-pairs loops."
        )

    def fallback_family(self, index: int) -> str:
        return "two_hop" if index % 2 else "redundancy_prune"

    def update(self, record):
        record.setdefault("operator", "clade-thompson-sampling")
        record["generic_clade"] = code_feature_signature(str(record.get("code", "")))
        super().update(record)
