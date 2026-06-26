# -*- coding: utf-8 -*-
"""Ranking and Pareto selection for HAST candidates."""

from __future__ import annotations

import math
from typing import Any, Iterable

import pandas as pd

from .config import SearchWeights


def _rank_series(values: pd.Series, higher_is_better: bool) -> pd.Series:
    ordered = values.rank(method="average", ascending=not higher_is_better)
    if len(values) <= 1:
        return pd.Series([1.0] * len(values), index=values.index)
    return 1.0 - (ordered - 1.0) / (len(values) - 1.0)


def _rank_time_saturated(values: pd.Series, fast_quantile: float = 0.60) -> pd.Series:
    """Rank runtime, but stop over-rewarding candidates once they are fast enough."""

    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric[numeric.notna() & numeric.map(math.isfinite)]
    out = pd.Series(0.0, index=values.index)
    if len(finite) == 0:
        return out
    if len(finite) == 1:
        out.loc[finite.index] = 1.0
        return out
    threshold = _quantile(finite.astype(float).tolist(), fast_quantile)
    fast = finite <= threshold
    out.loc[fast[fast].index] = 1.0
    slow_idx = fast[~fast].index
    if len(slow_idx) == 1:
        out.loc[slow_idx] = 0.5
    elif len(slow_idx) > 1:
        out.loc[slow_idx] = 0.85 * _rank_series(numeric.loc[slow_idx], False)
    return out


def add_rank_scores(df: pd.DataFrame, weights: SearchWeights, root_auc_cNBI: float | None = None) -> pd.DataFrame:
    out = df.copy()
    valid = out["valid"].astype(bool)
    root_baseline = root_auc_cNBI if root_auc_cNBI is not None else out["auc_cNBI"].min()
    out["delta_root_auc_cNBI"] = out["auc_cNBI"] - root_baseline
    if "parent_auc_cNBI" in out:
        out["delta_auc_cNBI"] = out["auc_cNBI"] - pd.to_numeric(out["parent_auc_cNBI"], errors="coerce")
        out.loc[out["delta_auc_cNBI"].isna(), "delta_auc_cNBI"] = out.loc[out["delta_auc_cNBI"].isna(), "delta_root_auc_cNBI"]
    else:
        out["delta_auc_cNBI"] = out["delta_root_auc_cNBI"]
    out["rank_relative_credit"] = 0.0
    out["rank_fragmentation"] = 0.0
    out["rank_time"] = 0.0
    out["rank_absolute_quality"] = 0.0
    out["rank_early_fragmentation"] = 0.0
    out["rank_score"] = -1.0
    if valid.sum() == 0:
        return out
    idx = out.index[valid]
    out.loc[idx, "rank_relative_credit"] = _rank_series(out.loc[idx, "delta_auc_cNBI"], True)
    out.loc[idx, "rank_fragmentation"] = _rank_series(out.loc[idx, "R"], False)
    out.loc[idx, "rank_time"] = _rank_time_saturated(out.loc[idx, "time_s"])
    out.loc[idx, "rank_absolute_quality"] = _rank_series(out.loc[idx, "auc_cNBI"], True)
    early_cols = {"early_cNBI", "early_NCC", "early_GCC"}
    if early_cols.issubset(out.columns):
        out.loc[idx, "rank_early_fragmentation"] = (
            0.45 * _rank_series(out.loc[idx, "early_cNBI"], True)
            + 0.35 * _rank_series(out.loc[idx, "early_NCC"], True)
            + 0.20 * _rank_series(out.loc[idx, "early_GCC"], False)
        )
    out.loc[idx, "rank_score"] = (
        weights.relative_credit * out.loc[idx, "rank_relative_credit"]
        + weights.fragmentation * out.loc[idx, "rank_fragmentation"]
        + weights.time * out.loc[idx, "rank_time"]
        + weights.absolute_quality * out.loc[idx, "rank_absolute_quality"]
    )
    if early_cols.issubset(out.columns):
        out.loc[idx, "rank_score"] = 0.75 * out.loc[idx, "rank_score"] + 0.25 * out.loc[idx, "rank_early_fragmentation"]
    return out


def pareto_frontier(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [r for r in records if r.get("valid") and math.isfinite(float(r.get("auc_cNBI", float("nan"))))]
    frontier: list[dict[str, Any]] = []
    for row in rows:
        dominated = False
        for other in rows:
            if other is row:
                continue
            better_or_equal = (
                float(other["auc_cNBI"]) >= float(row["auc_cNBI"])
                and float(other["R"]) <= float(row["R"])
                and float(other["time_s"]) <= float(row["time_s"])
            )
            strictly_better = (
                float(other["auc_cNBI"]) > float(row["auc_cNBI"])
                or float(other["R"]) < float(row["R"])
                or float(other["time_s"]) < float(row["time_s"])
            )
            if better_or_equal and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(row)
    return sorted(frontier, key=lambda r: (float(r.get("rank_score", 0.0)), float(r["auc_cNBI"])), reverse=True)


def select_final_q_s(frontier: list[dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    if not frontier:
        return {"HAST-Final-Q": None, "HAST-Final-S": None}
    quality = max(frontier, key=lambda r: (float(r["auc_cNBI"]), -float(r["R"])))
    auc_floor = 0.90 * float(quality["auc_cNBI"])
    r_floor = float(quality["R"]) + 0.08
    guarded = [
        row
        for row in frontier
        if float(row["auc_cNBI"]) >= auc_floor and float(row["R"]) <= r_floor
    ]
    speed_pool = guarded or frontier
    speed = min(speed_pool, key=lambda r: (float(r["time_s"]), -float(r["auc_cNBI"]), float(r["R"])))
    return {"HAST-Final-Q": quality, "HAST-Final-S": speed}


def _quantile(values: list[float], q: float) -> float:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return float("nan")
    if len(clean) == 1:
        return clean[0]
    pos = (len(clean) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return clean[lo]
    return clean[lo] + (clean[hi] - clean[lo]) * (pos - lo)


def select_final_q_s_target_guard(frontier: list[dict[str, Any]]) -> dict[str, Any]:
    """Select final Q/S with a light target guard for low-R searches.

    The guard keeps the Stage 3 Pareto-front mechanism intact, but prevents the
    final quality label from choosing a candidate whose proxy R is excellent
    only by sacrificing both cNBI and runtime.
    """

    if not frontier:
        return {
            "HAST-Final-Q": None,
            "HAST-Final-S": None,
            "selection_metadata": {
                "final_selection_mode": "target_guard",
                "guard_status": "empty_frontier",
            },
        }

    rows = [
        row
        for row in frontier
        if math.isfinite(float(row.get("auc_cNBI", float("nan"))))
        and math.isfinite(float(row.get("R", float("nan"))))
        and math.isfinite(float(row.get("time_s", float("nan"))))
    ]
    if not rows:
        final = select_final_q_s(frontier)
        final["selection_metadata"] = {
            "final_selection_mode": "target_guard",
            "guard_status": "fallback_no_finite_rows",
        }
        return final

    auc_values = [float(row["auc_cNBI"]) for row in rows]
    time_values = [float(row["time_s"]) for row in rows]
    thresholds = {
        "auc_top25_floor": _quantile(auc_values, 0.75),
        "auc_median_floor": _quantile(auc_values, 0.50),
        "time_median_ceiling": _quantile(time_values, 0.50),
        "time_q75_ceiling": _quantile(time_values, 0.75),
    }
    strict_pool = [
        row
        for row in rows
        if float(row["auc_cNBI"]) >= thresholds["auc_top25_floor"]
        and float(row["time_s"]) <= thresholds["time_median_ceiling"]
    ]
    relaxed_pool = [
        row
        for row in rows
        if float(row["auc_cNBI"]) >= thresholds["auc_median_floor"]
        and float(row["time_s"]) <= thresholds["time_q75_ceiling"]
    ]
    min_pool_size = min(5, max(1, math.ceil(len(rows) * 0.40)))
    if len(strict_pool) >= min_pool_size:
        quality_pool = strict_pool
        guard_status = "strict_auc_top25_time_median"
    elif len(relaxed_pool) >= min_pool_size:
        quality_pool = relaxed_pool
        guard_status = "relaxed_auc_median_time_q75"
    else:
        quality_pool = rows
        guard_status = "fallback_full_frontier_min_pool"

    elite_quality_pool = [row for row in quality_pool if str(row.get("tree_role", "")) == "elite"]
    if elite_quality_pool:
        quality_pool = elite_quality_pool
        guard_status += "_elite_preferred"
    quality = min(quality_pool, key=lambda r: (float(r["R"]), float(r["time_s"]), -float(r["auc_cNBI"])))

    auc_floor = 0.90 * float(quality["auc_cNBI"])
    r_floor = float(quality["R"]) + 0.08
    speed_pool = [
        row
        for row in rows
        if float(row["auc_cNBI"]) >= auc_floor and float(row["R"]) <= r_floor
    ] or rows
    elite_speed_pool = [row for row in speed_pool if str(row.get("tree_role", "")) == "elite"]
    if elite_speed_pool:
        speed_pool = elite_speed_pool
    speed = min(speed_pool, key=lambda r: (float(r["time_s"]), float(r["R"]), -float(r["auc_cNBI"])))
    return {
        "HAST-Final-Q": quality,
        "HAST-Final-S": speed,
        "selection_metadata": {
            "final_selection_mode": "target_guard",
            "guard_status": guard_status,
            "frontier_size": len(frontier),
            "finite_frontier_size": len(rows),
            "strict_pool_size": len(strict_pool),
            "relaxed_pool_size": len(relaxed_pool),
            "min_pool_size": min_pool_size,
            "thresholds": thresholds,
            "quality_sort": "R asc, time_s asc, auc_cNBI desc within guarded pool",
            "speed_sort": "time_s asc, R asc, auc_cNBI desc within 90% auc and R+0.08 guard",
        },
    }


def select_final_q_s_by_mode(frontier: list[dict[str, Any]], mode: str = "legacy") -> dict[str, Any]:
    if mode == "legacy":
        return select_final_q_s(frontier)
    if mode == "target_guard":
        return select_final_q_s_target_guard(frontier)
    raise ValueError("final_selection_mode must be 'legacy' or 'target_guard'")
