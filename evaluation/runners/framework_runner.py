"""Version 3 — Framework runner: full architect → validator → iterate pipeline.

This runner uses the complete ``build_graph`` pipeline with iteration
(architect_phase → validator_phase → conditional routing → final output).
Both reasoning and execution models are set to the same model for fair
cross-model comparison.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.config.provider_meta import PROVIDER_REGISTRY
from cloudy_intell.config.settings import get_settings
from cloudy_intell.graph.builder import build_graph
from cloudy_intell.graph.state_init import create_initial_state
from cloudy_intell.infrastructure.llm_factory import get_llm
from cloudy_intell.infrastructure.tools import create_tool_bundle
from cloudy_intell.infrastructure.vector_store import create_vector_store

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrameworkResult:
    """Output from a full framework run."""

    output: str
    model: str
    elapsed_seconds: float
    iteration_count: int


def run_framework(
    problem: str,
    model_name: str,
    provider: str = "aws",
    min_iterations: int = 1,
    max_iterations: int = 3,
) -> FrameworkResult:
    """Run the full architect → validator → iterate pipeline.

    Args:
        problem: The user problem statement.
        model_name: LLM model identifier — used for *both* reasoning and
            execution tiers to ensure fair cross-model comparison.
        provider: Cloud provider name (``"aws"`` or ``"azure"``).
        min_iterations: Minimum architect-validate cycles.
        max_iterations: Maximum cycles.

    Returns:
        A ``FrameworkResult`` with the final architecture summary text.
    """
    settings = get_settings()
    provider_meta = PROVIDER_REGISTRY[provider]  # type: ignore[index]

    llm = get_llm(model_name)
    vector_store = create_vector_store(settings, provider)
    tool_bundle = create_tool_bundle(llm, vector_store, provider_meta, settings)  # type: ignore[arg-type]

    ctx = RuntimeContext(
        settings=settings,
        mini_llm=llm,  # type: ignore[arg-type]
        reasoning_llm=llm,  # type: ignore[arg-type]
        tools=tool_bundle,
        provider=provider_meta,
    )

    graph = build_graph(ctx)

    initial_state = create_initial_state(
        user_problem=problem,
        min_iterations=min_iterations,
        max_iterations=max_iterations,
        reasoning_model=model_name,
        execution_model=model_name,
    )

    logger.info(
        "Framework run: model=%s provider=%s iterations=%d-%d",
        model_name, provider, min_iterations, max_iterations,
    )
    start = time.perf_counter()

    final_state = graph.invoke(initial_state)

    elapsed = time.perf_counter() - start

    output = final_state.get("architecture_summary", "") or ""
    if not output:
        final_arch = final_state.get("final_architecture")
        if isinstance(final_arch, dict):
            output = final_arch.get("document", str(final_arch))

    logger.info(
        "Framework run complete: %.1fs, %d chars, %d iterations",
        elapsed, len(output), final_state.get("iteration_count", 0),
    )

    return FrameworkResult(
        output=output,
        model=model_name,
        elapsed_seconds=elapsed,
        iteration_count=final_state.get("iteration_count", 0),
    )
