# -*- coding: utf-8 -*-
"""Smoke runner for AHD baselines."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from model.config import make_run_dir  # noqa: E402
from model.llm import OpenAICompatibleLLMProvider  # noqa: E402

from .core import rows_without_code, write_audit, write_csv  # noqa: E402
from .task_adapters import get_task_adapter  # noqa: E402
from .policies import all_policies  # noqa: E402


def safe_token(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in text).strip("._") or "run"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", default="ahd_smoke")
    parser.add_argument("--run-date", default="", help="Override run timestamp. Accepts YYYYMMDD-HHMMSS, YYYYMMDDHHMMSS, or legacy YYYYMMDD.")
    parser.add_argument("--task", choices=["nd", "im"], default="nd")
    parser.add_argument("--budget", type=int, default=1, help="Candidates per baseline for smoke.")
    parser.add_argument("--use-llm", action="store_true", help="Call the configured LLM instead of deterministic fallback code.")
    parser.add_argument(
        "--methods",
        default="",
        help="Optional comma-separated method slugs to run, e.g. era,clade_ahd.",
    )
    return parser.parse_args()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_policy_smoke(
    policy,
    task_adapter,
    graphs: dict[str, Any],
    run_dir: Path,
    budget: int,
    provider,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    call_rows: list[dict[str, Any]] = []
    for idx in range(1, budget + 1):
        prompt = policy.build_prompt(idx)
        prompt_path = run_dir / "prompts" / policy.slug / f"{idx:04d}.txt"
        write_text(prompt_path, prompt)
        call_row = {
            "method": policy.display_name,
            "method_slug": policy.slug,
            "task": task_adapter.slug,
            "candidate_index": idx,
            "llm_mode": "real" if provider is not None else "deterministic_fallback",
            "api_key_saved": False,
            "prompt_path": str(prompt_path),
            "ok": True,
            "error": "",
        }
        if provider is None:
            raw = policy.fallback_code(idx)
        else:
            try:
                raw = provider.generate(prompt, n=1)[0]
            except Exception as exc:  # noqa: BLE001
                raw = ""
                call_row["ok"] = False
                call_row["error"] = f"{type(exc).__name__}: {exc}"
        raw_path = run_dir / "raw_llm" / policy.slug / f"{idx:04d}.txt"
        write_text(raw_path, raw)
        call_row["raw_path"] = str(raw_path)
        call_rows.append(call_row)

        row, program = task_adapter.evaluate_code(
            raw,
            method_slug=policy.slug,
            method_name=policy.display_name,
            graphs=graphs,
            index=idx,
            source=policy.source,
        )
        row["prompt_path"] = str(prompt_path)
        row["raw_path"] = str(raw_path)
        if program is not None:
            code_path = run_dir / "candidates" / policy.slug / f"{idx:04d}_{program.candidate_id}.py"
            write_text(code_path, program.code)
            row["code_path"] = str(code_path)
        rows.append(row)
        ranked = task_adapter.rank_records(policy.records + [row])
        latest = ranked[-1]
        policy.records = ranked[:-1]
        policy.update(latest)
        rows[-1] = policy.records[-1]
    return rows, call_rows


def main() -> None:
    args = parse_args()
    task_adapter = get_task_adapter(args.task)
    run_date = args.run_date or datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = make_run_dir(task_adapter.slug.upper(), safe_token(args.run_name), run_date)
    run_dir.mkdir(parents=True, exist_ok=True)

    graphs = task_adapter.make_proxy_graphs()
    policies = all_policies(task_adapter)
    if args.methods:
        wanted = {item.strip() for item in args.methods.split(",") if item.strip()}
        policies = [policy for policy in policies if policy.slug in wanted]
        missing = sorted(wanted - {policy.slug for policy in policies})
        if missing:
            raise SystemExit(f"Unknown method slug(s): {', '.join(missing)}")
    write_csv(run_dir / "graph_manifest.csv", task_adapter.manifest_rows(graphs))
    write_audit(run_dir / "baseline_reasonableness_audit_cn.md", policies, task_adapter)

    provider = OpenAICompatibleLLMProvider.from_env() if args.use_llm else None
    all_rows: list[dict[str, Any]] = []
    all_call_rows: list[dict[str, Any]] = []
    for policy in policies:
        rows, call_rows = run_policy_smoke(policy, task_adapter, graphs, run_dir, max(1, args.budget), provider)
        all_rows.extend(rows)
        all_call_rows.extend(call_rows)

    ranked_all = task_adapter.rank_records(all_rows)
    write_csv(run_dir / "smoke_records.csv", rows_without_code(ranked_all))
    write_csv(run_dir / "llm_call_summary.csv", all_call_rows)
    manifest = {
        "run_dir": str(run_dir),
        "task": task_adapter.slug,
        "task_name": task_adapter.task_name,
        "candidate_interface": task_adapter.candidate_interface,
        "budget_per_method": max(1, args.budget),
        "proxy_graph_count": len(graphs),
        "methods": [policy.display_name for policy in policies],
        "method_slugs": [policy.slug for policy in policies],
        "llm_mode": "real" if args.use_llm else "deterministic_fallback",
        "api_key_saved": False,
        "outputs": [
            "graph_manifest.csv",
            "smoke_records.csv",
            "llm_call_summary.csv",
            "baseline_reasonableness_audit_cn.md",
        ],
    }
    write_text(run_dir / "run_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
