"""Result aggregation across runs, scenarios, and experiments.

Loads all metrics JSON files from the results directory, groups by
(scenario, model, version), and computes mean ± std across the N
runs per configuration.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_all_metrics(results_dir: str) -> pd.DataFrame:
    """Load every ``run_*_metrics.json`` file into a single DataFrame.

    Each row represents one run's metrics for a specific
    (scenario, model, version) configuration.
    """
    records: list[dict] = []
    results_path = Path(results_dir)

    for metrics_file in sorted(results_path.rglob("run_*_metrics.json")):
        parts = metrics_file.relative_to(results_path).parts
        if len(parts) < 4:
            logger.warning("Skipping unexpected path: %s", metrics_file)
            continue

        scenario_id, model, version, filename = parts[0], parts[1], parts[2], parts[3]
        run_num = filename.replace("run_", "").replace("_metrics.json", "")

        try:
            data = json.loads(metrics_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read %s: %s", metrics_file, e)
            continue

        record = {
            "scenario": scenario_id,
            "model": model,
            "version": version,
            "run": int(run_num),
            "meteor": data.get("meteor", None),
            "bert_score_precision": data.get("bert_score_precision", None),
            "bert_score_recall": data.get("bert_score_recall", None),
            "bert_score_f1": data.get("bert_score_f1", None),
            "judge_completeness": data.get("judge_completeness", None),
            "judge_technical_accuracy": data.get("judge_technical_accuracy", None),
            "judge_security": data.get("judge_security", None),
            "judge_scalability": data.get("judge_scalability", None),
            "judge_best_practices": data.get("judge_best_practices", None),
            "judge_specificity": data.get("judge_specificity", None),
            "judge_total": data.get("judge_total", None),
            "elapsed_seconds": data.get("elapsed_seconds", None),
        }
        records.append(record)

    df = pd.DataFrame(records)
    logger.info("Loaded %d metric records from %s", len(df), results_dir)
    return df


def aggregate_by_config(df: pd.DataFrame) -> pd.DataFrame:
    """Compute mean and std for each (scenario, model, version) group.

    Returns a DataFrame with one row per (scenario, model, version) and
    columns ``<metric>_mean`` and ``<metric>_std`` for each numeric metric.
    """
    metric_cols = [
        "meteor", "bert_score_f1",
        "judge_completeness", "judge_technical_accuracy",
        "judge_security", "judge_scalability",
        "judge_best_practices", "judge_specificity", "judge_total",
        "elapsed_seconds",
    ]

    existing_cols = [c for c in metric_cols if c in df.columns]
    grouped = df.groupby(["scenario", "model", "version"])[existing_cols]

    means = grouped.mean().rename(columns={c: f"{c}_mean" for c in existing_cols})
    stds = grouped.std(ddof=1).rename(columns={c: f"{c}_std" for c in existing_cols})

    result = means.join(stds).reset_index()
    return result


def split_experiments(agg_df: pd.DataFrame, gpt_model: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split aggregated results into version-comparison and model-comparison DataFrames.

    Args:
        agg_df: Aggregated DataFrame from ``aggregate_by_config``.
        gpt_model: The GPT model identifier (e.g. ``"gpt-5.4"``).

    Returns:
        ``(version_df, model_df)`` — the two experiment subsets.
    """
    # Experiment 1: all versions, GPT only
    version_df = agg_df[agg_df["model"] == gpt_model].copy()

    # Experiment 2: framework only, all models
    model_df = agg_df[agg_df["version"] == "framework"].copy()

    return version_df, model_df
