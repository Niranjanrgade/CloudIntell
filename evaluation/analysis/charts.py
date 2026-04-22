"""Matplotlib/seaborn chart generation for thesis figures.

Generates publication-ready charts organized by experiment:
  - Experiment 1: grouped bar chart (version comparison), box plot
  - Experiment 2: grouped bar chart (model comparison), radar chart, heatmap

All charts use consistent academic styling suitable for thesis embedding.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)

# Use non-interactive backend for server/CLI use
matplotlib.use("Agg")

# ── Academic styling ──────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.1,
})

VERSION_LABELS = {"baseline": "Single Prompt LLM", "agentic": "Agentic Framework", "framework": "Evaluator Optimiser Loop Framework"}
MODEL_LABELS = {
    "gpt-5.4": "GPT-5.4",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro",
}
METRIC_LABELS = {
    "meteor": "METEOR",
    "bert_score_f1": "BERTScore F1",
    "judge_total": "Judge Total",
}

PALETTE_VERSIONS = ["#2196F3", "#FF9800", "#4CAF50"]
PALETTE_MODELS = ["#2196F3", "#9C27B0", "#F44336"]


def _save(fig: Figure, output_dir: str, name: str) -> list[str]:
    """Save figure as both PDF and PNG."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("pdf", "png"):
        fpath = out / f"{name}.{ext}"
        fig.savefig(str(fpath))
        paths.append(str(fpath))
    plt.close(fig)
    logger.info("Saved chart: %s", name)
    return paths


# ── Experiment 1: Version Comparison Charts ───────────────────────────────


def chart_version_grouped_bar(
    version_df: pd.DataFrame,
    output_dir: str,
) -> list[str]:
    """Chart 1: Grouped bar chart — version comparison (GPT only).

    X-axis: metrics, grouped bars: one per version, with error bars.
    """
    metrics = ["meteor", "bert_score_f1", "judge_total"]
    versions = ["baseline", "agentic", "framework"]

    data = []
    for version in versions:
        subset = version_df[version_df["version"] == version]
        for metric in metrics:
            mean_col = f"{metric}_mean"
            std_col = f"{metric}_std"
            if mean_col in subset.columns:
                m = subset[mean_col].mean()
                s = subset[mean_col].std() if len(subset) > 1 else 0.0
                # For judge_total, normalize to 0-1 scale for comparability
                if metric == "judge_total":
                    m, s = m / 10.0, s / 10.0
                data.append({
                    "Version": VERSION_LABELS.get(version, version),
                    "Metric": METRIC_LABELS[metric],
                    "Score": m,
                    "Std": s,
                })

    if not data:
        return []

    df = pd.DataFrame(data)
    fig, ax = plt.subplots(figsize=(8, 5))

    metric_names = [METRIC_LABELS[m] for m in metrics]
    x = np.arange(len(metric_names))
    width = 0.25

    for i, version in enumerate(versions):
        v_label = VERSION_LABELS[version]
        v_data = df[df["Version"] == v_label]
        means = [v_data[v_data["Metric"] == m]["Score"].values[0] if len(v_data[v_data["Metric"] == m]) else 0 for m in metric_names]
        stds = [v_data[v_data["Metric"] == m]["Std"].values[0] if len(v_data[v_data["Metric"] == m]) else 0 for m in metric_names]
        ax.bar(x + i * width, means, width, yerr=stds, label=v_label,
               color=PALETTE_VERSIONS[i], capsize=3, edgecolor="white", linewidth=0.5)

    ax.set_xlabel("Metric")
    ax.set_ylabel("Score")
    ax.set_title("Version Comparison (GPT-5.4)")
    ax.set_xticks(x + width)
    ax.set_xticklabels(metric_names)
    ax.legend()
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", alpha=0.3)

    return _save(fig, output_dir, "chart_version_grouped_bar")


def chart_version_box_plot(
    raw_df: pd.DataFrame,
    output_dir: str,
    gpt_model: str,
) -> list[str]:
    """Chart 2: Box plot — BERTScore F1 distribution across versions (GPT).

    Uses raw (non-aggregated) data for proper distribution display.
    """
    subset = raw_df[raw_df["model"] == gpt_model].copy()
    if "bert_score_f1" not in subset.columns or subset["bert_score_f1"].isna().all():
        return []

    subset["Version"] = subset["version"].map(VERSION_LABELS)

    fig, ax = plt.subplots(figsize=(7, 5))
    order = [VERSION_LABELS[v] for v in ["baseline", "agentic", "framework"] if VERSION_LABELS[v] in subset["Version"].values]
    sns.boxplot(data=subset, x="Version", y="bert_score_f1", order=order,
                palette=PALETTE_VERSIONS[:len(order)], ax=ax)
    ax.set_xlabel("System Version")
    ax.set_ylabel("BERTScore F1")
    ax.set_title("BERTScore F1 Distribution by Version (GPT-5.4)")
    ax.grid(axis="y", alpha=0.3)

    return _save(fig, output_dir, "chart_version_boxplot")


# ── Experiment 2: Model Comparison Charts ─────────────────────────────────


def chart_model_grouped_bar(
    model_df: pd.DataFrame,
    output_dir: str,
) -> list[str]:
    """Chart 3: Grouped bar chart — model comparison (Framework only)."""
    metrics = ["meteor", "bert_score_f1", "judge_total"]
    models = sorted(model_df["model"].unique())

    data = []
    for model in models:
        subset = model_df[model_df["model"] == model]
        for metric in metrics:
            mean_col = f"{metric}_mean"
            std_col = f"{metric}_std"
            if mean_col in subset.columns:
                m = subset[mean_col].mean()
                s = subset[mean_col].std() if len(subset) > 1 else 0.0
                if metric == "judge_total":
                    m, s = m / 10.0, s / 10.0
                data.append({
                    "Model": MODEL_LABELS.get(model, model),
                    "Metric": METRIC_LABELS[metric],
                    "Score": m,
                    "Std": s,
                })

    if not data:
        return []

    df = pd.DataFrame(data)
    fig, ax = plt.subplots(figsize=(8, 5))

    metric_names = [METRIC_LABELS[m] for m in metrics]
    x = np.arange(len(metric_names))
    width = 0.25

    for i, model in enumerate(models):
        m_label = MODEL_LABELS.get(model, model)
        m_data = df[df["Model"] == m_label]
        means = [m_data[m_data["Metric"] == mn]["Score"].values[0] if len(m_data[m_data["Metric"] == mn]) else 0 for mn in metric_names]
        stds = [m_data[m_data["Metric"] == mn]["Std"].values[0] if len(m_data[m_data["Metric"] == mn]) else 0 for mn in metric_names]
        ax.bar(x + i * width, means, width, yerr=stds, label=m_label,
               color=PALETTE_MODELS[i], capsize=3, edgecolor="white", linewidth=0.5)

    ax.set_xlabel("Metric")
    ax.set_ylabel("Score")
    ax.set_title("Model Comparison (Evaluator Optimiser Loop Framework)")
    ax.set_xticks(x + width)
    ax.set_xticklabels(metric_names)
    ax.legend()
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", alpha=0.3)

    return _save(fig, output_dir, "chart_model_grouped_bar")


def chart_model_radar(
    model_df: pd.DataFrame,
    output_dir: str,
) -> list[str]:
    """Chart 4: Radar/spider chart — model strength profiles (Framework)."""
    dims = [
        ("judge_completeness", "Completeness"),
        ("judge_technical_accuracy", "Accuracy"),
        ("judge_security", "Security"),
        ("judge_scalability", "Scalability"),
        ("judge_best_practices", "Best Practices"),
        ("judge_specificity", "Specificity"),
    ]
    dim_keys = [d[0] for d in dims]
    dim_labels = [d[1] for d in dims]
    models = sorted(model_df["model"].unique())

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    angles = np.linspace(0, 2 * np.pi, len(dims), endpoint=False).tolist()
    angles += angles[:1]  # close the polygon

    for i, model in enumerate(models):
        subset = model_df[model_df["model"] == model]
        values = []
        for dk in dim_keys:
            mean_col = f"{dk}_mean"
            if mean_col in subset.columns:
                values.append(subset[mean_col].mean())
            else:
                values.append(0)
        values += values[:1]  # close

        ax.plot(angles, values, "o-", label=MODEL_LABELS.get(model, model),
                color=PALETTE_MODELS[i], linewidth=2, markersize=4)
        ax.fill(angles, values, alpha=0.1, color=PALETTE_MODELS[i])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dim_labels)
    ax.set_ylim(0, 10)
    ax.set_title("LLM Judge Dimension Profiles (Evaluator Optimiser Loop Framework)", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

    return _save(fig, output_dir, "chart_model_radar")


def chart_model_heatmap(
    model_df: pd.DataFrame,
    output_dir: str,
) -> list[str]:
    """Chart 5: Heatmap — LLM Judge dimensions by model (Framework)."""
    dims = [
        ("judge_completeness", "Completeness"),
        ("judge_technical_accuracy", "Accuracy"),
        ("judge_security", "Security"),
        ("judge_scalability", "Scalability"),
        ("judge_best_practices", "Best Practices"),
        ("judge_specificity", "Specificity"),
        ("judge_total", "Total"),
    ]
    # Fixed order: Claude on top, GPT in middle, Gemini at bottom
    preferred_order = ["claude-sonnet-4-6", "gpt-5.4", "gemini-3.1-pro-preview"]
    available = set(model_df["model"].unique())
    models = [m for m in preferred_order if m in available]
    # Append any unexpected models at the end
    models.extend(m for m in sorted(available) if m not in models)

    matrix = []
    row_labels = []
    for model in models:
        subset = model_df[model_df["model"] == model]
        row = []
        for dk, _ in dims:
            mean_col = f"{dk}_mean"
            if mean_col in subset.columns:
                row.append(subset[mean_col].mean())
            else:
                row.append(0)
        matrix.append(row)
        row_labels.append(MODEL_LABELS.get(model, model))

    matrix_np = np.array(matrix)
    col_labels = [d[1] for d in dims]

    fig, ax = plt.subplots(figsize=(9, 4))
    im = ax.imshow(matrix_np, cmap="YlGnBu", aspect="auto", vmin=1, vmax=10)

    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_yticks(np.arange(len(row_labels)))
    xlabels = ax.set_xticklabels(col_labels, rotation=45, ha="right")
    xlabels[-1].set_fontweight("bold")
    ax.set_yticklabels(row_labels)

    # Annotate cells with values (2 decimal places for Total column)
    total_col_idx = len(col_labels) - 1
    for i in range(len(row_labels)):
        for j in range(len(col_labels)):
            val = matrix_np[i, j]
            color = "white" if val > 6.5 else "black"
            fmt = f"{val:.2f}" if j == total_col_idx else f"{val:.1f}"
            weight = "bold" if j == total_col_idx else "normal"
            ax.text(j, i, fmt, ha="center", va="center", color=color,
                    fontsize=10, fontweight=weight)

    fig.colorbar(im, ax=ax, label="Score (1-10)")
    ax.set_title("LLM Judge Dimension Scores by Model (Evaluator Optimiser Loop Framework)")
    fig.tight_layout()

    return _save(fig, output_dir, "chart_model_heatmap")


def chart_version_heatmap(
    version_df: pd.DataFrame,
    output_dir: str,
) -> list[str]:
    """Chart 6: Heatmap — LLM Judge dimensions by version (GPT-5.4)."""
    dims = [
        ("judge_completeness", "Completeness"),
        ("judge_technical_accuracy", "Accuracy"),
        ("judge_security", "Security"),
        ("judge_scalability", "Scalability"),
        ("judge_best_practices", "Best Practices"),
        ("judge_specificity", "Specificity"),
        ("judge_total", "Total"),
    ]
    # Fixed order: Evaluator Optimiser Loop Framework on top, Agentic Framework in middle, Single Prompt LLM at bottom
    preferred_order = ["framework", "agentic", "baseline"]
    available = set(version_df["version"].unique())
    versions = [v for v in preferred_order if v in available]
    versions.extend(v for v in sorted(available) if v not in versions)

    matrix = []
    row_labels = []
    for version in versions:
        subset = version_df[version_df["version"] == version]
        row = []
        for dk, _ in dims:
            mean_col = f"{dk}_mean"
            if mean_col in subset.columns:
                row.append(subset[mean_col].mean())
            else:
                row.append(0)
        matrix.append(row)
        row_labels.append(VERSION_LABELS.get(version, version))

    matrix_np = np.array(matrix)
    col_labels = [d[1] for d in dims]

    fig, ax = plt.subplots(figsize=(9, 4))
    im = ax.imshow(matrix_np, cmap="YlGnBu", aspect="auto", vmin=1, vmax=10)

    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_yticks(np.arange(len(row_labels)))
    xlabels = ax.set_xticklabels(col_labels, rotation=45, ha="right", fontsize=12)
    xlabels[-1].set_fontweight("bold")
    ax.set_yticklabels(row_labels, fontsize=12)

    # Annotate cells with values (2 decimal places for Total column)
    total_col_idx = len(col_labels) - 1
    for i in range(len(row_labels)):
        for j in range(len(col_labels)):
            val = matrix_np[i, j]
            color = "white" if val > 6.5 else "black"
            fmt = f"{val:.2f}" if j == total_col_idx else f"{val:.1f}"
            weight = "bold" if j == total_col_idx else "normal"
            ax.text(j, i, fmt, ha="center", va="center", color=color,
                    fontsize=13, fontweight=weight)

    fig.colorbar(im, ax=ax, label="Score (1-10)")
    ax.set_title("LLM Judge Dimension Scores by Version (GPT-5.4)", fontsize=13)
    fig.tight_layout()

    return _save(fig, output_dir, "chart_version_heatmap")

def chart_combined_heatmap(
    agg_df: pd.DataFrame,
    output_dir: str,
) -> list[str]:
    """Chart 7: Heatmap — LLM Judge dimensions by version, averaged across all models."""
    dims = [
        ("judge_completeness", "Completeness"),
        ("judge_technical_accuracy", "Accuracy"),
        ("judge_security", "Security"),
        ("judge_scalability", "Scalability"),
        ("judge_best_practices", "Best Practices"),
        ("judge_specificity", "Specificity"),
        ("judge_total", "Total"),
    ]
    preferred_order = ["framework", "agentic", "baseline"]
    available = set(agg_df["version"].unique())
    versions = [v for v in preferred_order if v in available]
    versions.extend(v for v in sorted(available) if v not in versions)

    matrix = []
    row_labels = []
    for version in versions:
        subset = agg_df[agg_df["version"] == version]
        row = []
        for dk, _ in dims:
            mean_col = f"{dk}_mean"
            if mean_col in subset.columns and not subset[mean_col].isna().all():
                row.append(subset[mean_col].mean())
            else:
                row.append(0)
        matrix.append(row)
        row_labels.append(VERSION_LABELS.get(version, version))

    matrix_np = np.array(matrix)
    col_labels = [d[1] for d in dims]

    fig, ax = plt.subplots(figsize=(9, 4))
    im = ax.imshow(matrix_np, cmap="YlGnBu", aspect="auto", vmin=1, vmax=10)

    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_yticks(np.arange(len(row_labels)))
    xlabels = ax.set_xticklabels(col_labels, rotation=45, ha="right", fontsize=12)
    xlabels[-1].set_fontweight("bold")
    ax.set_yticklabels(row_labels, fontsize=12)

    total_col_idx = len(col_labels) - 1
    for i in range(len(row_labels)):
        for j in range(len(col_labels)):
            val = matrix_np[i, j]
            color = "white" if val > 6.5 else "black"
            fmt = f"{val:.2f}" if j == total_col_idx else f"{val:.1f}"
            weight = "bold" if j == total_col_idx else "normal"
            ax.text(j, i, fmt, ha="center", va="center", color=color,
                    fontsize=13, fontweight=weight)

    fig.colorbar(im, ax=ax, label="Score (1-10)")
    ax.set_title("LLM Judge Dimension Scores by Version (All LLMs Combined)", fontsize=13)
    fig.tight_layout()

    return _save(fig, output_dir, "chart_combined_heatmap")

def generate_all_charts(
    version_df: pd.DataFrame,
    model_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    output_dir: str,
    gpt_model: str = "gpt-5.4",
    agg_df: pd.DataFrame | None = None,
) -> list[str]:
    """Generate all charts and return the list of file paths."""
    files: list[str] = []

    files.extend(chart_version_grouped_bar(version_df, output_dir))
    files.extend(chart_version_box_plot(raw_df, output_dir, gpt_model))
    files.extend(chart_version_heatmap(version_df, output_dir))
    files.extend(chart_model_grouped_bar(model_df, output_dir))
    files.extend(chart_model_radar(model_df, output_dir))
    files.extend(chart_model_heatmap(model_df, output_dir))
    if agg_df is not None and not agg_df.empty:
        files.extend(chart_combined_heatmap(agg_df, output_dir))

    logger.info("Generated %d chart files in %s", len(files), output_dir)
    return files
