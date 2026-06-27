# -*- coding: utf-8 -*-
"""Compatibility wrapper for the canonical IM LT evaluator."""

from __future__ import annotations

from metrics.IM_LT_evaluator import LTSpreadResult, evaluate_lt_spread, evaluate_lt_spread_many, normalize_seed_order

__all__ = ["LTSpreadResult", "normalize_seed_order", "evaluate_lt_spread", "evaluate_lt_spread_many"]
