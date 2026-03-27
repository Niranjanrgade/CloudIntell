"""LangGraph dev/studio entrypoint.

This module exposes compiled graph objects so ``langgraph dev`` can discover
and run workflows directly from repository configuration.

When you run ``langgraph dev``, the LangGraph CLI reads ``langgraph.json``
which points to this module's ``graph`` (AWS) and ``azure_graph`` (Azure)
symbols.  Each graph is built with the correct provider metadata, vector
store, and tool bundle so that provider selection is fully determined at
graph level.

Unlike the CLI/service entrypoint, this module does NOT create a checkpointer
because the LangGraph dev server manages persistence automatically.
"""

from dotenv import load_dotenv

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.config.provider_meta import get_provider_meta
from cloudy_intell.config.settings import get_settings
from cloudy_intell.graph.builder import build_graph
from cloudy_intell.graph.debate_graph import build_debate_graph
from cloudy_intell.infrastructure.llm_factory import create_execution_llm, create_reasoning_llm
from cloudy_intell.infrastructure.logging_utils import configure_logging
from cloudy_intell.infrastructure.tools import create_tool_bundle
from cloudy_intell.infrastructure.vector_store import create_vector_store
from cloudy_intell.services.architecture_service import configure_langsmith_environment


def _init_shared():
    """One-time shared setup (settings, LLMs, logging)."""
    load_dotenv(override=False)
    settings = get_settings()
    configure_langsmith_environment(settings)
    configure_logging(settings.log_level)
    mini_llm = create_execution_llm(settings)
    reasoning_llm = create_reasoning_llm(settings)
    return settings, mini_llm, reasoning_llm


def _build_provider_graph(settings, mini_llm, reasoning_llm, provider_name):
    """Build a compiled graph for the given cloud provider.

    Returns a (RuntimeContext, compiled_graph) tuple so the context can be
    reused by the debate graph which needs both provider contexts.
    """
    meta = get_provider_meta(provider_name)
    vector_store = create_vector_store(settings, provider=provider_name)
    tools = create_tool_bundle(mini_llm, vector_store, provider_meta=meta)

    ctx = RuntimeContext(
        settings=settings,
        mini_llm=mini_llm,
        reasoning_llm=reasoning_llm,
        tools=tools,
        provider=meta,
    )
    # LangGraph API dev mode manages persistence automatically.
    return ctx, build_graph(ctx)


# LangGraph CLI loads these symbols from langgraph.json.
_settings, _mini_llm, _reasoning_llm = _init_shared()

_aws_ctx, graph = _build_provider_graph(_settings, _mini_llm, _reasoning_llm, "aws")
_azure_ctx, azure_graph = _build_provider_graph(_settings, _mini_llm, _reasoning_llm, "azure")

# Debate graph uses both provider contexts for advocate tool access.
debate_graph = build_debate_graph(_aws_ctx, _azure_ctx)
