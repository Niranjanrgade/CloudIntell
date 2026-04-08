"""LLM-as-Judge evaluation metric.

Uses a fixed judge model (GPT-4o by default) to score generated architectures
on six domain-specific dimensions.  The judge is independent from the models
being tested to avoid self-evaluation bias.

The six scoring dimensions are aligned with the AWS Well-Architected Framework
pillars and cloud architecture best practices, making the evaluation
academically defensible.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass

from pydantic import BaseModel, Field

from cloudy_intell.infrastructure.llm_factory import get_llm

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """\
You are an expert cloud architecture evaluator for academic research. You will \
be given a problem statement, a reference architecture (ground truth from \
official documentation), and a generated architecture produced by an AI system.

Score the generated architecture on each dimension below using an integer \
from 1 (very poor) to 10 (excellent). Be strict and consistent.

**Scoring Dimensions:**
1. **Completeness** — Does the architecture cover all required components \
   across compute, network, storage, and database domains?
2. **Technical Accuracy** — Are service names, configurations, and \
   integration patterns correct?
3. **Security** — Are security measures (IAM, encryption, network isolation, \
   audit logging) properly addressed?
4. **Scalability** — Does the design handle scaling (auto-scaling, load \
   balancing, caching, multi-AZ)?
5. **Best Practices Alignment** — How well does it align with the \
   Well-Architected Framework pillars?
6. **Specificity** — Does it name concrete services and configurations \
   rather than giving generic advice?

Respond with valid JSON matching this exact schema:
{{
  "completeness": <int 1-10>,
  "technical_accuracy": <int 1-10>,
  "security": <int 1-10>,
  "scalability": <int 1-10>,
  "best_practices": <int 1-10>,
  "specificity": <int 1-10>,
  "total_score": <float — average of the 6 dimensions>,
  "reasoning": "<2-3 sentence justification for the scores>"
}}\
"""

JUDGE_USER_TEMPLATE = """\
## Problem Statement
{problem}

## Reference Architecture (Ground Truth)
{reference}

## Generated Architecture (To Evaluate)
{generated}\
"""


class JudgeScores(BaseModel):
    """Structured output from the LLM judge."""

    completeness: int = Field(ge=1, le=10)
    technical_accuracy: int = Field(ge=1, le=10)
    security: int = Field(ge=1, le=10)
    scalability: int = Field(ge=1, le=10)
    best_practices: int = Field(ge=1, le=10)
    specificity: int = Field(ge=1, le=10)
    total_score: float = Field(ge=1.0, le=10.0)
    reasoning: str = ""


@dataclass(frozen=True)
class JudgeResult:
    """Full judge evaluation result."""

    completeness: int
    technical_accuracy: int
    security: int
    scalability: int
    best_practices: int
    specificity: int
    total_score: float
    reasoning: str

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_with_judge(
    generated: str,
    reference: str,
    problem: str,
    judge_model: str = "gpt-4o",
) -> JudgeResult:
    """Score a generated architecture using an independent LLM judge.

    Args:
        generated: The system-generated architecture text.
        reference: The ground-truth reference architecture text.
        problem: The original problem statement for context.
        judge_model: Model to use as the judge (should not be one of
            the models under test).

    Returns:
        A ``JudgeResult`` with scores for each dimension.
    """
    llm = get_llm(judge_model)

    user_prompt = JUDGE_USER_TEMPLATE.format(
        problem=problem,
        reference=reference,
        generated=generated,
    )

    response = llm.invoke([
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])

    raw = response.content if hasattr(response, "content") else response
    content = raw if isinstance(raw, str) else str(raw)

    # Parse JSON from response, handling potential markdown code fences
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    try:
        scores = JudgeScores.model_validate_json(content)
    except Exception:
        # Fallback: try parsing as dict
        try:
            data = json.loads(content)
            scores = JudgeScores(**data)
        except Exception as e:
            logger.error("Failed to parse judge response: %s\nContent: %s", e, content[:500])
            raise ValueError(f"Judge response parsing failed: {e}") from e

    # Recompute total_score as the actual average for consistency
    dims = [
        scores.completeness,
        scores.technical_accuracy,
        scores.security,
        scores.scalability,
        scores.best_practices,
        scores.specificity,
    ]
    computed_total = sum(dims) / len(dims)

    result = JudgeResult(
        completeness=scores.completeness,
        technical_accuracy=scores.technical_accuracy,
        security=scores.security,
        scalability=scores.scalability,
        best_practices=scores.best_practices,
        specificity=scores.specificity,
        total_score=round(computed_total, 2),
        reasoning=scores.reasoning,
    )

    logger.debug(
        "Judge scores: total=%.2f comp=%d acc=%d sec=%d scal=%d bp=%d spec=%d",
        result.total_score, result.completeness, result.technical_accuracy,
        result.security, result.scalability, result.best_practices, result.specificity,
    )
    return result
