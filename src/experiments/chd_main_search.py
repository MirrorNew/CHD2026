# -*- coding: utf-8 -*-
"""运行 CHD 阶段搜索，并可选执行跨图完整验证。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model.stage1_stage3_search import default_config, read_benchmark_context, run_stage_search, write_prepare_manifest
from experiments.full_validation import FullValidationConfig, evaluate_full_validation, load_stage3_final_programs
from model.config import SearchWeights
from model.reference_check import write_reference_check
from model.llm import OpenAICompatibleLLMProvider


def parse_csv_list(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def parse_rank_weights(text: str, option_name: str) -> SearchWeights | None:
    if not text:
        return None
    try:
        values = [float(item.strip()) for item in text.split(",")]
    except ValueError as exc:
        raise SystemExit(f"{option_name} must contain four comma-separated numbers") from exc
    if len(values) != 4:
        raise SystemExit(f"{option_name} must contain exactly four values: relative_credit,fragmentation,time,absolute_quality")
    if any(value < 0 for value in values):
        raise SystemExit(f"{option_name} values must be non-negative")
    if abs(sum(values) - 1.0) > 1e-9:
        raise SystemExit(f"{option_name} values must sum to 1.0; got {sum(values):.12g}")
    return SearchWeights(
        relative_credit=values[0],
        fragmentation=values[1],
        time=values[2],
        absolute_quality=values[3],
    )


def write_input_parameters(config, args: argparse.Namespace, run_date: str) -> Path:
    config.run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "argv": sys.argv,
        "cli_args": vars(args),
        "resolved": {
            "run_dir": str(config.run_dir),
            "task": config.task,
            "run_date": run_date,
            "delta_credit_mode": config.delta_credit_mode,
            "proxy_datasets": config.proxy_datasets,
            "full_datasets": config.full_datasets,
            "stage1_budget": config.stage1_budget,
            "stage2_budget": config.stage2_budget,
            "stage3_budget": config.stage3_budget,
            "candidates_per_llm_call": config.candidates_per_llm_call,
            "stage3_parent_limit": config.stage3_parent_limit,
            "candidate_timeout_s": config.candidate_timeout_s,
            "llm_workers": config.llm_workers,
            "parent_priority_mode": config.parent_priority_mode,
            "final_selection_mode": config.final_selection_mode,
            "stage1_rank_weights": config.stage1_weights.to_dict(),
            "stage3_rank_weights": config.stage3_weights.to_dict(),
            "elite_candidate_paths": config.elite_candidate_paths or [],
            "online_graph": config.online_graph,
            "online_live_edge_worlds": config.online_live_edge_worlds,
            "online_rr_sets": config.online_rr_sets,
            "execute": bool(args.execute),
            "run_full_validation": bool(args.run_full_validation),
            "preset": args.preset,
            "proxy_profile": args.proxy_profile,
            "full_validation_role": "evaluation_only_no_reselection",
            "stage3_final_selection_source": "stage3_final_selection.json",
        },
        "llm_env": {
            "api_key_source": "HAST_LLM_API_KEY or OPENAI_API_KEY environment variable",
            "model_env": "HAST_LLM_MODEL",
            "reasoning_effort_env": "HAST_LLM_REASONING_EFFORT",
            "temperature_env": "HAST_LLM_TEMPERATURE",
            "base_url_env": "HAST_LLM_BASE_URL",
            "timeout_env": "HAST_LLM_TIMEOUT_S",
            "api_key_saved": False,
        },
    }
    path = config.run_dir / "input_parameters.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["nd", "im"], default="nd", help="Task mode: network dismantling or influence maximization.")
    parser.add_argument("--run-name", default="main", help="Specific task name used in src/runs/YYYYMMDD-HHMMSS-ND-<mode-run-name>.")
    parser.add_argument("--run-date", default="", help="Override run timestamp. Accepts YYYYMMDD-HHMMSS, YYYYMMDDHHMMSS, or legacy YYYYMMDD.")
    parser.add_argument("--preset", choices=["default", "target-family"], default="default")
    parser.add_argument(
        "--proxy-profile",
        choices=["default", "xxx-like-powerlaw500"],
        default="default",
        help="Named online proxy profile. xxx-like-powerlaw500 keeps search comparable with other xxx-like runs.",
    )
    parser.add_argument("--proxy-datasets", default="", help="Comma-separated proxy datasets for Stage 1/3 search.")
    parser.add_argument("--full-datasets", default="", help="Comma-separated datasets for optional full validation.")
    parser.add_argument("--stage1-budget", type=int, default=None)
    parser.add_argument("--stage2-budget", type=int, default=None)
    parser.add_argument("--stage3-budget", type=int, default=None)
    parser.add_argument("--candidate-timeout-s", type=float, default=None)
    parser.add_argument(
        "--delta-credit-mode",
        choices=["parent", "root"],
        default=None,
        help="Use root-relative credit for the main run; parent-relative is reserved for ablation runs.",
    )
    parser.add_argument("--llm-workers", type=int, default=None, help="Concurrent LLM requests.")
    parser.add_argument("--online-graph", default="", help="IM online proxy graph path, relative to project root or absolute.")
    parser.add_argument("--online-live-edge-worlds", type=int, default=128, help="Fixed IC live-edge worlds for IM online scoring.")
    parser.add_argument("--online-rr-sets", type=int, default=2048, help="Fixed RR sets for IM online scoring.")
    parser.add_argument(
        "--stage1-rank-weights",
        default="",
        help="Comma-separated Stage 1 weights: relative_credit,fragmentation,time,absolute_quality. Values must sum to 1.0.",
    )
    parser.add_argument(
        "--stage3-rank-weights",
        default="",
        help="Comma-separated Stage 3 weights: relative_credit,fragmentation,time,absolute_quality. Values must sum to 1.0.",
    )
    parser.add_argument(
        "--parent-priority-mode",
        choices=["legacy", "hast_stage1"],
        default="hast_stage1",
        help="Parent expansion priority strategy for Stage 1/3 tree search.",
    )
    parser.add_argument(
        "--final-selection-mode",
        choices=["legacy", "target_guard"],
        default="target_guard",
        help="How Stage 3 fixes HAST-Final-Q/S from the proxy Pareto frontier.",
    )
    parser.add_argument(
        "--elite-candidate-paths",
        default="",
        help="Comma-separated existing candidate .py files to seed Stage 3 and include in final archive selection.",
    )
    parser.add_argument("--allow-existing-run-dir", action="store_true", help="Allow writing into an existing run directory.")
    parser.add_argument("--execute", action="store_true", help="Actually call the LLM provider and run Stage 1/2/3.")
    parser.add_argument("--dry-run", action="store_true", help="Alias for the default prepare-only behavior.")
    parser.add_argument(
        "--run-full-validation",
        dest="run_full_validation",
        action="store_true",
        help="After Stage 3, evaluate the fixed HAST-Final-Q/S on the full benchmark.",
    )
    args = parser.parse_args()
    stage1_weights = parse_rank_weights(args.stage1_rank_weights, "--stage1-rank-weights")
    stage3_weights = parse_rank_weights(args.stage3_rank_weights, "--stage3-rank-weights")

    delta_credit_mode = args.delta_credit_mode or "root"
    run_date = args.run_date or datetime.now().strftime("%Y%m%d-%H%M%S")
    config = default_config(
        args.run_name,
        delta_credit_mode=delta_credit_mode,
        run_date=run_date,
        task=args.task,
        online_graph=args.online_graph or None,
        online_live_edge_worlds=args.online_live_edge_worlds,
        online_rr_sets=args.online_rr_sets,
    )
    if args.preset == "target-family":
        config = config.__class__(
            **{
                **config.__dict__,
                "stage1_budget": 300,
                "stage2_budget": 10,
                "stage3_budget": 200,
                "proxy_datasets": ["Powerlaw_500"],
                "parent_priority_mode": args.parent_priority_mode,
                "final_selection_mode": args.final_selection_mode,
            }
        )
    if args.proxy_profile == "xxx-like-powerlaw500":
        config = config.__class__(**{**config.__dict__, "proxy_datasets": ["Powerlaw_500"]})
    if args.proxy_datasets:
        config = config.__class__(**{**config.__dict__, "proxy_datasets": parse_csv_list(args.proxy_datasets)})
    if args.full_datasets:
        config = config.__class__(**{**config.__dict__, "full_datasets": parse_csv_list(args.full_datasets)})
    if args.parent_priority_mode != config.parent_priority_mode:
        config = config.__class__(**{**config.__dict__, "parent_priority_mode": args.parent_priority_mode})
    if args.final_selection_mode != config.final_selection_mode:
        config = config.__class__(**{**config.__dict__, "final_selection_mode": args.final_selection_mode})
    if args.elite_candidate_paths:
        config = config.__class__(**{**config.__dict__, "elite_candidate_paths": parse_csv_list(args.elite_candidate_paths)})
    if stage1_weights is not None or stage3_weights is not None:
        config = config.__class__(
            **{
                **config.__dict__,
                "stage1_weights": stage1_weights if stage1_weights is not None else config.stage1_weights,
                "stage3_weights": stage3_weights if stage3_weights is not None else config.stage3_weights,
            }
        )
    if (
        args.stage1_budget is not None
        or args.stage2_budget is not None
        or args.stage3_budget is not None
        or args.candidate_timeout_s is not None
        or args.llm_workers is not None
    ):
        config = config.__class__(
            run_dir=config.run_dir,
            proxy_datasets=config.proxy_datasets,
            full_datasets=config.full_datasets,
            stage1_budget=args.stage1_budget if args.stage1_budget is not None else config.stage1_budget,
            stage2_budget=args.stage2_budget if args.stage2_budget is not None else config.stage2_budget,
            stage3_budget=args.stage3_budget if args.stage3_budget is not None else config.stage3_budget,
            candidates_per_llm_call=config.candidates_per_llm_call,
            stage3_parent_limit=config.stage3_parent_limit,
            candidate_timeout_s=args.candidate_timeout_s if args.candidate_timeout_s is not None else config.candidate_timeout_s,
            delta_credit_mode=config.delta_credit_mode,
            llm_workers=args.llm_workers if args.llm_workers is not None else config.llm_workers,
            parent_priority_mode=config.parent_priority_mode,
            final_selection_mode=config.final_selection_mode,
            stage1_weights=config.stage1_weights,
            stage3_weights=config.stage3_weights,
            elite_candidate_paths=config.elite_candidate_paths,
            task=config.task,
            online_graph=config.online_graph,
            online_live_edge_worlds=config.online_live_edge_worlds,
            online_rr_sets=config.online_rr_sets,
        )

    context = read_benchmark_context() if config.task == "nd" else {"root": "IM online proxy"}
    if args.dry_run and args.execute:
        raise SystemExit("Choose either --dry-run or --execute, not both.")
    if config.run_dir.exists() and any(config.run_dir.iterdir()) and not args.allow_existing_run_dir:
        raise SystemExit(
            f"Run directory already exists and is not empty: {config.run_dir}. "
            "Use a new --run-name/--run-date or pass --allow-existing-run-dir intentionally."
        )
    input_parameters_path = write_input_parameters(config, args, run_date)

    if not args.execute:
        manifest = write_prepare_manifest(config, context)
        manifest["input_parameters_path"] = str(input_parameters_path)
        manifest["preset"] = args.preset
        manifest["proxy_profile"] = args.proxy_profile
        manifest["can_run_full_validation_with"] = (
            "python src/scripts/run_im_12graph_benchmark.py --include native,ahd,chd"
            if config.task == "im"
            else "python src/scripts/run_full_validation.py --stage3-final-dir <run_dir>/final"
        )
        print(json.dumps({"prepared": True, **manifest}, ensure_ascii=False, indent=2))
        return

    provider = OpenAICompatibleLLMProvider.from_env()
    result = run_stage_search(config, provider)
    result["input_parameters_path"] = str(input_parameters_path)
    if args.run_full_validation and config.task == "im":
        raise SystemExit("--run-full-validation is only implemented for --task nd; use run_im_12graph_benchmark.py for IM.")
    if args.run_full_validation:
        programs, method_names = load_stage3_final_programs(config.run_dir / "final", family="HAST-final")
        validation_config = FullValidationConfig(
            output_dir=config.run_dir / "full_validation",
            datasets=config.full_datasets,
            source="chd_stage3_final_then_full_validation",
            method_names=method_names,
            candidate_timeout_s=config.candidate_timeout_s,
        )
        result["full_validation"] = evaluate_full_validation(validation_config, programs)
        result["legacy_reference_check"] = write_reference_check(config.run_dir / "full_validation")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

