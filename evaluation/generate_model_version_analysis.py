"""Generate version-comparison tables and charts for Claude and Gemini.

This script mirrors the GPT-5.4 version-comparison outputs (Experiment 1)
for Claude Sonnet 4.6 and Gemini 3.1 Pro Preview.

Outputs:
  evaluation/results/tables/
    table_version_meteor_claude.tex
    table_version_bert_score_f1_claude.tex
    table_version_judge_total_claude.tex
    table_version_summary_claude.tex
    table_version_meteor_gemini.tex
    table_version_bert_score_f1_gemini.tex
    table_version_judge_total_gemini.tex
    table_version_summary_gemini.tex
    table_version_judge_breakdown_claude.tex
    table_version_judge_breakdown_gemini.tex

  evaluation/results/charts/
    chart_version_grouped_bar_claude.{pdf,png}
    chart_version_heatmap_claude.{pdf,png}
    chart_version_boxplot_claude.{pdf,png}
    chart_version_grouped_bar_gemini.{pdf,png}
    chart_version_heatmap_gemini.{pdf,png}
    chart_version_boxplot_gemini.{pdf,png}

Usage (from repo root):
    python -m evaluation.generate_model_version_analysis
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.figure import Figure

matplotlib.use("Agg")

# ── add repo root to path so sibling imports work ─────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.analysis.aggregator import aggregate_by_config, load_all_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

RESULTS_DIR = Path(__file__).parent / "results"
TABLES_DIR = RESULTS_DIR / "tables"
CHARTS_DIR = RESULTS_DIR / "charts"

MODELS = {
    "claude-sonnet-4-6": ("Claude Sonnet 4.6", "claude"),
    "gemini-3.1-pro-preview": ("Gemini 3.1 Pro", "gemini"),
}

VERSION_LABELS = {
    "baseline": "Single Prompt LLM",
    "agentic": "Agentic Framework",
    "framework": "Evaluator Optimiser Loop Framework",
}
VERSION_ORDER = ["baseline", "agentic", "framework"]

METRIC_LABELS = {
    "meteor": "METEOR",
    "bert_score_f1": "BERTScore F1",
    "judge_total": "Judge Total",
}

PALETTE_VERSIONS = ["#2196F3", "#FF9800", "#4CAF50"]

plt.rcParams.update(
    {
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
    }
)


# ── Helpers ───────────────────────────────────────────────────────────────


def _save(fig: Figure, name: str) -> list[str]:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for ext in ("pdf", "png"):
        p = CHARTS_DIR / f"{name}.{ext}"
        fig.savefig(str(p))
        paths.append(str(p))
    plt.close(fig)
    logger.info("Saved chart: %s", name)
    return paths


def _fmt(mean: float | None, std: float | None) -> str:
    if mean is None:
        return "—"
    if std is not None and std > 0:
        return f"{mean:.3f} $\\pm$ {std:.3f}"
    return f"{mean:.3f}"


def _begin_table(caption: str, label: str, col_spec: str) -> str:
    return "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            f"\\caption{{{caption}}}",
            f"\\label{{{label}}}",
            f"\\begin{{tabular}}{{{col_spec}}}",
            r"\toprule",
        ]
    )


def _end_table() -> str:
    return "\n".join([r"\bottomrule", r"\end{tabular}", r"\end{table}"])


def _write_tex(content: str, path: Path) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    logger.info("Wrote %s", path)


# ── Table generators ──────────────────────────────────────────────────────


def generate_version_comparison_tables(
    version_df: pd.DataFrame,
    model_label: str,
    suffix: str,
) -> list[str]:
    """Per-metric version comparison table (one per metric)."""
    files: list[str] = []
    metrics = ["meteor", "bert_score_f1", "judge_total"]
    versions = [v for v in VERSION_ORDER if v in version_df["version"].values]
    scenarios = sorted(version_df["scenario"].unique())
    col_spec = "l" + "c" * len(versions)
    header_cols = " & ".join(VERSION_LABELS.get(v, v) for v in versions)

    for metric in metrics:
        metric_label = METRIC_LABELS.get(metric, metric)
        mean_col = f"{metric}_mean"
        std_col = f"{metric}_std"

        if mean_col not in version_df.columns:
            continue

        lines = [
            _begin_table(
                caption=f"Version Comparison — {metric_label} ({model_label})",
                label=f"tab:version_{metric}_{suffix}",
                col_spec=col_spec,
            ),
            f"Scenario & {header_cols} \\\\",
            r"\midrule",
        ]

        for scenario in scenarios:
            cells = [scenario.replace("_", r"\_")]
            for version in versions:
                row = version_df[
                    (version_df["scenario"] == scenario) & (version_df["version"] == version)
                ]
                if len(row) == 0:
                    cells.append("—")
                else:
                    cells.append(
                        _fmt(
                            row[mean_col].iloc[0],
                            row[std_col].iloc[0] if std_col in row.columns else None,
                        )
                    )
            lines.append(" & ".join(cells) + r" \\")

        lines.append(_end_table())
        tex = "\n".join(lines)
        fpath = TABLES_DIR / f"table_version_{metric}_{suffix}.tex"
        _write_tex(tex, fpath)
        files.append(str(fpath))

    return files


def generate_version_summary_table(
    version_df: pd.DataFrame,
    model_label: str,
    suffix: str,
) -> str:
    metrics = ["meteor", "bert_score_f1", "judge_total"]
    versions = [v for v in VERSION_ORDER if v in version_df["version"].values]
    col_spec = "l" + "c" * len(versions)
    header_cols = " & ".join(VERSION_LABELS.get(v, v) for v in versions)

    lines = [
        _begin_table(
            caption=f"Version Comparison Summary ({model_label}, Aggregated Across Scenarios)",
            label=f"tab:version_summary_{suffix}",
            col_spec=col_spec,
        ),
        f"Metric & {header_cols} \\\\",
        r"\midrule",
    ]

    for metric in metrics:
        mean_col = f"{metric}_mean"
        if mean_col not in version_df.columns:
            continue
        cells = [METRIC_LABELS.get(metric, metric)]
        for version in versions:
            subset = version_df[version_df["version"] == version]
            if len(subset) == 0:
                cells.append("—")
            else:
                m = subset[mean_col].mean()
                s = subset[mean_col].std()
                cells.append(_fmt(m, s if not np.isnan(s) else None))
        lines.append(" & ".join(cells) + r" \\")

    lines.append(_end_table())
    tex = "\n".join(lines)
    fpath = TABLES_DIR / f"table_version_summary_{suffix}.tex"
    _write_tex(tex, fpath)
    return str(fpath)


def generate_judge_breakdown_table(
    version_df: pd.DataFrame,
    model_label: str,
    suffix: str,
) -> str:
    """LLM Judge dimension breakdown by version for a single model."""
    dims = [
        ("judge_completeness", "Comp."),
        ("judge_technical_accuracy", "Accuracy"),
        ("judge_security", "Security"),
        ("judge_scalability", "Scalab."),
        ("judge_best_practices", "Best Pr."),
        ("judge_specificity", "Specif."),
        ("judge_total", "Total"),
    ]
    versions = [v for v in VERSION_ORDER if v in version_df["version"].values]
    col_spec = "l" + "c" * len(dims)
    header_cols = " & ".join(label for _, label in dims)

    lines = [
        _begin_table(
            caption=f"LLM Judge Dimension Breakdown by Version ({model_label})",
            label=f"tab:judge_breakdown_version_{suffix}",
            col_spec=col_spec,
        ),
        f"Version & {header_cols} \\\\",
        r"\midrule",
    ]

    for version in versions:
        subset = version_df[version_df["version"] == version]
        cells: list[str] = [VERSION_LABELS.get(version, version)]
        for dim_key, _ in dims:
            mean_col = f"{dim_key}_mean"
            std_col = f"{dim_key}_std"
            if mean_col in subset.columns and len(subset) > 0:
                m = subset[mean_col].mean()
                s = subset[mean_col].std() if len(subset) > 1 else 0.0
                cells.append(_fmt(m, s if not np.isnan(s) else None))
            else:
                cells.append("—")
        lines.append(" & ".join(cells) + r" \\")

    lines.append(_end_table())
    tex = "\n".join(lines)
    fpath = TABLES_DIR / f"table_version_judge_breakdown_{suffix}.tex"
    _write_tex(tex, fpath)
    return str(fpath)


# ── Chart generators ──────────────────────────────────────────────────────


def chart_version_grouped_bar(
    version_df: pd.DataFrame,
    model_label: str,
    suffix: str,
) -> list[str]:
    """Grouped bar chart — version comparison for a single model."""
    metrics = ["meteor", "bert_score_f1", "judge_total"]
    versions = [v for v in VERSION_ORDER if v in version_df["version"].values]

    data: list[dict] = []
    for version in versions:
        subset = version_df[version_df["version"] == version]
        for metric in metrics:
            mean_col = f"{metric}_mean"
            if mean_col in subset.columns:
                m = subset[mean_col].mean()
                s = float(subset[mean_col].std()) if len(subset) > 1 else 0.0
                if metric == "judge_total":
                    m, s = m / 10.0, s / 10.0
                data.append(
                    {
                        "Version": VERSION_LABELS.get(version, version),
                        "Metric": METRIC_LABELS[metric],
                        "Score": m,
                        "Std": s,
                    }
                )

    if not data:
        return []

    df = pd.DataFrame(data)
    metric_names = [METRIC_LABELS[m] for m in metrics]
    x = np.arange(len(metric_names))
    width = 0.25

    fig, ax = plt.subplots(figsize=(8, 5))
    for i, version in enumerate(versions):
        v_label = VERSION_LABELS[version]
        v_data = df[df["Version"] == v_label]
        means = [
            v_data[v_data["Metric"] == mn]["Score"].values[0]
            if len(v_data[v_data["Metric"] == mn]) > 0
            else 0
            for mn in metric_names
        ]
        stds = [
            v_data[v_data["Metric"] == mn]["Std"].values[0]
            if len(v_data[v_data["Metric"] == mn]) > 0
            else 0
            for mn in metric_names
        ]
        ax.bar(
            x + i * width,
            means,
            width,
            yerr=stds,
            label=v_label,
            color=PALETTE_VERSIONS[i],
            capsize=3,
            edgecolor="white",
            linewidth=0.5,
        )

    ax.set_xlabel("Metric")
    ax.set_ylabel("Score")
    ax.set_title(f"Version Comparison ({model_label})")
    ax.set_xticks(x + width)
    ax.set_xticklabels(metric_names)
    ax.legend()
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", alpha=0.3)

    return _save(fig, f"chart_version_grouped_bar_{suffix}")


def chart_version_boxplot(
    raw_df: pd.DataFrame,
    model_id: str,
    model_label: str,
    suffix: str,
) -> list[str]:
    """Box plot — BERTScore F1 distribution across versions for a single model."""
    subset = raw_df[raw_df["model"] == model_id].copy()
    if "bert_score_f1" not in subset.columns or subset["bert_score_f1"].isna().all():
        return []

    subset["Version"] = subset["version"].map(VERSION_LABELS)
    order = [VERSION_LABELS[v] for v in VERSION_ORDER if VERSION_LABELS[v] in subset["Version"].values]

    fig, ax = plt.subplots(figsize=(7, 5))
    sns.boxplot(
        data=subset,
        x="Version",
        y="bert_score_f1",
        order=order,
        palette=PALETTE_VERSIONS[: len(order)],
        ax=ax,
    )
    ax.set_xlabel("System Version")
    ax.set_ylabel("BERTScore F1")
    ax.set_title(f"BERTScore F1 Distribution by Version ({model_label})")
    ax.grid(axis="y", alpha=0.3)

    return _save(fig, f"chart_version_boxplot_{suffix}")


def chart_version_heatmap(
    version_df: pd.DataFrame,
    model_label: str,
    suffix: str,
) -> list[str]:
    """Heatmap — LLM Judge dimensions by version for a single model."""
    dims = [
        ("judge_completeness", "Completeness"),
        ("judge_technical_accuracy", "Accuracy"),
        ("judge_security", "Security"),
        ("judge_scalability", "Scalability"),
        ("judge_best_practices", "Best Practices"),
        ("judge_specificity", "Specificity"),
        ("judge_total", "Total"),
    ]
    versions = [v for v in VERSION_ORDER if v in version_df["version"].values]

    matrix: list[list[float]] = []
    row_labels: list[str] = []
    for version in versions:
        subset = version_df[version_df["version"] == version]
        row: list[float] = []
        for dk, _ in dims:
            mean_col = f"{dk}_mean"
            if mean_col in subset.columns:
                row.append(float(subset[mean_col].mean()))
            else:
                row.append(0.0)
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
            ax.text(j, i, fmt, ha="center", va="center", color=color, fontsize=13, fontweight=weight)

    fig.colorbar(im, ax=ax, label="Score (1-10)")
    ax.set_title(f"LLM Judge Dimension Scores by Version ({model_label})", fontsize=13)
    fig.tight_layout()

    return _save(fig, f"chart_version_heatmap_{suffix}")


# ── Combined (all 3 models) generators ───────────────────────────────────

ALL_MODEL_ORDER = [
    ("gpt-5.4", "GPT-5.4"),
    ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
    ("gemini-3.1-pro-preview", "Gemini 3.1 Pro"),
]
PALETTE_MODELS_3 = ["#2196F3", "#9C27B0", "#F44336"]


def generate_combined_version_summary_table(agg_df: pd.DataFrame) -> str:
    """Combined table: rows = metric, column groups = model × version (3×3 = 9 cols)."""
    metrics = ["meteor", "bert_score_f1", "judge_total"]
    versions = VERSION_ORDER

    # Build header: multicolumn groups per model
    model_headers = " & ".join(
        f"\\multicolumn{{3}}{{c}}{{{label}}}" for _, label in ALL_MODEL_ORDER
    )
    version_subheader = " & ".join(
        " & ".join(["SP", "AF", "EOL"]) for _ in ALL_MODEL_ORDER
    )
    n_cols = 1 + 3 * len(ALL_MODEL_ORDER)
    col_spec = "l" + "ccc" * len(ALL_MODEL_ORDER)

    cmidrule_parts = []
    for i, _ in enumerate(ALL_MODEL_ORDER):
        start = 2 + i * 3
        end = start + 2
        cmidrule_parts.append(f"\\cmidrule(lr){{{start}-{end}}}")
    cmidrule = " ".join(cmidrule_parts)

    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Version Comparison Summary — All Models (Aggregated Across Scenarios)}",
        r"\label{tab:version_summary_combined}",
        r"\small",
        f"\\begin{{tabular}}{{{col_spec}}}",
        r"\toprule",
        f"Metric & {model_headers} \\\\",
        cmidrule,
        f" & {version_subheader} \\\\",
        r"\midrule",
    ]

    for metric in metrics:
        mean_col = f"{metric}_mean"
        if mean_col not in agg_df.columns:
            continue
        cells = [METRIC_LABELS.get(metric, metric)]
        for model_id, _ in ALL_MODEL_ORDER:
            for version in versions:
                subset = agg_df[(agg_df["model"] == model_id) & (agg_df["version"] == version)]
                if len(subset) == 0:
                    cells.append("—")
                else:
                    cells.append(f"{subset[mean_col].mean():.3f}")
        lines.append(" & ".join(cells) + r" \\")

    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    tex = "\n".join(lines)

    fpath = TABLES_DIR / "table_version_summary_combined.tex"
    _write_tex(tex, fpath)
    return str(fpath)


def generate_combined_judge_breakdown_table(agg_df: pd.DataFrame) -> str:
    """Combined judge breakdown: rows = model × version, columns = judge dims."""
    dims = [
        ("judge_completeness", "Comp."),
        ("judge_technical_accuracy", "Accuracy"),
        ("judge_security", "Security"),
        ("judge_scalability", "Scalab."),
        ("judge_best_practices", "Best Pr."),
        ("judge_specificity", "Specif."),
        ("judge_total", "Total"),
    ]
    col_spec = "ll" + "c" * len(dims)
    header_cols = " & ".join(label for _, label in dims)

    lines = [
        _begin_table(
            caption="LLM Judge Dimension Breakdown — All Models by Version",
            label="tab:judge_breakdown_combined",
            col_spec=col_spec,
        ),
        f"Model & Version & {header_cols} \\\\",
        r"\midrule",
    ]

    for i, (model_id, model_label) in enumerate(ALL_MODEL_ORDER):
        if i > 0:
            lines.append(r"\midrule")
        for version in VERSION_ORDER:
            subset = agg_df[(agg_df["model"] == model_id) & (agg_df["version"] == version)]
            ver_label = VERSION_LABELS.get(version, version)
            # Shorten for table width
            short_ver = {"Single Prompt LLM": "SP LLM", "Agentic Framework": "Agentic", "Evaluator Optimiser Loop Framework": "EOL Framework"}
            cells: list[str] = [model_label if version == VERSION_ORDER[0] else "", short_ver.get(ver_label, ver_label)]
            for dk, _ in dims:
                mean_col = f"{dk}_mean"
                if mean_col in subset.columns and len(subset) > 0:
                    cells.append(f"{subset[mean_col].mean():.2f}")
                else:
                    cells.append("—")
            lines.append(" & ".join(cells) + r" \\")

    lines.append(_end_table())
    tex = "\n".join(lines)
    fpath = TABLES_DIR / "table_version_judge_breakdown_combined.tex"
    _write_tex(tex, fpath)
    return str(fpath)


def chart_combined_version_grouped_bar(agg_df: pd.DataFrame) -> list[str]:
    """Grouped bar: one group per metric, bars per model×version (9 bars per metric)."""
    metrics = ["meteor", "bert_score_f1", "judge_total"]
    metric_names = [METRIC_LABELS[m] for m in metrics]

    # Build one bar per (model, version) combo
    combos = [(mid, ml, v) for mid, ml in ALL_MODEL_ORDER for v in VERSION_ORDER]
    n_combos = len(combos)  # 9
    n_metrics = len(metrics)

    bar_values = np.zeros((n_combos, n_metrics))
    for ci, (model_id, _, version) in enumerate(combos):
        subset = agg_df[(agg_df["model"] == model_id) & (agg_df["version"] == version)]
        for mi, metric in enumerate(metrics):
            mean_col = f"{metric}_mean"
            if mean_col in subset.columns and len(subset) > 0:
                val = float(subset[mean_col].mean())
                bar_values[ci, mi] = val / 10.0 if metric == "judge_total" else val

    fig, ax = plt.subplots(figsize=(12, 5))
    x = np.arange(n_metrics)
    total_width = 0.8
    bar_w = total_width / n_combos

    # Color: shade by version, hue by model
    model_colors = PALETTE_MODELS_3
    version_alphas = [1.0, 0.65, 0.4]

    for ci, (model_id, model_label, version) in enumerate(combos):
        mi_idx = list(dict.fromkeys(m for _, m in ALL_MODEL_ORDER)).index(
            next(ml for mid, ml in ALL_MODEL_ORDER if mid == model_id)
        )
        color = model_colors[mi_idx]
        alpha = version_alphas[VERSION_ORDER.index(version)]
        offset = (ci - n_combos / 2 + 0.5) * bar_w
        ver_short = {"baseline": "SP", "agentic": "AF", "framework": "EOL"}[version]
        label = f"{model_label} ({ver_short})"
        ax.bar(x + offset, bar_values[ci], bar_w * 0.9,
               color=color, alpha=alpha, label=label, edgecolor="white", linewidth=0.3)

    ax.set_xlabel("Metric")
    ax.set_ylabel("Score (Judge normalised to 0–1)")
    ax.set_title("Version Comparison — All Models")
    ax.set_xticks(x)
    ax.set_xticklabels(metric_names)
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(loc="upper right", fontsize=7, ncol=3)

    return _save(fig, "chart_version_grouped_bar_combined")


def generate_version_avg_all_models_table(agg_df: pd.DataFrame) -> str:
    """3-row table: rows = version, columns = metrics, values = mean across all 3 models."""
    metrics = ["meteor", "bert_score_f1", "judge_total"]
    versions = VERSION_ORDER
    col_spec = "l" + "c" * len(metrics)
    header_cols = " & ".join(METRIC_LABELS.get(m, m) for m in metrics)

    lines = [
        _begin_table(
            caption="Version Comparison — Average Across All Models (GPT-5.4, Claude Sonnet 4.6, Gemini 3.1 Pro)",
            label="tab:version_avg_all_models",
            col_spec=col_spec,
        ),
        f"Version & {header_cols} \\\\",
        r"\midrule",
    ]

    for version in versions:
        subset = agg_df[agg_df["version"] == version]
        cells = [VERSION_LABELS.get(version, version)]
        for metric in metrics:
            mean_col = f"{metric}_mean"
            if mean_col in subset.columns and len(subset) > 0:
                avg = subset[mean_col].mean()
                std = subset[mean_col].std()
                cells.append(_fmt(avg, std if not np.isnan(std) else None))
            else:
                cells.append("—")
        lines.append(" & ".join(cells) + r" \\")

    lines.append(_end_table())
    tex = "\n".join(lines)
    fpath = TABLES_DIR / "table_version_avg_all_models.tex"
    _write_tex(tex, fpath)
    return str(fpath)


def chart_version_avg_all_models_bar(agg_df: pd.DataFrame) -> list[str]:
    """Grouped bar chart: 3 metric groups, one bar per version, values averaged across all models."""
    metrics = ["meteor", "bert_score_f1", "judge_total"]
    metric_names = [METRIC_LABELS[m] for m in metrics]
    versions = VERSION_ORDER

    means_grid = np.zeros((len(versions), len(metrics)))
    stds_grid = np.zeros((len(versions), len(metrics)))
    for vi, version in enumerate(versions):
        subset = agg_df[agg_df["version"] == version]
        for mi, metric in enumerate(metrics):
            mean_col = f"{metric}_mean"
            if mean_col in subset.columns and len(subset) > 0:
                val = float(subset[mean_col].mean())
                err = float(subset[mean_col].std())
                if metric == "judge_total":
                    val, err = val / 10.0, err / 10.0
                means_grid[vi, mi] = val
                stds_grid[vi, mi] = err if not np.isnan(err) else 0.0

    x = np.arange(len(metrics))
    width = 0.25
    fig, ax = plt.subplots(figsize=(8, 5))

    for vi, version in enumerate(versions):
        ax.bar(
            x + vi * width,
            means_grid[vi],
            width,
            yerr=stds_grid[vi],
            label=VERSION_LABELS[version],
            color=PALETTE_VERSIONS[vi],
            capsize=3,
            edgecolor="white",
            linewidth=0.5,
        )

    ax.set_xlabel("Metric")
    ax.set_ylabel("Score (Judge normalised to 0–1)")
    ax.set_title("Version Comparison — Average Across All Models")
    ax.set_xticks(x + width)
    ax.set_xticklabels(metric_names)
    ax.set_ylim(0, 1.1)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    return _save(fig, "chart_version_avg_all_models_bar")


def chart_combined_version_heatmap(agg_df: pd.DataFrame) -> list[str]:
    """Heatmap: rows = model × version, columns = judge dimensions."""
    dims = [
        ("judge_completeness", "Completeness"),
        ("judge_technical_accuracy", "Accuracy"),
        ("judge_security", "Security"),
        ("judge_scalability", "Scalability"),
        ("judge_best_practices", "Best Practices"),
        ("judge_specificity", "Specificity"),
        ("judge_total", "Total"),
    ]

    row_order = [(mid, v) for mid, _ in ALL_MODEL_ORDER for v in VERSION_ORDER]
    row_labels: list[str] = []
    matrix: list[list[float]] = []

    ver_short = {"baseline": "SP LLM", "agentic": "Agentic", "framework": "EOL"}
    model_map = dict(ALL_MODEL_ORDER)

    for model_id, version in row_order:
        subset = agg_df[(agg_df["model"] == model_id) & (agg_df["version"] == version)]
        row: list[float] = []
        for dk, _ in dims:
            mean_col = f"{dk}_mean"
            row.append(float(subset[mean_col].mean()) if mean_col in subset.columns and len(subset) > 0 else 0.0)
        matrix.append(row)
        row_labels.append(f"{model_map[model_id]} / {ver_short[version]}")

    matrix_np = np.array(matrix)
    col_labels = [d[1] for d in dims]

    fig, ax = plt.subplots(figsize=(11, 6))
    im = ax.imshow(matrix_np, cmap="YlGnBu", aspect="auto", vmin=1, vmax=10)

    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_yticks(np.arange(len(row_labels)))
    xlabels = ax.set_xticklabels(col_labels, rotation=45, ha="right")
    xlabels[-1].set_fontweight("bold")
    ax.set_yticklabels(row_labels)

    # Draw horizontal separator lines between model groups
    for sep in [2.5, 5.5]:
        ax.axhline(sep, color="white", linewidth=2)

    total_col_idx = len(col_labels) - 1
    for i in range(len(row_labels)):
        for j in range(len(col_labels)):
            val = matrix_np[i, j]
            color = "white" if val > 6.5 else "black"
            fmt = f"{val:.2f}" if j == total_col_idx else f"{val:.1f}"
            weight = "bold" if j == total_col_idx else "normal"
            ax.text(j, i, fmt, ha="center", va="center", color=color, fontsize=9, fontweight=weight)

    fig.colorbar(im, ax=ax, label="Score (1-10)")
    ax.set_title("LLM Judge Dimension Scores — All Models by Version")
    fig.tight_layout()

    return _save(fig, "chart_version_heatmap_combined")


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    raw_df = load_all_metrics(str(RESULTS_DIR))
    if raw_df.empty:
        logger.error("No metric records found in %s", RESULTS_DIR)
        sys.exit(1)

    agg_df = aggregate_by_config(raw_df)

    all_files: list[str] = []

    for model_id, (model_label, suffix) in MODELS.items():
        logger.info("=== Generating outputs for %s ===", model_label)

        version_df = agg_df[agg_df["model"] == model_id].copy()
        if version_df.empty:
            logger.warning("No aggregated data found for model %s — skipping.", model_id)
            continue

        # ── Tables ──
        all_files.extend(
            generate_version_comparison_tables(version_df, model_label, suffix)
        )
        all_files.append(
            generate_version_summary_table(version_df, model_label, suffix)
        )
        all_files.append(
            generate_judge_breakdown_table(version_df, model_label, suffix)
        )

        # ── Charts ──
        all_files.extend(chart_version_grouped_bar(version_df, model_label, suffix))
        all_files.extend(chart_version_boxplot(raw_df, model_id, model_label, suffix))
        all_files.extend(chart_version_heatmap(version_df, model_label, suffix))

    # ── Combined outputs (all 3 models) ──
    logger.info("=== Generating combined outputs (all 3 models) ===")
    all_files.append(generate_combined_version_summary_table(agg_df))
    all_files.append(generate_combined_judge_breakdown_table(agg_df))
    all_files.append(generate_version_avg_all_models_table(agg_df))
    all_files.extend(chart_version_avg_all_models_bar(agg_df))
    all_files.extend(chart_combined_version_grouped_bar(agg_df))
    all_files.extend(chart_combined_version_heatmap(agg_df))

    logger.info("Done. Generated %d files.", len(all_files))
    for f in all_files:
        print(f)


if __name__ == "__main__":
    main()
