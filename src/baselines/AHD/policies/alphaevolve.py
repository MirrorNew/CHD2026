# -*- coding: utf-8 -*-
"""AlphaEvolve/OpenEvolve-style archive policy."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np

from .common import AHDPolicy, code_feature_signature, display_name, valid_records

METHOD_SLUG = "alphaevolve"
METHOD_DISPLAY_NAME = display_name(METHOD_SLUG)
OFFICIAL_SOURCE = "local HAST AlphaEvolve-like policy; OpenEvolve reference: https://github.com/algorithmicsuperintelligence/openevolve"
MECHANISM_NOTES = "Archive and niche search balancing novelty with execution performance."


class Policy(AHDPolicy):
    slug = METHOD_SLUG
    display_name = METHOD_DISPLAY_NAME
    source = "direct port from local HAST AlphaEvolve-like archive policy"
    official_source = OFFICIAL_SOURCE
    core_mechanism = MECHANISM_NOTES
    approximation_notes = "DeepMind AlphaEvolve is not open-sourced; this uses the local archive/niche policy structure."
    default_fallback_family = "fast_archive"

    def select_parent(self) -> dict[str, Any] | None:
        pool = valid_records(self.records)
        if not pool:
            return None
        if len(pool) <= 1:
            return pool[0]
        bins: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in pool:
            bins[str(record.get("map_bin") or "root")].append(record)
        names = list(bins)
        weights = np.array([1.0 / math.sqrt(len(bins[name])) for name in names], dtype=float)
        weights = weights / weights.sum()
        selected = self.rng.choices(names, weights=weights.tolist(), k=1)[0]
        ranked = sorted(bins[selected], key=lambda row: float(row.get("rank_score", -1.0)), reverse=True)
        if self.rng.random() < 0.2:
            return self.rng.choice(pool)
        return ranked[0]

    def prompt_guidance(self, index: int) -> str:
        return (
            "Use AlphaEvolve/OpenEvolve-like archive search. Target a niche that differs from existing elites, "
            "but keep the program executable, compact, and bounded by local graph signals."
        )

    def fallback_family(self, index: int) -> str:
        return "fast_archive" if index % 2 else "harmony"

    def update(self, record):
        code = str(record.get("code", ""))
        length_bin = "short" if len(code) < 1800 else "long"
        loop_bin = "fewloops" if code.count("for ") + code.count("while ") < 7 else "manyloops"
        feature = code_feature_signature(code).split("+")[0]
        record["map_bin"] = f"{length_bin}:{loop_bin}:{feature}"
        record.setdefault("operator", "archive-niche-search")
        super().update(record)
