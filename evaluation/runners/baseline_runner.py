"""Version 1 — Baseline runner: single LLM call with no agents or tools.

This runner makes a single prompt call to the specified LLM and returns
the raw text response.  It represents the simplest possible approach:
a human would get the same output by pasting the problem into ChatGPT.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from cloudy_intell.infrastructure.llm_factory import get_llm

logger = logging.getLogger(__name__)

BASELINE_SYSTEM_PROMPT = """\
You are a {provider_display} Principal Solutions Architect with deep expertise \
in cloud infrastructure design. You must produce a comprehensive, production-ready \
cloud architecture document.

Your response MUST include:
1. **Executive Summary** — A concise overview of the proposed architecture.
2. **Architecture Overview** — High-level description of the solution and how \
   components interact.
3. **Component Details** — For each domain (compute, network, storage, database), \
   list the specific {provider_display} services chosen, their configuration, and \
   justification.
4. **Security & Compliance** — Encryption, IAM, network isolation, and audit logging.
5. **Scalability & High Availability** — Auto-scaling, multi-AZ, failover strategies.
6. **Deployment Guidance** — Recommended deployment approach and operational \
   considerations.

Use specific service names, concrete configuration values, and cite best practices \
from official {provider_display} documentation where relevant.\
"""


@dataclass(frozen=True)
class BaselineResult:
    """Output from a baseline run."""

    output: str
    model: str
    elapsed_seconds: float


def run_baseline(
    problem: str,
    model_name: str,
    provider: str = "aws",
) -> BaselineResult:
    """Run a single LLM call with no agents, tools, or iteration.

    Args:
        problem: The user problem statement.
        model_name: LLM model identifier (e.g. ``"gpt-5.4"``).
        provider: Cloud provider name for prompt context.

    Returns:
        A ``BaselineResult`` with the raw LLM output text, model name,
        and wall-clock elapsed time in seconds.
    """
    provider_display = "AWS" if provider == "aws" else "Azure"
    system_prompt = BASELINE_SYSTEM_PROMPT.format(provider_display=provider_display)

    llm = get_llm(model_name)

    logger.info("Baseline run: model=%s provider=%s", model_name, provider)
    start = time.perf_counter()

    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": problem},
    ])

    elapsed = time.perf_counter() - start
    raw = response.content if hasattr(response, "content") else response
    output = raw if isinstance(raw, str) else str(raw)
    logger.info("Baseline run complete: %.1fs, %d chars", elapsed, len(output))

    return BaselineResult(output=output, model=model_name, elapsed_seconds=elapsed)
