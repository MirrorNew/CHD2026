"""Audit that the standalone main workspace has the expected code and data mirrors."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


REQUIRED_DIRS = [
    "src/model",
    "src/baselines",
    "src/metrics",
    "src/configs",
    "src/scripts",
    "src/runs",
    "docs",
    "src/baselines/AHD",
    "src/baselines/AHD/policies",
    "src/baselines/ND_native_baseline",
    "src/baselines/ND_native_baseline/native_baseline",
    "src/baselines/ND_native_baseline/native_strong_baseline",
    "src/baselines/IM_native_baseline",
    "src/baselines/IM_native_baseline/native_baseline",
    "src/baselines/IM_native_baseline/native_strong_baseline",
    "src/experiments",
    "src/plotting",
    "network",
]

REQUIRED_FILES = [
    "README.md",
    ".gitignore",
    "src/baselines/AHD/__init__.py",
    "src/baselines/AHD/core.py",
    "src/baselines/AHD/task_adapters.py",
    "src/baselines/AHD/policies/era.py",
    "src/baselines/AHD/policies/mcts_ahd.py",
    "src/baselines/AHD/policies/clade_ahd.py",
    "src/baselines/AHD/policies/funsearch.py",
    "src/baselines/AHD/policies/alphaevolve.py",
    "src/baselines/ND_native_baseline/algorithms.py",
    "src/baselines/ND_native_baseline/README.md",
    "src/baselines/IM_native_baseline/README.md",
    "src/baselines/IM_native_baseline/native_baseline/__init__.py",
    "src/baselines/IM_native_baseline/native_strong_baseline/__init__.py",
    "src/experiments/README.md",
    "src/experiments/chd_main_search.py",
    "src/experiments/full_validation.py",
    "src/experiments/paper_source_tables.py",
    "src/experiments/motivation_observation_contract.py",
    "src/experiments/scaling_contract.py",
    "src/model/stage1_stage3_search.py",
    "src/plotting/README.md",
    "src/plotting/paper_figures.py",
    "src/configs/chd.yaml",
    "src/runs/README.md",
    "src/scripts/run_ahd_baselines.py",
    "src/scripts/run_full_validation.py",
]


def count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.rglob("*") if p.is_file())


def main() -> None:
    missing_dirs = [path for path in REQUIRED_DIRS if not (ROOT / path).is_dir()]
    missing_files = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]

    result = {
        "root": str(ROOT),
        "missing_dirs": missing_dirs,
        "missing_files": missing_files,
        "ahd_policy_file_count": count_files(ROOT / "src" / "baselines" / "AHD" / "policies"),
        "nd_native_file_count": count_files(ROOT / "src" / "baselines" / "ND_native_baseline"),
        "im_native_file_count": count_files(ROOT / "src" / "baselines" / "IM_native_baseline"),
        "experiment_file_count": count_files(ROOT / "src" / "experiments"),
        "plotting_file_count": count_files(ROOT / "src" / "plotting"),
        "run_record_file_count": count_files(ROOT / "src" / "runs"),
        "network_file_count": count_files(ROOT / "network"),
        "source_table_file_count": count_files(ROOT / "artifacts" / "source_tables"),
        "ok": not missing_dirs and not missing_files,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

