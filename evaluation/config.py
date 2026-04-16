"""Evaluation configuration for the two-experiment design.

Experiment 1 — Version Comparison:
    3 versions (baseline, agentic, framework) × GPT only

Experiment 2 — Model Comparison:
    Framework only × 3 models (GPT, Claude, Gemini)

Framework × GPT runs are shared across both experiments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# ── Model identifiers used in evaluation ────────────────────────────────
EVAL_GPT_MODEL = "gpt-5.4"
EVAL_CLAUDE_MODEL = "claude-sonnet-4-6"
EVAL_GEMINI_MODEL = "gemini-3.1-pro-preview"

EVAL_JUDGE_MODEL = "claude-sonnet-4-6"

# Versions
VERSION_BASELINE = "baseline"
VERSION_AGENTIC = "agentic"
VERSION_FRAMEWORK = "framework"

ALL_VERSIONS = [VERSION_BASELINE, VERSION_AGENTIC, VERSION_FRAMEWORK]
ALL_MODELS = [EVAL_GPT_MODEL, EVAL_CLAUDE_MODEL, EVAL_GEMINI_MODEL]

ExperimentName = Literal["version_comparison", "model_comparison"]


@dataclass
class EvalConfig:
    """Shared evaluation settings."""

    scenarios_dir: str = "evaluation/scenarios"
    output_dir: str = "evaluation/results"
    runs_per_config: int = 3
    provider: str = "aws"
    judge_model: str = EVAL_JUDGE_MODEL
    min_iterations: int = 1
    max_iterations: int = 3


@dataclass
class ExperimentConfig:
    """A single experiment's model × version matrix."""

    name: ExperimentName
    models: list[str]
    versions: list[str]
    base: EvalConfig = field(default_factory=EvalConfig)


def get_version_experiment(base: EvalConfig | None = None) -> ExperimentConfig:
    """Experiment 1: compare Baseline vs Agentic vs Framework using GPT."""
    return ExperimentConfig(
        name="version_comparison",
        models=[EVAL_GPT_MODEL],
        versions=ALL_VERSIONS,
        base=base or EvalConfig(),
    )


def get_model_experiment(base: EvalConfig | None = None) -> ExperimentConfig:
    """Experiment 2: compare GPT vs Claude vs Gemini using Framework."""
    return ExperimentConfig(
        name="model_comparison",
        models=ALL_MODELS,
        versions=[VERSION_FRAMEWORK],
        base=base or EvalConfig(),
    )


@dataclass
class RunFilter:
    """Fine-grained filter for selecting a subset of evaluation runs."""

    scenarios: list[str] | None = None
    models: list[str] | None = None
    versions: list[str] | None = None
    runs: list[int] | None = None

    def matches(
        self,
        scenario_id: str,
        model: str,
        version: str,
        run: int,
    ) -> bool:
        """Return True if the given run matches all active filters."""
        if self.scenarios and scenario_id not in self.scenarios:
            return False
        if self.models and model not in self.models:
            return False
        if self.versions and version not in self.versions:
            return False
        if self.runs and run not in self.runs:
            return False
        return True


# ── Metric names ────────────────────────────────────────────────────────
METRIC_METEOR = "meteor"
METRIC_BERT = "bert"
METRIC_JUDGE = "judge"
ALL_METRICS = [METRIC_METEOR, METRIC_BERT, METRIC_JUDGE]


def result_path(
    output_dir: str,
    scenario_id: str,
    model: str,
    version: str,
    run: int,
    suffix: str = "",
) -> Path:
    """Build the canonical result file path.

    Layout: ``<output_dir>/<scenario_id>/<model>/<version>/run_<n><suffix>.json``
    """
    return Path(output_dir) / scenario_id / model / version / f"run_{run}{suffix}.json"
