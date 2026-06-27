# -*- coding: utf-8 -*-
"""Command entry for the IM 12-graph benchmark."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from experiments.im_12graph_benchmark import config_from_args, run_benchmark  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--graph-dir", default="network/12main_network")
    parser.add_argument("--online-graph", default="network/12main_network/Powerlaw_500.edgelist")
    parser.add_argument("--key-file", default="")
    parser.add_argument("--include", default="native,ahd,chd")
    parser.add_argument("--ahd-budget", type=int, default=1)
    parser.add_argument("--chd-stage1-budget", type=int, default=3)
    parser.add_argument("--chd-stage2-budget", type=int, default=1)
    parser.add_argument("--chd-stage3-budget", type=int, default=3)
    parser.add_argument("--llm-workers", type=int, default=4)
    parser.add_argument("--native-workers", type=int, default=8)
    parser.add_argument("--online-live-edge-worlds", type=int, default=1024)
    parser.add_argument("--online-rr-sets", type=int, default=1024)
    parser.add_argument("--eval-simulations", type=int, default=128)
    parser.add_argument("--rr-sets", type=int, default=2048, help="Accepted for full-plan CLI compatibility.")
    parser.add_argument("--max-rr-sets", type=int, default=20000, help="Accepted for full-plan CLI compatibility.")
    parser.add_argument("--native-eval-mode", choices=["formal4096", "debug-simple"], default="formal4096")
    parser.add_argument(
        "--native-source-run-dir",
        default="src/runs/20260626-020000-IM-IM-lt-common-worlds-4096",
        help="Formal native LT source run used when --native-eval-mode=formal4096.",
    )
    parser.add_argument("--run-name", default="im12-smoke")
    parser.add_argument("--run-date", default="")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.key_file:
        key_path = Path(args.key_file)
        if not key_path.is_absolute():
            key_path = ROOT / key_path
        if key_path.exists() and not os.environ.get("HAST_LLM_API_KEY"):
            os.environ["HAST_LLM_API_KEY"] = key_path.read_text(encoding="utf-8").strip().splitlines()[0].strip()

    config = config_from_args(args)
    result = run_benchmark(config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
