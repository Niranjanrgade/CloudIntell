"""Main evaluation orchestrator.

Runs the two-experiment evaluation:
  Experiment 1: Version Comparison (Baseline vs Agentic vs Framework) — GPT only
  Experiment 2: Model Comparison (GPT vs Claude vs Gemini) — Framework only

Framework × GPT runs are shared across both experiments (idempotent caching).

Usage:
    python -m evaluation.run_evaluation --experiment all
    python -m evaluation.run_evaluation --experiment version
    python -m evaluation.run_evaluation --experiment model
    python -m evaluation.run_evaluation --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from evaluation.analysis.aggregator import (
    aggregate_by_config,
    load_all_metrics,
    split_experiments,
)
from evaluation.analysis.charts import generate_all_charts
from evaluation.analysis.latex_tables import generate_all_tables
from evaluation.config import (
    EVAL_GPT_MODEL,
    VERSION_AGENTIC,
    VERSION_BASELINE,
    VERSION_FRAMEWORK,
    EvalConfig,
    ExperimentConfig,
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


def _load_scenarios(scenarios_dir: str) -> list[dict]:
    """Load all scenario JSON files from the scenarios directory."""
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


def _compute_metrics(
    generated: str,
    reference: str,
    problem: str,
    judge_model: str,
) -> dict:
    """Compute all metrics for a single generated output."""
    # METEOR
    meteor = compute_meteor(generated, reference)

    # BERTScore
    bs = compute_bert_score(generated, reference)

    # LLM Judge
    judge = evaluate_with_judge(generated, reference, problem, judge_model)

    return {
        "meteor": meteor,
        "bert_score_precision": bs.precision,
        "bert_score_recall": bs.recall,
        "bert_score_f1": bs.f1,
        "judge_completeness": judge.completeness,
        "judge_technical_accuracy": judge.technical_accuracy,
        "judge_security": judge.security,
        "judge_scalability": judge.scalability,
        "judge_best_practices": judge.best_practices,
        "judge_specificity": judge.specificity,
        "judge_total": judge.total_score,
        "judge_reasoning": judge.reasoning,
    }


def _run_experiment(
    experiment: ExperimentConfig,
    scenarios: list[dict],
) -> None:
    """Execute all runs for a single experiment."""
    base = experiment.base
    total = (
        len(scenarios)
        * len(experiment.models)
        * len(experiment.versions)
        * base.runs_per_config
    )
    completed = 0
    skipped = 0

    logger.info(
        "Starting experiment '%s': %d scenarios × %d models × %d versions × %d runs = %d total",
        experiment.name,
        len(scenarios),
        len(experiment.models),
        len(experiment.versions),
        base.runs_per_config,
        total,
    )

    for scenario in scenarios:
        scenario_id = scenario["id"]
        problem = scenario["user_problem"]
        reference = scenario["reference_architecture"]["full_text"]

        for model in experiment.models:
            for version in experiment.versions:
                for run in range(1, base.runs_per_config + 1):
                    # Check if result already exists (idempotent resumption)
                    output_file = result_path(
                        base.output_dir, scenario_id, model, version, run
                    )
                    metrics_file = result_path(
                        base.output_dir, scenario_id, model, version, run, "_metrics"
                    )

                    if output_file.exists() and metrics_file.exists():
                        skipped += 1
                        completed += 1
                        logger.debug(
                            "Skipping existing: %s/%s/%s/run_%d",
                            scenario_id, model, version, run,
                        )
                        continue

                    logger.info(
                        "[%d/%d] %s | scenario=%s model=%s version=%s run=%d",
                        completed + 1, total, experiment.name,
                        scenario_id, model, version, run,
                    )

                    # Run the system version
                    try:
                        output, elapsed = _run_version(
                            problem, version, model, base.provider,
                            base.min_iterations, base.max_iterations,
                        )
                    except Exception as e:
                        logger.error("Runner failed: %s", e)
                        output = f"ERROR: {e}"
                        elapsed = 0.0

                    # Save raw output
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    output_file.write_text(json.dumps({
                        "scenario_id": scenario_id,
                        "model": model,
                        "version": version,
                        "run": run,
                        "output": output,
                        "elapsed_seconds": elapsed,
                    }, indent=2))

                    # Compute and save metrics
                    try:
                        metrics = _compute_metrics(
                            output, reference, problem, base.judge_model,
                        )
                        metrics["elapsed_seconds"] = elapsed
                    except Exception as e:
                        logger.error("Metrics computation failed: %s", e)
                        metrics = {"error": str(e), "elapsed_seconds": elapsed}

                    metrics_file.write_text(json.dumps(metrics, indent=2))

                    completed += 1

    logger.info(
        "Experiment '%s' complete: %d/%d runs (%d skipped/cached)",
        experiment.name, completed, total, skipped,
    )


def run_full_evaluation(
    base_config: EvalConfig,
    experiment_filter: str = "all",
) -> None:
    """Run the full evaluation pipeline.

    Args:
        base_config: Shared evaluation settings.
        experiment_filter: ``"all"``, ``"version"``, or ``"model"``.
    """
    scenarios = _load_scenarios(base_config.scenarios_dir)

    start_time = time.perf_counter()

    # Run experiments
    if experiment_filter in ("all", "version"):
        exp1 = get_version_experiment(base_config)
        _run_experiment(exp1, scenarios)

    if experiment_filter in ("all", "model"):
        exp2 = get_model_experiment(base_config)
        _run_experiment(exp2, scenarios)

    # Aggregate and generate outputs
    logger.info("Aggregating results...")
    raw_df = load_all_metrics(base_config.output_dir)

    if raw_df.empty:
        logger.warning("No metrics data found — skipping analysis.")
        return

    agg_df = aggregate_by_config(raw_df)
    version_df, model_df = split_experiments(agg_df, EVAL_GPT_MODEL)

    # Generate LaTeX tables
    tables_dir = str(Path(base_config.output_dir) / "tables")
    generate_all_tables(version_df, model_df, tables_dir)

    # Generate charts
    charts_dir = str(Path(base_config.output_dir) / "charts")
    generate_all_charts(version_df, model_df, raw_df, charts_dir, EVAL_GPT_MODEL)

    elapsed = time.perf_counter() - start_time
    logger.info("Full evaluation complete in %.1f seconds", elapsed)


def dry_run(base_config: EvalConfig) -> None:
    """Print the evaluation matrix without executing."""
    scenarios = _load_scenarios(base_config.scenarios_dir)

    exp1 = get_version_experiment(base_config)
    exp2 = get_model_experiment(base_config)

    # Collect unique (model, version) pairs
    configs: set[tuple[str, str]] = set()
    for exp in [exp1, exp2]:
        for model in exp.models:
            for version in exp.versions:
                configs.add((model, version))

    total_runs = len(scenarios) * len(configs) * base_config.runs_per_config

    print("\n=== Dry Run: Evaluation Matrix ===\n")
    print(f"Scenarios:       {len(scenarios)}")
    print(f"Configurations:  {len(configs)}")
    print(f"Runs per config: {base_config.runs_per_config}")
    print(f"Total runs:      {total_runs}")
    print(f"Provider:        {base_config.provider}")
    print(f"Judge model:     {base_config.judge_model}")
    print()

    print("Experiment 1 — Version Comparison:")
    for v in exp1.versions:
        for m in exp1.models:
            print(f"  {v:12s} × {m}")

    print("\nExperiment 2 — Model Comparison:")
    for m in exp2.models:
        for v in exp2.versions:
            print(f"  {m:30s} × {v}")

    print(f"\nScenarios:")
    for s in scenarios:
        ref_len = len(s.get("reference_architecture", {}).get("full_text", ""))
        print(f"  {s['id']:30s} — {s['name']} (ref: {ref_len} chars)")

    # Estimate existing cached results
    cached = 0
    for s in scenarios:
        for model, version in configs:
            for run in range(1, base_config.runs_per_config + 1):
                if result_path(base_config.output_dir, s["id"], model, version, run).exists():
                    cached += 1

    if cached:
        print(f"\nCached results:  {cached}/{total_runs} (will be skipped)")
        print(f"Remaining runs:  {total_runs - cached}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cloudy-Intell Academic Evaluation Framework",
    )
    parser.add_argument(
        "--experiment",
        choices=["all", "version", "model"],
        default="all",
        help="Which experiment to run (default: all)",
    )
    parser.add_argument(
        "--scenarios-dir",
        default="evaluation/scenarios",
        help="Directory containing scenario JSON files",
    )
    parser.add_argument(
        "--output-dir",
        default="evaluation/results",
        help="Directory to write results, tables, and charts",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per configuration (default: 3)",
    )
    parser.add_argument(
        "--provider",
        default="aws",
        choices=["aws", "azure"],
        help="Cloud provider for evaluation (default: aws)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print evaluation matrix without executing",
    )
    parser.add_argument(
        "--min-iterations",
        type=int,
        default=1,
        help="Min iterations for framework runner (default: 1)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Max iterations for framework runner (default: 3)",
    )

    args = parser.parse_args()

    base_config = EvalConfig(
        scenarios_dir=args.scenarios_dir,
        output_dir=args.output_dir,
        runs_per_config=args.runs,
        provider=args.provider,
        min_iterations=args.min_iterations,
        max_iterations=args.max_iterations,
    )

    if args.dry_run:
        dry_run(base_config)
    else:
        run_full_evaluation(base_config, args.experiment)


if __name__ == "__main__":
    main()
