"""Version 2 — Agentic runner: architect phase only (no validation loop).

This runner builds a minimal graph that executes the architect subgraph
(supervisor → 4 parallel domain architects → synthesizer) in a single pass
with no validator phase and no iteration.  It demonstrates the value of
multi-agent decomposition and tool use without the iterative refinement.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.config.provider_meta import PROVIDER_REGISTRY
from cloudy_intell.config.settings import get_settings
from cloudy_intell.graph.subgraphs import build_architect_subgraph
from cloudy_intell.infrastructure.llm_factory import get_llm
from cloudy_intell.infrastructure.tools import create_tool_bundle, rebind_tools
from cloudy_intell.infrastructure.vector_store import create_vector_store
from cloudy_intell.schemas.models import State

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgenticResult:
    """Output from an agentic (architect-only) run."""

    output: str
    model: str
    elapsed_seconds: float
    iteration_count: int


def _build_runtime_context(model_name: str, provider: str) -> RuntimeContext:
    """Build a RuntimeContext with both LLMs set to *model_name*."""
    settings = get_settings()
    provider_meta = PROVIDER_REGISTRY[provider]  # type: ignore[index]

    llm = get_llm(model_name)
    vector_store = create_vector_store(settings, provider)
    tool_bundle = create_tool_bundle(llm, vector_store, provider_meta, settings)  # type: ignore[arg-type]

    return RuntimeContext(
        settings=settings,
        mini_llm=llm,  # type: ignore[arg-type]
        reasoning_llm=llm,  # type: ignore[arg-type]
        tools=tool_bundle,
        provider=provider_meta,
    )


def run_agentic(
    problem: str,
    model_name: str,
    provider: str = "aws",
) -> AgenticResult:
    """Run the architect subgraph once — no validation, no iteration.

    Args:
        problem: The user problem statement.
        model_name: LLM model identifier (e.g. ``"gpt-5.4"``).
        provider: Cloud provider name (``"aws"`` or ``"azure"``).

    Returns:
        An ``AgenticResult`` with the synthesized architecture text.
    """
    ctx = _build_runtime_context(model_name, provider)

    # Build a minimal graph: START → architect_phase → END
    sg = StateGraph(State)
    sg.add_node("architect_phase", build_architect_subgraph(ctx).compile())
    sg.add_edge(START, "architect_phase")
    sg.add_edge("architect_phase", END)
    graph = sg.compile()

    initial_state = {
        "messages": [HumanMessage(content=problem)],
        "user_problem": problem,
        "iteration_count": 0,
        "min_iterations": 1,
        "max_iterations": 1,
        "architecture_domain_tasks": {},
        "architecture_components": {},
        "proposed_architecture": {},
        "validation_feedback": [],
        "validation_summary": None,
        "audit_feedback": [],
        "factual_errors_exist": False,
        "design_flaws_exist": False,
        "final_architecture": None,
        "architecture_summary": None,
        "aws_architecture_summary": None,
        "azure_architecture_summary": None,
        "debate_rounds": [],
        "current_debate_round": 0,
        "max_debate_rounds": 0,
        "debate_summary": None,
        "reasoning_model": model_name,
        "execution_model": model_name,
        "iac_format": None,
        "architecture_input": None,
        "iac_domain_code": {},
        "iac_output": None,
    }

    logger.info("Agentic run: model=%s provider=%s", model_name, provider)
    start = time.perf_counter()

    final_state = graph.invoke(initial_state)  # type: ignore[arg-type]

    elapsed = time.perf_counter() - start

    # Extract the synthesized architecture text
    proposed = final_state.get("proposed_architecture", {})
    output = proposed.get("architecture_summary", "")
    if not output:
        # Fallback: concatenate component recommendations
        components = final_state.get("architecture_components", {})
        parts = []
        for domain, comp in sorted(components.items()):
            if isinstance(comp, dict):
                parts.append(comp.get("recommendations", str(comp)))
            else:
                parts.append(str(comp))
        output = "\n\n".join(parts)

    logger.info("Agentic run complete: %.1fs, %d chars", elapsed, len(output))

    return AgenticResult(
        output=output,
        model=model_name,
        elapsed_seconds=elapsed,
        iteration_count=final_state.get("iteration_count", 1),
    )
