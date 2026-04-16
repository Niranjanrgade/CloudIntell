"""Main evaluation orchestrator — modular subcommand design.

Three independent stages that can be run separately:
  generate  — run LLM systems, save raw outputs       (costs API quota)
  score     — compute metrics on existing outputs      (judge costs API; meteor/bert are free)
  analyze   — aggregate results, generate charts/tables (free, no API)

Fine-grained filters (--scenario, --model, --version, --run) let you
evaluate a single slice without burning your full API budget.

Usage:
    # Generate one scenario, one version, one run
    python -m evaluation.run_evaluation generate --scenario three_tier_web --version baseline --runs 1

    # Score with free metrics only
    python -m evaluation.run_evaluation score --metrics meteor bert

    # Add LLM judge later
    python -m evaluation.run_evaluation score --metrics judge

    # Generate thesis charts/tables from whatever metrics exist
    python -m evaluation.run_evaluation analyze

    # Full pipeline (backward compatible)
    python -m evaluation.run_evaluation generate --experiment all
    python -m evaluation.run_evaluation score
    python -m evaluation.run_evaluation analyze

    # Dry-run: inspect the evaluation matrix
    python -m evaluation.run_evaluation dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # export .env vars (e.g. OPENAI_API_KEY) into os.environ

from evaluation.analysis.aggregator import (
    aggregate_by_config,
    load_all_metrics,
    split_experiments,
)
from evaluation.analysis.charts import generate_all_charts
from evaluation.analysis.latex_tables import generate_all_tables
from evaluation.config import (
    ALL_METRICS,
    EVAL_GPT_MODEL,
    METRIC_BERT,
    METRIC_JUDGE,
    METRIC_METEOR,
    VERSION_AGENTIC,
    VERSION_BASELINE,
    VERSION_FRAMEWORK,
    EvalConfig,
    ExperimentConfig,
    RunFilter,
    get_model_experiment,
    get_version_experiment,
    result_path,
)
from evaluation.metrics.bert_score import compute_bert_score
from evaluation.metrics.llm_judge import evaluate_with_judge
from evaluation.metrics.meteor_score import compute_meteor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _load_scenarios(
    scenarios_dir: str,
    filter_ids: list[str] | None = None,
) -> list[dict]:
    """Load scenario JSON files, optionally filtered by ID."""
    scenario_files = sorted(Path(scenarios_dir).glob("scenario_*.json"))
    scenarios = []
    for f in scenario_files:
        data = json.loads(f.read_text())
        if data.get("reference_architecture", {}).get("full_text", "").startswith("REPLACE"):
            logger.warning(
                "Scenario %s has placeholder reference text — skipping. "
                "Please replace with actual reference architecture.",
                data.get("id", f.stem),
            )
            continue
        if filter_ids and data.get("id") not in filter_ids:
            continue
        scenarios.append(data)
    if not scenarios:
        logger.error("No valid scenarios found in %s", scenarios_dir)
        sys.exit(1)
    logger.info("Loaded %d scenarios from %s", len(scenarios), scenarios_dir)
    return scenarios


def _run_version(
    problem: str,
    version: str,
    model_name: str,
    provider: str,
    min_iter: int,
    max_iter: int,
) -> tuple[str, float]:
    """Execute the appropriate runner for a version and return (output, elapsed)."""
    if version == VERSION_BASELINE:
        from evaluation.runners.baseline_runner import run_baseline

        result = run_baseline(problem, model_name, provider)
        return result.output, result.elapsed_seconds

    if version == VERSION_AGENTIC:
        from evaluation.runners.agentic_runner import run_agentic

        result = run_agentic(problem, model_name, provider)
        return result.output, result.elapsed_seconds

    if version == VERSION_FRAMEWORK:
        from evaluation.runners.framework_runner import run_framework

        result = run_framework(problem, model_name, provider, min_iter, max_iter)
        return result.output, result.elapsed_seconds

    raise ValueError(f"Unknown version: {version}")


# ── Metric helpers ──────────────────────────────────────────────────────

_METEOR_KEYS = {"meteor"}
_BERT_KEYS = {"bert_score_precision", "bert_score_recall", "bert_score_f1"}
_JUDGE_KEYS = {
    "judge_completeness",
    "judge_technical_accuracy",
    "judge_security",
    "judge_scalability",
    "judge_best_practices",
    "judge_specificity",
    "judge_total",
    "judge_reasoning",
}


def _compute_selected_metrics(
    generated: str,
    reference: str,
    problem: str,
    judge_model: str,
    metrics: list[str],
) -> dict:
    """Compute only the requested metrics."""
    result: dict = {}

    if METRIC_METEOR in metrics:
        result["meteor"] = compute_meteor(generated, reference)

    if METRIC_BERT in metrics:
        bs = compute_bert_score(generated, reference)
        result["bert_score_precision"] = bs.precision
        result["bert_score_recall"] = bs.recall
        result["bert_score_f1"] = bs.f1

    if METRIC_JUDGE in metrics:
        judge = evaluate_with_judge(generated, reference, problem, judge_model)
        result["judge_completeness"] = judge.completeness
        result["judge_technical_accuracy"] = judge.technical_accuracy
        result["judge_security"] = judge.security
        result["judge_scalability"] = judge.scalability
        result["judge_best_practices"] = judge.best_practices
        result["judge_specificity"] = judge.specificity
        result["judge_total"] = judge.total_score
        result["judge_reasoning"] = judge.reasoning

    return result


def _metric_keys_for(metrics: list[str]) -> set[str]:
    """Return the set of JSON keys produced by the given metric names."""
    keys: set[str] = set()
    if METRIC_METEOR in metrics:
        keys |= _METEOR_KEYS
    if METRIC_BERT in metrics:
        keys |= _BERT_KEYS
    if METRIC_JUDGE in metrics:
        keys |= _JUDGE_KEYS
    return keys


# ── Discovery ───────────────────────────────────────────────────────────
_RUN_FILE_RE = re.compile(r"^run_(\d+)\.json$")


def _discover_outputs(
    output_dir: str,
    run_filter: RunFilter,
) -> list[tuple[str, str, str, int, Path]]:
    """Scan the results directory for existing run output files.

    Returns list of ``(scenario_id, model, version, run_number, path)`` tuples
    matching the filter.
    """
    base = Path(output_dir)
    if not base.exists():
        return []

    results: list[tuple[str, str, str, int, Path]] = []
    # Layout: <output_dir>/<scenario_id>/<model>/<version>/run_N.json
    for scenario_dir in sorted(base.iterdir()):
        if not scenario_dir.is_dir():
            continue
        scenario_id = scenario_dir.name
        for model_dir in sorted(scenario_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            model = model_dir.name
            for version_dir in sorted(model_dir.iterdir()):
                if not version_dir.is_dir():
                    continue
                version = version_dir.name
                for f in sorted(version_dir.iterdir()):
                    m = _RUN_FILE_RE.match(f.name)
                    if not m:
                        continue
                    run_num = int(m.group(1))
                    if run_filter.matches(scenario_id, model, version, run_num):
                        results.append((scenario_id, model, version, run_num, f))
    return results


# ═══════════════════════════════════════════════════════════════════════
#  STAGE 1: generate
# ═══════════════════════════════════════════════════════════════════════

def cmd_generate(args: argparse.Namespace) -> None:
    """Generate raw architecture outputs (no metrics)."""
    base = _eval_config_from_args(args)
    run_filter = _run_filter_from_args(args)

    scenarios = _load_scenarios(base.scenarios_dir, run_filter.scenarios)

    experiments: list[ExperimentConfig] = []

    # If user explicitly specifies both --model and --version, create an
    # ad-hoc experiment so arbitrary model×version combinations work
    # without being constrained to the predefined experiment matrices.
    if run_filter.models and run_filter.versions:
        experiments.append(ExperimentConfig(
            name="model_comparison",
            models=run_filter.models,
            versions=run_filter.versions,
            base=base,
        ))
    else:
        experiment_filter = getattr(args, "experiment", "all")
        if experiment_filter in ("all", "version"):
            experiments.append(get_version_experiment(base))
        if experiment_filter in ("all", "model"):
            experiments.append(get_model_experiment(base))

    start_time = time.perf_counter()
    total_generated = 0
    total_skipped = 0

    for experiment in experiments:
        for scenario in scenarios:
            scenario_id = scenario["id"]
            problem = scenario["user_problem"]

            for model in experiment.models:
                for version in experiment.versions:
                    for run in range(1, base.runs_per_config + 1):
                        if not run_filter.matches(scenario_id, model, version, run):
                            continue

                        output_file = result_path(
                            base.output_dir, scenario_id, model, version, run,
                        )

                        if output_file.exists() and not args.force:
                            total_skipped += 1
                            logger.debug(
                                "Cached: %s/%s/%s/run_%d",
                                scenario_id, model, version, run,
                            )
                            continue

                        logger.info(
                            "Generating: scenario=%s model=%s version=%s run=%d",
                            scenario_id, model, version, run,
                        )

                        try:
                            output, elapsed = _run_version(
                                problem, version, model, base.provider,
                                base.min_iterations, base.max_iterations,
                            )
                        except Exception as e:
                            logger.error("Runner failed: %s", e)
                            output = f"ERROR: {e}"
                            elapsed = 0.0

                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        output_file.write_text(json.dumps({
                            "scenario_id": scenario_id,
                            "model": model,
                            "version": version,
                            "run": run,
                            "output": output,
                            "elapsed_seconds": elapsed,
                        }, indent=2))
                        total_generated += 1

    elapsed_total = time.perf_counter() - start_time
    logger.info(
        "Generate complete: %d generated, %d cached/skipped (%.1fs)",
        total_generated, total_skipped, elapsed_total,
    )


# ═══════════════════════════════════════════════════════════════════════
#  STAGE 2: score
# ═══════════════════════════════════════════════════════════════════════

def cmd_score(args: argparse.Namespace) -> None:
    """Compute metrics on existing generated outputs (incremental)."""
    base = _eval_config_from_args(args)
    run_filter = _run_filter_from_args(args)
    metrics = args.metrics if args.metrics else list(ALL_METRICS)
    force = args.force

    scenarios = _load_scenarios(base.scenarios_dir, run_filter.scenarios)
    scenario_map = {s["id"]: s for s in scenarios}

    outputs = _discover_outputs(base.output_dir, run_filter)
    if not outputs:
        logger.warning("No generated outputs found in %s matching filters.", base.output_dir)
        return

    needed_keys = _metric_keys_for(metrics)
    total_scored = 0
    total_skipped = 0

    start_time = time.perf_counter()

    for scenario_id, model, version, run_num, output_path in outputs:
        scenario = scenario_map.get(scenario_id)
        if not scenario:
            logger.debug("Scenario %s not loaded — skipping.", scenario_id)
            continue

        reference = scenario["reference_architecture"]["full_text"]
        problem = scenario["user_problem"]

        # Load generated output
        output_data = json.loads(output_path.read_text())
        generated = output_data.get("output", "")
        elapsed = output_data.get("elapsed_seconds", 0.0)

        # Load existing metrics (if any) for incremental update
        metrics_file = result_path(
            base.output_dir, scenario_id, model, version, run_num, "_metrics",
        )
        existing_metrics: dict = {}
        if metrics_file.exists():
            existing_metrics = json.loads(metrics_file.read_text())

        # Determine which metrics still need computing
        if force:
            metrics_to_compute = list(metrics)
        else:
            existing_keys = set(existing_metrics.keys())
            missing_keys = needed_keys - existing_keys
            if not missing_keys:
                total_skipped += 1
                logger.debug(
                    "All requested metrics cached: %s/%s/%s/run_%d",
                    scenario_id, model, version, run_num,
                )
                continue
            # Figure out which metric groups are missing
            metrics_to_compute = []
            if METRIC_METEOR in metrics and not (_METEOR_KEYS <= existing_keys):
                metrics_to_compute.append(METRIC_METEOR)
            if METRIC_BERT in metrics and not (_BERT_KEYS <= existing_keys):
                metrics_to_compute.append(METRIC_BERT)
            if METRIC_JUDGE in metrics and not (_JUDGE_KEYS <= existing_keys):
                metrics_to_compute.append(METRIC_JUDGE)

        if not metrics_to_compute:
            total_skipped += 1
            continue

        logger.info(
            "Scoring [%s]: scenario=%s model=%s version=%s run=%d",
            ",".join(metrics_to_compute), scenario_id, model, version, run_num,
        )

        try:
            new_metrics = _compute_selected_metrics(
                generated, reference, problem, base.judge_model, metrics_to_compute,
            )
        except Exception as e:
            logger.error("Metrics computation failed: %s", e)
            new_metrics = {"error": str(e)}

        # Merge: existing metrics + new metrics + elapsed
        merged = {**existing_metrics, **new_metrics, "elapsed_seconds": elapsed}
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        metrics_file.write_text(json.dumps(merged, indent=2))
        total_scored += 1

    elapsed_total = time.perf_counter() - start_time
    logger.info(
        "Score complete: %d scored, %d cached/skipped (%.1fs)",
        total_scored, total_skipped, elapsed_total,
    )


# ═══════════════════════════════════════════════════════════════════════
#  STAGE 3: analyze
# ═══════════════════════════════════════════════════════════════════════

def cmd_analyze(args: argparse.Namespace) -> None:
    """Aggregate metrics and generate charts/tables (no API calls)."""
    base = _eval_config_from_args(args)

    logger.info("Aggregating results from %s ...", base.output_dir)
    raw_df = load_all_metrics(base.output_dir)

    if raw_df.empty:
        logger.warning("No metrics data found — nothing to analyze.")
        return

    agg_df = aggregate_by_config(raw_df)
    version_df, model_df = split_experiments(agg_df, EVAL_GPT_MODEL)

    tables_dir = str(Path(base.output_dir) / "tables")
    generate_all_tables(version_df, model_df, tables_dir)

    charts_dir = str(Path(base.output_dir) / "charts")
    generate_all_charts(version_df, model_df, raw_df, charts_dir, EVAL_GPT_MODEL, agg_df=agg_df)

    logger.info("Analysis complete — tables in %s, charts in %s", tables_dir, charts_dir)


# ═══════════════════════════════════════════════════════════════════════
#  dry-run
# ═══════════════════════════════════════════════════════════════════════

def cmd_dry_run(args: argparse.Namespace) -> None:
    """Print the evaluation matrix without executing."""
    base = _eval_config_from_args(args)
    scenarios = _load_scenarios(base.scenarios_dir)

    exp1 = get_version_experiment(base)
    exp2 = get_model_experiment(base)

    configs: set[tuple[str, str]] = set()
    for exp in [exp1, exp2]:
        for model in exp.models:
            for version in exp.versions:
                configs.add((model, version))

    total_runs = len(scenarios) * len(configs) * base.runs_per_config

    print("\n=== Dry Run: Evaluation Matrix ===\n")
    print(f"Scenarios:       {len(scenarios)}")
    print(f"Configurations:  {len(configs)}")
    print(f"Runs per config: {base.runs_per_config}")
    print(f"Total runs:      {total_runs}")
    print(f"Provider:        {base.provider}")
    print(f"Judge model:     {base.judge_model}")
    print()

    print("Experiment 1 — Version Comparison:")
    for v in exp1.versions:
        for m in exp1.models:
            print(f"  {v:12s} × {m}")

    print("\nExperiment 2 — Model Comparison:")
    for m in exp2.models:
        for v in exp2.versions:
            print(f"  {m:30s} × {v}")

    print("\nScenarios:")
    for s in scenarios:
        ref_len = len(s.get("reference_architecture", {}).get("full_text", ""))
        print(f"  {s['id']:30s} — {s['name']} (ref: {ref_len} chars)")

    cached = 0
    for s in scenarios:
        for model, version in configs:
            for run in range(1, base.runs_per_config + 1):
                if result_path(base.output_dir, s["id"], model, version, run).exists():
                    cached += 1

    if cached:
        print(f"\nCached results:  {cached}/{total_runs} (will be skipped)")
        print(f"Remaining runs:  {total_runs - cached}")


# ── Backward-compatible full pipeline ───────────────────────────────────

def run_full_evaluation(
    base_config: EvalConfig,
    experiment_filter: str = "all",
) -> None:
    """Run the full evaluation pipeline (generate + score all + analyze).

    Kept for backward compatibility.
    """
    scenarios = _load_scenarios(base_config.scenarios_dir)
    start_time = time.perf_counter()

    experiments: list[ExperimentConfig] = []
    if experiment_filter in ("all", "version"):
        experiments.append(get_version_experiment(base_config))
    if experiment_filter in ("all", "model"):
        experiments.append(get_model_experiment(base_config))

    no_filter = RunFilter()

    for experiment in experiments:
        for scenario in scenarios:
            scenario_id = scenario["id"]
            problem = scenario["user_problem"]
            reference = scenario["reference_architecture"]["full_text"]

            for model in experiment.models:
                for version in experiment.versions:
                    for run in range(1, base_config.runs_per_config + 1):
                        output_file = result_path(
                            base_config.output_dir, scenario_id, model, version, run,
                        )
                        metrics_file = result_path(
                            base_config.output_dir, scenario_id, model, version, run, "_metrics",
                        )

                        if output_file.exists() and metrics_file.exists():
                            continue

                        logger.info(
                            "Running: scenario=%s model=%s version=%s run=%d",
                            scenario_id, model, version, run,
                        )

                        try:
                            output, elapsed = _run_version(
                                problem, version, model, base_config.provider,
                                base_config.min_iterations, base_config.max_iterations,
                            )
                        except Exception as e:
                            logger.error("Runner failed: %s", e)
                            output = f"ERROR: {e}"
                            elapsed = 0.0

                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        output_file.write_text(json.dumps({
                            "scenario_id": scenario_id,
                            "model": model,
                            "version": version,
                            "run": run,
                            "output": output,
                            "elapsed_seconds": elapsed,
                        }, indent=2))

                        try:
                            metrics = _compute_selected_metrics(
                                output, reference, problem,
                                base_config.judge_model, list(ALL_METRICS),
                            )
                            metrics["elapsed_seconds"] = elapsed
                        except Exception as e:
                            logger.error("Metrics computation failed: %s", e)
                            metrics = {"error": str(e), "elapsed_seconds": elapsed}

                        metrics_file.write_text(json.dumps(metrics, indent=2))

    # Analysis
    raw_df = load_all_metrics(base_config.output_dir)
    if raw_df.empty:
        logger.warning("No metrics data found — skipping analysis.")
        return

    agg_df = aggregate_by_config(raw_df)
    version_df, model_df = split_experiments(agg_df, EVAL_GPT_MODEL)

    tables_dir = str(Path(base_config.output_dir) / "tables")
    generate_all_tables(version_df, model_df, tables_dir)

    charts_dir = str(Path(base_config.output_dir) / "charts")
    generate_all_charts(version_df, model_df, raw_df, charts_dir, EVAL_GPT_MODEL, agg_df=agg_df)

    elapsed = time.perf_counter() - start_time
    logger.info("Full evaluation complete in %.1f seconds", elapsed)


# ── CLI arg helpers ─────────────────────────────────────────────────────

def _eval_config_from_args(args: argparse.Namespace) -> EvalConfig:
    return EvalConfig(
        scenarios_dir=args.scenarios_dir,
        output_dir=args.output_dir,
        runs_per_config=getattr(args, "runs", 3),
        provider=args.provider,
        judge_model=getattr(args, "judge_model", "gpt-4o"),
        min_iterations=getattr(args, "min_iterations", 1),
        max_iterations=getattr(args, "max_iterations", 3),
    )


def _run_filter_from_args(args: argparse.Namespace) -> RunFilter:
    scenarios = None
    if hasattr(args, "scenario") and args.scenario:
        scenarios = [s.strip() for s in args.scenario.split(",")]

    models = None
    if hasattr(args, "model") and args.model:
        models = [m.strip() for m in args.model.split(",")]

    versions = None
    if hasattr(args, "version") and args.version:
        versions = [v.strip() for v in args.version.split(",")]

    runs = None
    if hasattr(args, "run") and args.run:
        runs = [int(r.strip()) for r in args.run.split(",")]

    return RunFilter(scenarios=scenarios, models=models, versions=versions, runs=runs)


def _add_shared_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments shared across all subcommands."""
    parser.add_argument(
        "--scenarios-dir", default="evaluation/scenarios",
        help="Directory containing scenario JSON files",
    )
    parser.add_argument(
        "--output-dir", default="evaluation/results",
        help="Directory to write results, tables, and charts",
    )
    parser.add_argument(
        "--provider", default="aws", choices=["aws", "azure"],
        help="Cloud provider (default: aws)",
    )


def _add_filter_args(parser: argparse.ArgumentParser) -> None:
    """Add fine-grained filter arguments."""
    parser.add_argument(
        "--scenario",
        help="Filter to specific scenario IDs (comma-separated, e.g. three_tier_web,serverless_data_lake)",
    )
    parser.add_argument(
        "--model",
        help="Filter to specific models (comma-separated, e.g. gpt-5.4)",
    )
    parser.add_argument(
        "--version",
        help="Filter to specific versions (comma-separated, e.g. baseline,framework)",
    )
    parser.add_argument(
        "--run",
        help="Filter to specific run numbers (comma-separated, e.g. 1,2)",
    )


# ── Main CLI ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cloudy-Intell Academic Evaluation Framework",
    )
    subparsers = parser.add_subparsers(dest="command", help="Stage to run")

    # ── generate ────────────────────────────────────────────────────────
    gen_parser = subparsers.add_parser(
        "generate",
        help="Run LLM systems and save raw architecture outputs (costs API quota)",
    )
    _add_shared_args(gen_parser)
    _add_filter_args(gen_parser)
    gen_parser.add_argument(
        "--experiment", choices=["all", "version", "model"], default="all",
        help="Which experiment matrix to generate (default: all)",
    )
    gen_parser.add_argument(
        "--runs", type=int, default=3,
        help="Number of runs per configuration (default: 3)",
    )
    gen_parser.add_argument(
        "--min-iterations", type=int, default=1,
        help="Min iterations for framework runner (default: 1)",
    )
    gen_parser.add_argument(
        "--max-iterations", type=int, default=3,
        help="Max iterations for framework runner (default: 3)",
    )
    gen_parser.add_argument(
        "--force", action="store_true",
        help="Regenerate even if output file already exists",
    )

    # ── score ───────────────────────────────────────────────────────────
    score_parser = subparsers.add_parser(
        "score",
        help="Compute metrics on existing outputs (judge costs API; meteor/bert are free)",
    )
    _add_shared_args(score_parser)
    _add_filter_args(score_parser)
    score_parser.add_argument(
        "--metrics", nargs="+",
        choices=[METRIC_METEOR, METRIC_BERT, METRIC_JUDGE, "all"],
        default=["all"],
        help="Which metrics to compute (default: all). 'meteor' and 'bert' are free; 'judge' costs API.",
    )
    score_parser.add_argument(
        "--judge-model", default="gpt-4o",
        help="Model to use for LLM judge (default: gpt-4o)",
    )
    score_parser.add_argument(
        "--force", action="store_true",
        help="Recompute selected metrics even if already cached",
    )
    score_parser.add_argument(
        "--runs", type=int, default=3,
        help="(unused — kept for config compat)",
    )

    # ── analyze ─────────────────────────────────────────────────────────
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Aggregate results, generate charts and LaTeX tables (free, no API)",
    )
    _add_shared_args(analyze_parser)

    # ── dry-run ─────────────────────────────────────────────────────────
    dry_parser = subparsers.add_parser(
        "dry-run",
        help="Print evaluation matrix without executing",
    )
    _add_shared_args(dry_parser)
    dry_parser.add_argument(
        "--runs", type=int, default=3,
        help="Number of runs per configuration (default: 3)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Normalize --metrics: expand "all" → individual metrics
    if hasattr(args, "metrics"):
        if "all" in args.metrics:
            args.metrics = list(ALL_METRICS)

    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "score":
        cmd_score(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "dry-run":
        cmd_dry_run(args)


if __name__ == "__main__":
    main()
