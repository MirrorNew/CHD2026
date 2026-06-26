# -*- coding: utf-8 -*-
"""Shared constants for the HAST project."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT
BENCHMARK_ROOT = PROJECT_ROOT / "network"
RUNS_ROOT = PROJECT_ROOT / "src" / "runs"
OUTPUTS_ROOT = RUNS_ROOT


def safe_run_token(text: str) -> str:
    token = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", text.strip())
    token = re.sub(r"_+", "_", token).strip("_")
    return token or "experiment"


def normalize_run_timestamp(timestamp_text: str | None = None) -> str:
    """Return a run timestamp in YYYYMMDD-HHMMSS form."""
    if not timestamp_text:
        return datetime.now().strftime("%Y%m%d-%H%M%S")
    text = timestamp_text.strip()
    if re.fullmatch(r"\d{8}-\d{6}", text):
        return text
    if re.fullmatch(r"\d{14}", text):
        return f"{text[:8]}-{text[8:]}"
    if re.fullmatch(r"\d{8}", text):
        return f"{text}-000000"
    raise ValueError("run timestamp must be YYYYMMDD-HHMMSS, YYYYMMDDHHMMSS, or YYYYMMDD")


def make_run_dir_name(task_slug: str, task_name: str, timestamp_text: str | None = None) -> str:
    task = safe_run_token(task_slug).upper()
    name = safe_run_token(task_name)
    return f"{normalize_run_timestamp(timestamp_text)}-{task}-{name}"


def make_run_dir(task_slug: str, task_name: str, timestamp_text: str | None = None) -> Path:
    return RUNS_ROOT / make_run_dir_name(task_slug, task_name, timestamp_text)

REAL_DATASETS = [
    "CEnew",
    "Collaboration",
    "condmat",
    "crime",
    "email",
    "Grid",
    "GrQC",
    "hamster",
    "HepPh",
    "PH",
    "Yeast",
]
DATASETS = REAL_DATASETS + ["Powerlaw_500"]
DATASET_RATES = {name: 0.30 for name in DATASETS}
DATASET_RATES["email"] = 0.40

MAIN_BUDGETS = {
    "stage1_candidates": 300,
    "stage2_llm_calls": 10,
    "stage3_candidates": 200,
    "candidates_per_llm_call": 1,
    "stage3_parent_limit": 24,
    "candidate_timeout_s": 90.0,
}

DELTA_CREDIT_MODES = ["parent", "root"]

LLM_DEFAULTS = {
    "model": "gpt-5.5",
    "reasoning_effort": "none",
    "temperature": 0.2,
    "base_url": "https://api.ritelt.com/v1",
}


@dataclass(frozen=True)
class SearchWeights:
    relative_credit: float
    fragmentation: float
    time: float
    absolute_quality: float

    def to_dict(self) -> dict[str, float]:
        return {
            "relative_credit": self.relative_credit,
            "fragmentation": self.fragmentation,
            "time": self.time,
            "absolute_quality": self.absolute_quality,
        }


STAGE1_WEIGHTS = SearchWeights(relative_credit=0.45, fragmentation=0.25, time=0.20, absolute_quality=0.10)
STAGE3_WEIGHTS = SearchWeights(relative_credit=0.40, fragmentation=0.25, time=0.25, absolute_quality=0.10)
