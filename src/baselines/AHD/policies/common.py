# -*- coding: utf-8 -*-
"""Shared policy mechanics for AHD baselines."""

from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from typing import Any

import numpy as np

from ..core import METHOD_DISPLAY_NAMES, summarize_records_for_prompt
from ..task_adapters import BaseTaskAdapter


def valid_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in records if bool(row.get("ok"))]


def child_count(records: list[dict[str, Any]]) -> Counter:
    return Counter(str(row.get("parent_id") or "") for row in records)


def record_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("node_id") or row.get("candidate_id")): row for row in records}


def depth_of(record: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> int:
    depth = 0
    cur = str(record.get("parent_id") or "")
    seen: set[str] = set()
    while cur and cur in by_id and cur not in seen:
        seen.add(cur)
        depth += 1
        cur = str(by_id[cur].get("parent_id") or "")
    return depth


def code_feature_signature(code: str) -> str:
    probes = {
        "heap": "heap" in code,
        "core": "core" in code.lower(),
        "tri": "tri" in code.lower() or "cluster" in code.lower(),
        "component": "component" in code.lower() or "connected" in code.lower(),
        "neighbor": "neighbor" in code.lower() or "nbr" in code.lower(),
        "twohop": "2" in code and ("hop" in code.lower() or "two" in code.lower()),
        "coverage": "cover" in code.lower() or "dominat" in code.lower(),
        "prune": "prune" in code.lower() or "trial" in code.lower(),
    }
    active = [key for key, value in probes.items() if value]
    return "+".join(active[:3]) if active else "simple"


class AHDPolicy:
    slug = "base"
    display_name = "Base"
    source = "local adapter"
    official_source = "local"
    core_mechanism = "Base policy"
    approximation_notes = "Not a standalone method."
    default_fallback_family = "root"

    def __init__(self, task_adapter: BaseTaskAdapter, rng: random.Random | None = None) -> None:
        self.task_adapter = task_adapter
        self.rng = rng or random.Random(20260603)
        self.records: list[dict[str, Any]] = []

    def select_parent(self) -> dict[str, Any] | None:
        pool = valid_records(self.records)
        if not pool:
            return None
        return max(pool, key=lambda record: float(record.get("rank_score", -1.0)))

    def examples(self, limit: int = 4) -> list[dict[str, Any]]:
        return sorted(valid_records(self.records), key=lambda row: float(row.get("rank_score", -1.0)), reverse=True)[:limit]

    def update(self, record: dict[str, Any]) -> None:
        record.setdefault("node_id", str(record.get("candidate_id") or f"{self.slug}-{len(self.records) + 1}"))
        if self.records and not record.get("parent_id"):
            parent = self.select_parent()
            if parent:
                record["parent_id"] = str(parent.get("node_id") or parent.get("candidate_id") or "")
        self.records.append(record)

    def prompt_guidance(self, index: int) -> str:
        del index
        return self.core_mechanism

    def fallback_family(self, index: int) -> str:
        del index
        return self.default_fallback_family

    def fallback_code(self, index: int) -> str:
        return self.task_adapter.fallback_code(self.slug, index, self.fallback_family(index))

    def build_prompt(self, index: int) -> str:
        parent = self.select_parent()
        parent_code = str(parent.get("code", self.task_adapter.root_code)) if parent else self.task_adapter.root_code
        top_rows = summarize_records_for_prompt(self.records, limit=4)
        parent_meta = json.dumps(
            {
                "parent_id": parent.get("node_id") if parent else None,
                "parent_score": parent.get("rank_score") if parent else None,
                "operator": parent.get("operator") if parent else None,
                "lineage": parent.get("lineage") if parent else None,
            },
            ensure_ascii=False,
        )
        return f"""
Task: {self.task_adapter.task_name} on an undirected NetworkX graph.

Candidate interface:
```python
{self.task_adapter.candidate_interface}
```

Task-specific evaluation:
{self.task_adapter.task_guidance}

Method: {self.display_name}
Search step: {index}
Method-specific guidance:
{self.prompt_guidance(index)}

Current parent metadata:
{parent_meta}

Current parent/root code:
```python
{parent_code}
```

Recent search evidence:
{top_rows}

Forbidden:
{self.task_adapter.forbidden_guidance}
- restricted builtins such as map/filter/eval/exec/open; use explicit loops or list comprehensions.

Return only raw Python code or one Python code block defining the requested {self.task_adapter.function_name} interface.
""".strip()


def display_name(slug: str) -> str:
    return METHOD_DISPLAY_NAMES[slug]


def grouped_records(records: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in valid_records(records):
        groups[str(record.get(key) or "default")].append(record)
    return groups


def thompson_sample_group(
    groups: dict[str, list[dict[str, Any]]],
    rng: random.Random,
    scores: list[float],
) -> str:
    if not groups:
        return "default"
    median = float(np.median(scores)) if scores else 0.0
    samples = []
    for name, group in groups.items():
        wins = sum(float(record.get("rank_score", 0.0)) >= median for record in group)
        losses = max(0, len(group) - wins)
        theta = rng.betavariate(1 + wins, 1 + losses)
        theta += 0.08 / math.sqrt(len(group))
        samples.append((theta, name))
    return max(samples, key=lambda item: item[0])[1]
