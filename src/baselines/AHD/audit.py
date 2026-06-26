# -*- coding: utf-8 -*-
"""Standalone audit writer for AHD baseline adapters."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

try:
    from .core import write_audit  # type: ignore  # noqa: E402
    from .policies import all_policies  # type: ignore  # noqa: E402
    from .task_adapters import get_task_adapter  # type: ignore  # noqa: E402
except ImportError:
    from baselines.AHD.core import write_audit  # type: ignore  # noqa: E402
    from baselines.AHD.policies import all_policies  # type: ignore  # noqa: E402
    from baselines.AHD.task_adapters import get_task_adapter  # type: ignore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["nd"], default="nd")
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "runs" / "baseline_reasonableness_audit_cn.md"),
        help="Audit markdown output path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    task_adapter = get_task_adapter(args.task)
    write_audit(Path(args.output), all_policies(task_adapter), task_adapter)
    print(args.output)


if __name__ == "__main__":
    main()
