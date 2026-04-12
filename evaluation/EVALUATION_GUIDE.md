# Cloudy-Intell Evaluation Framework — Complete Guide

This document covers how to set up, run, and interpret the academic evaluation framework for Cloudy-Intell.

---

## Table of Contents

1. [Overview](#overview)
2. [Experiment Design](#experiment-design)
3. [Prerequisites](#prerequisites)
4. [Environment Setup](#environment-setup)
5. [Scenarios](#scenarios)
6. [System Versions (Runners)](#system-versions-runners)
7. [Metrics](#metrics)
8. [Running the Evaluation](#running-the-evaluation)
   - [Dry Run](#1-dry-run-inspect-the-matrix)
   - [Stage 1: Generate](#2-stage-1-generate)
   - [Stage 2: Score](#3-stage-2-score)
   - [Stage 3: Analyze](#4-stage-3-analyze)
   - [Full Pipeline](#5-full-pipeline-all-stages)
9. [CLI Reference](#cli-reference)
10. [Output Structure](#output-structure)
11. [Analysis Outputs](#analysis-outputs)
12. [Cost Estimation](#cost-estimation)
13. [Recommended Workflow](#recommended-workflow)
14. [Troubleshooting](#troubleshooting)

---

## Overview

The evaluation framework benchmarks Cloudy-Intell across **three independent stages**:

| Stage | Command | Cost | Purpose |
|-------|---------|------|---------|
| **Generate** | `generate` | API quota ($$) | Run LLM systems, save raw architecture outputs |
| **Score** | `score` | Free (METEOR/BERTScore) or API (Judge) | Compute metrics on existing outputs |
| **Analyze** | `analyze` | Free | Aggregate results, generate thesis-ready charts and LaTeX tables |

Each stage can run independently, enabling incremental evaluation without re-running expensive API calls.

---

## Experiment Design

The framework runs **two experiments**:

### Experiment 1 — Version Comparison

Compares three system versions using a single model (GPT-5.4):

| Version | Description |
|---------|-------------|
| `baseline` | Single LLM call, no agents/tools/iteration |
| `agentic` | Architect phase only (supervisor → 4 domain agents → synthesizer) |
| `framework` | Full pipeline (architect → validator → iteration loop → final generator) |

**Matrix**: 3 versions × 1 model (GPT-5.4) × 5 scenarios × 3 runs = **45 runs**

### Experiment 2 — Model Comparison

Compares three LLM models using the full framework:

| Model | Provider |
|-------|----------|
| `gpt-5.4` | OpenAI |
| `claude-sonnet-4-6` | Anthropic |
| `gemini-3.1-pro-preview` | Google |

**Matrix**: 1 version (framework) × 3 models × 5 scenarios × 3 runs = **45 runs**

> **Note**: Framework × GPT-5.4 runs are shared across both experiments, so total unique runs = 75 (not 90).

---

## Prerequisites

### 1. Python Environment

The project requires Python 3.12+. Ensure the virtual environment is activated:

```bash
cd /path/to/CloudIntell
source .venv/bin/activate
```

### 2. Install the Package

The main project must be installed in editable mode so the evaluation can import from `cloudy_intell`:

```bash
pip install -e .
```

### 3. Install Evaluation Dependencies

```bash
pip install -r evaluation/requirements-eval.txt
```

This installs:
- `bert-score>=0.3.13` — DeBERTa-based semantic similarity
- `nltk>=3.9` — METEOR metric computation
- `pandas>=2.2` — DataFrame aggregation
- `matplotlib>=3.9` — Chart generation
- `seaborn>=0.13` — Statistical visualization styling
- `tabulate>=0.9` — Table formatting

### 4. NLTK Data (Auto-downloaded)

NLTK corpora (`punkt_tab`, `wordnet`) are downloaded automatically on first METEOR computation. No manual step needed.

---

## Environment Setup

### Required API Keys

Set these in your `.env` file or as environment variables:

```bash
# Required for all experiments
OPENAI_API_KEY=sk-...              # GPT models + LLM Judge (GPT-4o)
SERPER_API_KEY=...                 # Google Serper web search (used by agentic/framework runners)

# Required only for Experiment 2 (Model Comparison)
ANTHROPIC_API_KEY=sk-ant-...       # Claude models
GOOGLE_API_KEY=AI...               # Gemini models

# Optional — Tracing
LANGSMITH_API_KEY=lsv2_...         # LangSmith tracing (optional)
LANGSMITH_PROJECT=cloudy-intell    # LangSmith project name
LANGCHAIN_TRACING_V2=true          # Enable tracing
```

### ChromaDB Vector Stores

The `agentic` and `framework` runners use ChromaDB for RAG-based retrieval. Ensure the vector store directories exist:

```
chroma_db_AWSDocs/    # Pre-built AWS documentation embeddings
chroma_db_AzureDocs/  # Pre-built Azure documentation embeddings (if using --provider azure)
```

These must be pre-populated before running evaluation. They are used by domain architects and validators for documentation retrieval.

---

## Scenarios

Five evaluation scenarios are defined in `evaluation/scenarios/`, each representing a real-world AWS architecture pattern:

| # | ID | Description | Source |
|---|-----|-------------|--------|
| 1 | `three_tier_web` | Secure, scalable three-tier serverless web app | AWS Well-Architected |
| 2 | `serverless_data_lake` | Event-driven data lake with ETL and governance | AWS Docs |
| 3 | `disaster_recovery_warm_standby` | Multi-Region warm standby DR | AWS DR Guide |
| 4 | `containerized_microservices` | ECS/Fargate microservices with service discovery | AWS Containers Guide |
| 5 | `event_driven_ecommerce` | Event-driven order processing with EventBridge | AWS Event-Driven |

Each scenario JSON file contains:

```json
{
  "id": "three_tier_web",
  "name": "Three-Tier Serverless Web Application",
  "description": "...",
  "user_problem": "Design a secure, scalable ...",
  "reference_architecture": {
    "full_text": "Ground truth architecture from AWS docs ...",
    "services_expected": ["S3", "CloudFront", "Lambda", "DynamoDB", ...],
    "domains_covered": ["compute", "network", "storage", "database"]
  },
  "source": "https://docs.aws.amazon.com/..."
}
```

> **Important**: Scenarios with `"REPLACE"` placeholder text in `reference_architecture.full_text` are automatically skipped with a warning.

---

## System Versions (Runners)

### Baseline (`evaluation/runners/baseline_runner.py`)

- **What it does**: Single LLM API call with a structured system prompt
- **No agents, no tools, no iteration**
- **Represents**: What a user would get by pasting the problem into ChatGPT directly
- **Output**: 6-section architecture document

### Agentic (`evaluation/runners/agentic_runner.py`)

- **What it does**: Builds a `RuntimeContext` with LLM, ChromaDB vector store, and tool bundle (RAG + web search), then runs the architect subgraph
- **Graph**: `START → architect_subgraph → END` (single pass)
- **Uses**: 4 domain agents (compute, network, storage, database) in parallel + synthesizer
- **No validation loop or iteration**
- **Represents**: Value of multi-agent decomposition + tool use

### Framework (`evaluation/runners/framework_runner.py`)

- **What it does**: Full Cloudy-Intell pipeline with architect phase, validator phase, iteration loop, and final architecture generator
- **Graph**: `START → architect_phase → validator_phase → routing → (loop or finish) → final_generator → END`
- **Iterations**: Configurable via `--min-iterations` (default: 1) and `--max-iterations` (default: 3)
- **Represents**: Complete Cloudy-Intell system

---

## Metrics

Three complementary metrics evaluate generated architectures against reference solutions:

### METEOR Score (Free, Local)

- **Type**: N-gram-based metric with stemming and synonym matching
- **Range**: 0.0 – 1.0
- **Best for**: Checking phrase and term coverage
- **Cost**: Free (local computation)

### BERTScore (Free, Local)

- **Type**: Semantic similarity using `microsoft/deberta-xlarge-mnli` embeddings
- **Returns**: Precision, Recall, and F1 (all 0.0 – 1.0)
- **Best for**: Detecting semantic equivalence even with different wording
- **Cost**: Free (local computation, ~1 min per run)

### LLM-as-Judge (API Cost)

- **Type**: Independent LLM (GPT-4o by default) scores on 6 dimensions
- **Dimensions** (1–10 scale each):
  1. **Completeness** — Coverage of required components
  2. **Technical Accuracy** — Correct service names, configs, integration patterns
  3. **Security** — IAM, encryption, network isolation, audit logging
  4. **Scalability** — Auto-scaling, load balancing, multi-AZ
  5. **Best Practices** — AWS Well-Architected Framework alignment
  6. **Specificity** — Concrete services/configs vs. generic advice
- **Returns**: 6 dimension scores + total (average) + reasoning text
- **Cost**: ~$0.10 per evaluation (uses GPT-4o)

---

## Running the Evaluation

All commands are run from the project root directory:

```bash
cd /path/to/CloudIntell
source .venv/bin/activate
```

### 1. Dry Run — Inspect the Matrix

Preview what will be evaluated without making any API calls:

```bash
python -m evaluation.run_evaluation dry-run
```

Output shows:
- Number of scenarios, configurations, and total runs
- Experiment matrices
- Already cached results (will be skipped)

### 2. Stage 1: Generate

Generate raw architecture outputs by running LLM systems.

#### Run everything (all experiments):

```bash
python -m evaluation.run_evaluation generate
```

#### Run a single experiment:

```bash
# Experiment 1 only (version comparison with GPT-5.4)
python -m evaluation.run_evaluation generate --experiment version

# Experiment 2 only (model comparison with framework)
python -m evaluation.run_evaluation generate --experiment model
```

#### Filter to specific slices (save cost):

```bash
# Single scenario, single version, single run
python -m evaluation.run_evaluation generate \
  --scenario three_tier_web \
  --version baseline \
  --runs 1

# Multiple scenarios (comma-separated)
python -m evaluation.run_evaluation generate \
  --scenario three_tier_web,serverless_data_lake \
  --version framework \
  --model gpt-5.4

# Specific run numbers
python -m evaluation.run_evaluation generate \
  --scenario three_tier_web \
  --run 1,2
```

#### Force regeneration (overwrite cached results):

```bash
python -m evaluation.run_evaluation generate --force
```

#### Set iteration bounds for framework runner:

```bash
python -m evaluation.run_evaluation generate \
  --experiment version \
  --min-iterations 1 \
  --max-iterations 3
```

### 3. Stage 2: Score

Compute metrics on previously generated outputs. Only computes missing metrics (incremental).

#### Score with all metrics:

```bash
python -m evaluation.run_evaluation score
```

#### Score with free metrics only (no API cost):

```bash
python -m evaluation.run_evaluation score --metrics meteor bert
```

#### Add LLM judge scores later:

```bash
python -m evaluation.run_evaluation score --metrics judge
```

#### Use a different judge model:

```bash
python -m evaluation.run_evaluation score --metrics judge --judge-model gpt-4o-mini
```

#### Filter scoring to specific slices:

```bash
python -m evaluation.run_evaluation score \
  --scenario three_tier_web \
  --version baseline \
  --metrics meteor bert
```

#### Force recomputation of existing metrics:

```bash
python -m evaluation.run_evaluation score --metrics meteor --force
```

### 4. Stage 3: Analyze

Aggregate all scored results and generate thesis-ready charts and LaTeX tables:

```bash
python -m evaluation.run_evaluation analyze
```

This reads all `run_*_metrics.json` files, aggregates by configuration, and outputs:
- **Charts** → `evaluation/results/charts/` (PDF + PNG)
- **Tables** → `evaluation/results/tables/` (LaTeX `.tex` files)

### 5. Full Pipeline (All Stages)

For backward compatibility, you can also use the legacy full pipeline approach:

```bash
python -m evaluation.run_evaluation generate --experiment all
python -m evaluation.run_evaluation score
python -m evaluation.run_evaluation analyze
```

---

## CLI Reference

### Global Arguments (all subcommands)

| Argument | Default | Description |
|----------|---------|-------------|
| `--scenarios-dir` | `evaluation/scenarios` | Directory containing scenario JSON files |
| `--output-dir` | `evaluation/results` | Directory for results, tables, and charts |
| `--provider` | `aws` | Cloud provider (`aws` or `azure`) |

### Filter Arguments (`generate`, `score`)

| Argument | Example | Description |
|----------|---------|-------------|
| `--scenario` | `three_tier_web,serverless_data_lake` | Comma-separated scenario IDs |
| `--model` | `gpt-5.4` | Comma-separated model names |
| `--version` | `baseline,framework` | Comma-separated versions |
| `--run` | `1,2` | Comma-separated run numbers |

### `generate` Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--experiment` | `all` | Which experiment: `all`, `version`, or `model` |
| `--runs` | `3` | Number of runs per configuration |
| `--min-iterations` | `1` | Min iterations for framework runner |
| `--max-iterations` | `3` | Max iterations for framework runner |
| `--force` | `false` | Regenerate even if cached |

### `score` Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--metrics` | `all` | Space-separated: `meteor`, `bert`, `judge`, or `all` |
| `--judge-model` | `gpt-4o` | Model for LLM judge |
| `--force` | `false` | Recompute even if cached |

### `dry-run` Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--runs` | `3` | Runs per config (for matrix calculation) |

---

## Output Structure

```
evaluation/results/
├── <scenario_id>/                          # e.g., three_tier_web
│   ├── <model>/                            # e.g., gpt-5.4
│   │   ├── <version>/                      # e.g., baseline
│   │   │   ├── run_1.json                  # Raw generated output
│   │   │   ├── run_1_metrics.json          # Computed metrics
│   │   │   ├── run_2.json
│   │   │   ├── run_2_metrics.json
│   │   │   └── run_3.json
│   │   │   └── run_3_metrics.json
│   │   ├── agentic/
│   │   │   └── ...
│   │   └── framework/
│   │       └── ...
│   ├── claude-sonnet-4-6/
│   │   └── framework/
│   │       └── ...
│   └── gemini-3.1-pro-preview/
│       └── framework/
│           └── ...
├── charts/                                 # Generated visualizations
│   ├── exp1_version_comparison.pdf
│   ├── exp1_version_comparison.png
│   ├── exp1_bertscore_boxplot.pdf
│   ├── exp2_model_comparison.pdf
│   ├── exp2_judge_radar.pdf
│   └── exp2_judge_heatmap.pdf
└── tables/                                 # LaTeX tables
    ├── exp1_per_metric.tex
    ├── exp1_summary.tex
    ├── exp2_per_metric.tex
    ├── exp2_summary.tex
    └── exp2_judge_dimensions.tex
```

### Raw Output File (`run_N.json`)

```json
{
  "scenario_id": "three_tier_web",
  "model": "gpt-5.4",
  "version": "framework",
  "run": 1,
  "output": "## Executive Summary\n\nThis architecture ...",
  "elapsed_seconds": 42.5
}
```

### Metrics File (`run_N_metrics.json`)

```json
{
  "meteor": 0.523,
  "bert_score_precision": 0.812,
  "bert_score_recall": 0.795,
  "bert_score_f1": 0.803,
  "judge_completeness": 8,
  "judge_technical_accuracy": 9,
  "judge_security": 7,
  "judge_scalability": 8,
  "judge_best_practices": 8,
  "judge_specificity": 7,
  "judge_total": 7.83,
  "judge_reasoning": "The architecture covers all four domains ...",
  "elapsed_seconds": 42.5
}
```

---

## Analysis Outputs

### Charts (Experiment 1 — Version Comparison)

1. **Grouped Bar Chart** — Mean metric scores (METEOR, BERTScore F1, Judge Total) by version with error bars
2. **Box Plot** — BERTScore F1 distribution across scenarios and runs per version

### Charts (Experiment 2 — Model Comparison)

3. **Grouped Bar Chart** — Mean metric scores by model with error bars
4. **Radar/Spider Chart** — Judge dimension profiles (6 axes) per model
5. **Heatmap** — Judge dimension scores (rows = models, cols = dimensions)

### LaTeX Tables

1. **Exp 1 Per-Metric** — Rows = scenarios, columns = versions, cells = `mean ± std`
2. **Exp 1 Summary** — Aggregated across all scenarios
3. **Exp 2 Per-Metric** — Rows = scenarios, columns = models
4. **Exp 2 Summary** — Aggregated across all scenarios
5. **Exp 2 Judge Dimensions** — Rows = models, columns = 6 judge dimensions + total

All tables use `booktabs` style (`\toprule`, `\midrule`, `\bottomrule`).

---

## Cost Estimation

### API Costs (Approximate)

| Component | Runs | Estimated Cost |
|-----------|------|----------------|
| Baseline (GPT-5.4) | 15 | ~$2 |
| Agentic (GPT-5.4) | 15 | ~$45 |
| Framework (GPT-5.4) | 15 | ~$90 |
| Framework (Claude Sonnet 4.6) | 15 | ~$45 |
| Framework (Gemini 3.1 Pro) | 15 | ~$45 |
| LLM Judge (GPT-4o) | 75 | ~$8 |
| **Total** | **75** | **~$235** |

### Free Metrics

METEOR and BERTScore are computed locally at no API cost.

### Cost Optimization Strategy

1. Start with baseline runs (cheapest) to validate the pipeline
2. Run free metrics first (`--metrics meteor bert`)
3. Add judge scoring last (`--metrics judge`)
4. Use `--scenario` and `--run` filters to test with minimal slices

---

## Recommended Workflow

### Step 1 — Validate Setup

```bash
# Check the evaluation matrix
python -m evaluation.run_evaluation dry-run

# Test with one cheap run
python -m evaluation.run_evaluation generate \
  --scenario three_tier_web \
  --version baseline \
  --runs 1

# Score with free metrics
python -m evaluation.run_evaluation score \
  --scenario three_tier_web \
  --version baseline \
  --metrics meteor bert
```

### Step 2 — Run Experiment 1 (Version Comparison)

```bash
# Generate all version comparison runs
python -m evaluation.run_evaluation generate --experiment version

# Score with free metrics
python -m evaluation.run_evaluation score \
  --version baseline,agentic,framework \
  --model gpt-5.4 \
  --metrics meteor bert

# Add judge scores
python -m evaluation.run_evaluation score \
  --version baseline,agentic,framework \
  --model gpt-5.4 \
  --metrics judge
```

### Step 3 — Run Experiment 2 (Model Comparison)

```bash
# Generate model comparison runs (GPT already done from Step 2)
python -m evaluation.run_evaluation generate --experiment model

# Score all model comparison outputs
python -m evaluation.run_evaluation score \
  --version framework \
  --metrics meteor bert

python -m evaluation.run_evaluation score \
  --version framework \
  --metrics judge
```

### Step 4 — Generate Thesis Outputs

```bash
python -m evaluation.run_evaluation analyze
```

Charts and tables will be in `evaluation/results/charts/` and `evaluation/results/tables/`.

---

## Troubleshooting

### "No valid scenarios found"

Ensure scenario JSON files exist in `evaluation/scenarios/` and that `reference_architecture.full_text` does not start with `"REPLACE"`.

### "No generated outputs found"

Run `generate` before `score`. The `score` command only computes metrics on existing output files.

### NLTK Download Errors

If NLTK data download fails behind a proxy:

```bash
python -c "import nltk; nltk.download('punkt_tab'); nltk.download('wordnet')"
```

### BERTScore Slow on First Run

The first BERTScore computation downloads the `microsoft/deberta-xlarge-mnli` model (~1.5 GB). Subsequent runs use the cached model.

### Import Errors

Ensure the package is installed in editable mode:

```bash
pip install -e .
```

### API Rate Limits

The framework runs are sequential, but if you hit rate limits:
- Reduce `--runs` to `1` for initial testing
- Use `--scenario` to process one scenario at a time
- Cached results are automatically skipped on re-run

### Missing API Keys

| Error | Missing Key |
|-------|-------------|
| `openai.AuthenticationError` | `OPENAI_API_KEY` |
| `anthropic.AuthenticationError` | `ANTHROPIC_API_KEY` |
| `google.api_core.exceptions.Unauthenticated` | `GOOGLE_API_KEY` |
| `Serper API error` | `SERPER_API_KEY` |
