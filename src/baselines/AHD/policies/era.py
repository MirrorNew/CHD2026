# -*- coding: utf-8 -*-
"""ERA/PUCT-style AHD policy."""

from __future__ import annotations

import math
from typing import Any

from .common import AHDPolicy, child_count, display_name, valid_records

METHOD_SLUG = "era"
METHOD_DISPLAY_NAME = display_name(METHOD_SLUG)
OFFICIAL_SOURCE = "historical local HAST generic ERA/PUCT search policy"
MECHANISM_NOTES = "PUCT/ERA-style exploitation-exploration over generated heuristic states."


class Policy(AHDPolicy):
    slug = METHOD_SLUG
    display_name = METHOD_DISPLAY_NAME
    source = "direct port from local HAST generic ERA policy"
    official_source = OFFICIAL_SOURCE
    core_mechanism = MECHANISM_NOTES
    approximation_notes = "Uses the HAST paper-facing ERA/PUCT structure and injects the selected task adapter."
    default_fallback_family = "private_coverage"

    def select_parent(self) -> dict[str, Any] | None:
        pool = valid_records(self.records)
        if not pool:
            return None
        counts = child_count(self.records)
        total = max(2, len(self.records))

        def value(record: dict[str, Any]) -> float:
            score = max(0.0, float(record.get("rank_score", 0.0)))
            visits = counts[str(record.get("node_id") or record.get("candidate_id"))]
            return score + 1.35 * math.sqrt(math.log(total) / (1.0 + visits))

        return max(pool, key=value)

    def prompt_guidance(self, index: int) -> str:
        return (
            "Use ERA/PUCT-style search: exploit a strong parent while making one clear structural mutation. "
            "Keep sibling branches diverse and avoid adding expensive global graph routines."
        )

    def fallback_family(self, index: int) -> str:
        return "redundancy_prune" if index % 2 else "private_coverage"
