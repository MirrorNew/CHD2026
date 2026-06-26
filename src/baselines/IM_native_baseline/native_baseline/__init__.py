# -*- coding: utf-8 -*-
"""Lightweight native influence-maximization seed-selection baselines.

These wrappers are kept for the existing package layout.  They now point to
real IC-model IM baselines instead of centrality-only placeholders.
"""

from __future__ import annotations

from ..algorithms import (
    cluster_greedy_lt_seed_order,
    degree_discount_ic_seed_order,
    domim_seed_order,
    imm_seed_order,
    mia_seed_order,
    rr_greedy_seed_order,
)

__all__ = [
    "degree_discount_ic_seed_order",
    "mia_seed_order",
    "rr_greedy_seed_order",
    "imm_seed_order",
    "domim_seed_order",
    "cluster_greedy_lt_seed_order",
]
