"""Canonical metric and evaluator exports grouped by task."""

from .ND_fragmentation import auc_mean, compute_metrics, summarize_metrics
from .IM_IC_evaluator import build_fixed_live_edge_worlds, build_fixed_rr_sets, fixed_live_edge_spread, rr_coverage
from .IM_LT_evaluator import LTSpreadResult, evaluate_lt_spread, evaluate_lt_spread_many

__all__ = [
    "auc_mean",
    "compute_metrics",
    "summarize_metrics",
    "build_fixed_live_edge_worlds",
    "build_fixed_rr_sets",
    "fixed_live_edge_spread",
    "rr_coverage",
    "LTSpreadResult",
    "evaluate_lt_spread",
    "evaluate_lt_spread_many",
]
