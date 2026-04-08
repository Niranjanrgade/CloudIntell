"""LaTeX table generation for thesis results.

Generates publication-ready LaTeX tables using ``booktabs`` style,
suitable for direct inclusion in a thesis document.

Tables are organized by experiment:
  - Experiment 1 (Version Comparison): Tables 1-2
  - Experiment 2 (Model Comparison): Tables 3-5
  - Appendix: Table 6 (per-scenario detail)
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Display-friendly labels
VERSION_LABELS: dict[str, str] = {"baseline": "Baseline", "agentic": "Agentic", "framework": "Framework"}
MODEL_LABELS: dict[str, str] = {
    "gpt-5.4": "GPT-5.4",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro",
}
METRIC_LABELS: dict[str, str] = {
    "meteor": "METEOR",
    "bert_score_f1": "BERTScore F1",
    "judge_total": "Judge Total",
}


def _label_for_model(model: str) -> str:
    return MODEL_LABELS.get(model) or model


def _fmt(mean: float | None, std: float | None) -> str:
    """Format a mean ± std cell value."""
    if mean is None:
        return "—"
    if std is not None and std > 0:
        return f"{mean:.3f} $\\pm$ {std:.3f}"
    return f"{mean:.3f}"


def _begin_table(caption: str, label: str, col_spec: str) -> str:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        f"\\begin{{tabular}}{{{col_spec}}}",
        r"\toprule",
    ]
    return "\n".join(lines)


def _end_table() -> str:
    return "\n".join([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])


def generate_version_comparison_tables(
    version_df: pd.DataFrame,
    output_dir: str,
) -> list[str]:
    """Table 1: Per-metric version comparison (GPT only).

    One table per metric with rows = scenarios, columns = versions.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    files = []

    metrics = ["meteor", "bert_score_f1", "judge_total"]
    versions = ["baseline", "agentic", "framework"]

    for metric in metrics:
        metric_label = METRIC_LABELS.get(metric, metric)
        mean_col = f"{metric}_mean"
        std_col = f"{metric}_std"

        if mean_col not in version_df.columns:
            continue

        scenarios = sorted(version_df["scenario"].unique())
        col_spec = "l" + "c" * len(versions)
        header_cols = " & ".join(VERSION_LABELS.get(v, v) for v in versions)

        lines = [
            _begin_table(
                caption=f"Version Comparison — {metric_label} (GPT-5.4)",
                label=f"tab:version_{metric}",
                col_spec=col_spec,
            ),
            f"Scenario & {header_cols} \\\\",
            r"\midrule",
        ]

        for scenario in scenarios:
            cells = [scenario.replace("_", r"\_")]
            for version in versions:
                row = version_df[
                    (version_df["scenario"] == scenario)
                    & (version_df["version"] == version)
                ]
                if len(row) == 0:
                    cells.append("—")
                else:
                    cells.append(_fmt(
                        row[mean_col].iloc[0],
                        row[std_col].iloc[0] if std_col in row.columns else None,
                    ))
            lines.append(" & ".join(cells) + r" \\")

        lines.append(_end_table())
        tex = "\n".join(lines)

        fpath = output_path / f"table_version_{metric}.tex"
        fpath.write_text(tex)
        files.append(str(fpath))
        logger.info("Wrote %s", fpath)

    return files


def generate_version_summary_table(
    version_df: pd.DataFrame,
    output_dir: str,
) -> str:
    """Table 2: Version comparison summary aggregated across scenarios."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    metrics = ["meteor", "bert_score_f1", "judge_total"]
    versions = ["baseline", "agentic", "framework"]

    col_spec = "l" + "c" * len(versions)
    header_cols = " & ".join(VERSION_LABELS.get(v, v) for v in versions)

    lines = [
        _begin_table(
            caption="Version Comparison Summary (GPT-5.4, Aggregated Across Scenarios)",
            label="tab:version_summary",
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
                cells.append(_fmt(m, s))
        lines.append(" & ".join(cells) + r" \\")

    lines.append(_end_table())
    tex = "\n".join(lines)

    fpath = output_path / "table_version_summary.tex"
    fpath.write_text(tex)
    logger.info("Wrote %s", fpath)
    return str(fpath)


def generate_model_comparison_tables(
    model_df: pd.DataFrame,
    output_dir: str,
) -> list[str]:
    """Table 3: Per-metric model comparison (Framework only).

    One table per metric with rows = scenarios, columns = models.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    files = []

    metrics = ["meteor", "bert_score_f1", "judge_total"]
    models = sorted(model_df["model"].unique())

    for metric in metrics:
        metric_label = METRIC_LABELS.get(metric, metric)
        mean_col = f"{metric}_mean"
        std_col = f"{metric}_std"

        if mean_col not in model_df.columns:
            continue

        scenarios = sorted(model_df["scenario"].unique())
        col_spec = "l" + "c" * len(models)
        header_cols = " & ".join(_label_for_model(m) for m in models)

        lines = [
            _begin_table(
                caption=f"Model Comparison — {metric_label} (Framework)",
                label=f"tab:model_{metric}",
                col_spec=col_spec,
            ),
            f"Scenario & {header_cols} \\\\",
            r"\midrule",
        ]

        for scenario in scenarios:
            cells = [scenario.replace("_", r"\_")]
            for model in models:
                row = model_df[
                    (model_df["scenario"] == scenario) & (model_df["model"] == model)
                ]
                if len(row) == 0:
                    cells.append("—")
                else:
                    cells.append(_fmt(
                        row[mean_col].iloc[0],
                        row[std_col].iloc[0] if std_col in row.columns else None,
                    ))
            lines.append(" & ".join(cells) + r" \\")

        lines.append(_end_table())
        tex = "\n".join(lines)

        fpath = output_path / f"table_model_{metric}.tex"
        fpath.write_text(tex)
        files.append(str(fpath))
        logger.info("Wrote %s", fpath)

    return files


def generate_model_summary_table(
    model_df: pd.DataFrame,
    output_dir: str,
) -> str:
    """Table 4: Model comparison summary aggregated across scenarios."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    metrics = ["meteor", "bert_score_f1", "judge_total"]
    models = sorted(model_df["model"].unique())

    col_spec = "l" + "c" * len(models)
    header_cols = " & ".join(_label_for_model(m) for m in models)

    lines = [
        _begin_table(
            caption="Model Comparison Summary (Framework, Aggregated Across Scenarios)",
            label="tab:model_summary",
            col_spec=col_spec,
        ),
        f"Metric & {header_cols} \\\\",
        r"\midrule",
    ]

    for metric in metrics:
        mean_col = f"{metric}_mean"
        if mean_col not in model_df.columns:
            continue

        cells = [METRIC_LABELS.get(metric, metric)]
        for model in models:
            subset = model_df[model_df["model"] == model]
            if len(subset) == 0:
                cells.append("—")
            else:
                m = subset[mean_col].mean()
                s = subset[mean_col].std()
                cells.append(_fmt(m, s))
        lines.append(" & ".join(cells) + r" \\")

    lines.append(_end_table())
    tex = "\n".join(lines)

    fpath = output_path / "table_model_summary.tex"
    fpath.write_text(tex)
    logger.info("Wrote %s", fpath)
    return str(fpath)


def generate_judge_breakdown_table(
    model_df: pd.DataFrame,
    output_dir: str,
) -> str:
    """Table 5: LLM Judge dimension breakdown by model (Framework only)."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    dims = [
        ("judge_completeness", "Comp."),
        ("judge_technical_accuracy", "Accuracy"),
        ("judge_security", "Security"),
        ("judge_scalability", "Scalab."),
        ("judge_best_practices", "Best Pr."),
        ("judge_specificity", "Specif."),
        ("judge_total", "Total"),
    ]
    models = sorted(model_df["model"].unique())

    col_spec = "l" + "c" * len(dims)
    header_cols = " & ".join(label for _, label in dims)

    lines = [
        _begin_table(
            caption="LLM Judge Dimension Breakdown by Model (Framework)",
            label="tab:judge_breakdown",
            col_spec=col_spec,
        ),
        f"Model & {header_cols} \\\\",
        r"\midrule",
    ]

    for model in models:
        subset = model_df[model_df["model"] == model]
        cells: list[str] = [_label_for_model(model)]
        for dim_key, _ in dims:
            mean_col = f"{dim_key}_mean"
            std_col = f"{dim_key}_std"
            if mean_col in subset.columns and len(subset) > 0:
                m = subset[mean_col].mean()
                s = subset[mean_col].std() if len(subset) > 1 else 0.0
                cells.append(_fmt(m, s))
            else:
                cells.append("—")
        lines.append(" & ".join(cells) + r" \\")

    lines.append(_end_table())
    tex = "\n".join(lines)

    fpath = output_path / "table_judge_breakdown.tex"
    fpath.write_text(tex)
    logger.info("Wrote %s", fpath)
    return str(fpath)


def generate_all_tables(
    version_df: pd.DataFrame,
    model_df: pd.DataFrame,
    output_dir: str,
) -> list[str]:
    """Generate all LaTeX tables and return the list of file paths."""
    files: list[str] = []

    files.extend(generate_version_comparison_tables(version_df, output_dir))
    files.append(generate_version_summary_table(version_df, output_dir))
    files.extend(generate_model_comparison_tables(model_df, output_dir))
    files.append(generate_model_summary_table(model_df, output_dir))
    files.append(generate_judge_breakdown_table(model_df, output_dir))

    logger.info("Generated %d LaTeX tables in %s", len(files), output_dir)
    return files
