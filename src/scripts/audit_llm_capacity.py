# -*- coding: utf-8 -*-
"""Audit a run directory for LLM capacity / switch-model failures."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd


NEEDLES = [
    "模型已满",
    "换个模型",
    "模型繁忙",
    "模型忙",
    "model full",
    "at capacity",
    "model capacity",
    "capacity",
    "overloaded",
    "currently overloaded",
    "temporarily unavailable",
    "no available model",
    "model_not_available",
    "insufficient_quota",
    "rate limit",
    "429",
    "503",
    "504",
]


def ordered(text: str, left: str, right: str) -> bool:
    left_index = text.find(left)
    right_index = text.find(right)
    return left_index >= 0 and right_index >= 0 and left_index < right_index


def find_capacity_issue(text: str) -> str:
    low = text.lower()
    for needle in NEEDLES:
        if needle.lower() in low:
            return needle
    if ("模型" in text and "满" in text) or ("请" in text and "换" in text and "模型" in text):
        return "模型/换模型相关中文提示"
    if (
        ordered(low, "model", "full")
        or ordered(low, "full", "model")
        or ordered(low, "model", "capacity")
        or ordered(low, "capacity", "model")
    ):
        return "model/full/capacity related prompt"
    return ""


def audit_run(run_dir: Path) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    summary_path = run_dir / "ahd" / "llm_call_summary.csv"
    if summary_path.exists():
        for row in pd.read_csv(summary_path, encoding="utf-8-sig").to_dict("records"):
            raw_path = Path(str(row.get("raw_path", "")))
            text = raw_path.read_text(encoding="utf-8", errors="replace") if raw_path.exists() else ""
            hit = find_capacity_issue(f"{row.get('error', '')}\n{text}")
            rows.append(
                {
                    "source": "ahd",
                    "method": row.get("method", ""),
                    "stage": "",
                    "index": row.get("candidate_index", ""),
                    "ok": row.get("ok", ""),
                    "raw_path": str(raw_path),
                    "capacity_or_switch_model_issue": bool(hit),
                    "matched_text": hit,
                    "error": row.get("error", ""),
                }
            )
    for stage in ["stage1", "stage2", "stage3"]:
        raw_dir = run_dir / "raw_llm" / stage
        if not raw_dir.exists():
            continue
        for raw_path in sorted(raw_dir.glob("*.txt")):
            text = raw_path.read_text(encoding="utf-8", errors="replace")
            hit = find_capacity_issue(text)
            rows.append(
                {
                    "source": "chd",
                    "method": "IM-CHD",
                    "stage": stage,
                    "index": raw_path.stem,
                    "ok": not text.lstrip().startswith("# LLM request failed:"),
                    "raw_path": str(raw_path),
                    "capacity_or_switch_model_issue": bool(hit),
                    "matched_text": hit,
                    "error": text[:500] if text.lstrip().startswith("# LLM request failed:") else "",
                }
            )
    for log_name in ["stage1_candidate_log.csv", "stage3_candidate_log.csv", "online/ahd_online_records.csv"]:
        path = run_dir / log_name
        if not path.exists():
            continue
        df = pd.read_csv(path, encoding="utf-8-sig")
        for index, row in df.iterrows():
            hit = find_capacity_issue(str(row.get("error", "")))
            if hit:
                rows.append(
                    {
                        "source": "candidate_log",
                        "method": str(row.get("method", "IM-CHD")),
                        "stage": log_name,
                        "index": index + 1,
                        "ok": False,
                        "raw_path": str(path),
                        "capacity_or_switch_model_issue": True,
                        "matched_text": hit,
                        "error": str(row.get("error", ""))[:500],
                    }
                )

    out_csv = run_dir / "llm_capacity_audit.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "source",
            "method",
            "stage",
            "index",
            "ok",
            "raw_path",
            "capacity_or_switch_model_issue",
            "matched_text",
            "error",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "run_dir": str(run_dir),
        "llm_call_records_scanned": len(rows),
        "capacity_or_switch_model_issues": sum(1 for row in rows if row["capacity_or_switch_model_issue"]),
        "issue_rows": [row for row in rows if row["capacity_or_switch_model_issue"]],
        "api_key_saved": False,
    }
    (run_dir / "llm_capacity_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(audit_run(Path(args.run_dir)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
