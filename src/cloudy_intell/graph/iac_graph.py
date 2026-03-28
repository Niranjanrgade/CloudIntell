"""IaC generation graph builder.

Assembles a standalone LangGraph ``StateGraph`` for Infrastructure as Code
generation.  This graph is registered separately from the main architecture
graph and invoked on-demand after the user views the architecture report.

Graph topology:

    START
      │
      ▼
    iac_supervisor   (validates format, passes architecture through)
      │
      ├─→ compute_iac_generator  ──┐
      ├─→ network_iac_generator  ──┼─→ iac_synthesizer → END
      ├─→ storage_iac_generator  ──┤
      └─→ database_iac_generator ──┘

The four domain generators run in parallel (same fan-out/fan-in pattern
as the architect and validator subgraphs), each producing IaC code for
its domain.  The synthesizer merges them into a single cohesive document.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.agents.iac_generators import (
    compute_iac_generator,
    database_iac_generator,
    iac_supervisor,
    iac_synthesizer,
    network_iac_generator,
    storage_iac_generator,
)
from cloudy_intell.schemas.models import State

__all__ = ["build_iac_graph"]


def build_iac_graph(ctx: RuntimeContext, checkpointer: Any | None = None):
    """Build and compile the IaC generation graph.

    Args:
        ctx: Runtime context containing LLMs, tools, settings, and provider
             metadata.  The provider's ``supported_iac_formats`` and
             ``iac_resource_hints`` are consumed by the domain generators.
        checkpointer: Optional LangGraph checkpointer for state persistence.
                      When None the graph runs without checkpointing (used by
                      ``langgraph dev``).

    Returns:
        A compiled LangGraph ``CompiledGraph`` ready to be invoked with an
        initial state containing ``architecture_input`` and ``iac_format``.
    """

    graph_builder = StateGraph(State)

    # ── Nodes ────────────────────────────────────────────────────────────
    graph_builder.add_node("iac_supervisor", iac_supervisor(ctx))
    graph_builder.add_node("compute_iac_generator", compute_iac_generator(ctx))
    graph_builder.add_node("network_iac_generator", network_iac_generator(ctx))
    graph_builder.add_node("storage_iac_generator", storage_iac_generator(ctx))
    graph_builder.add_node("database_iac_generator", database_iac_generator(ctx))
    graph_builder.add_node("iac_synthesizer", iac_synthesizer(ctx))

    # ── Edges ────────────────────────────────────────────────────────────
    graph_builder.add_edge(START, "iac_supervisor")

    # Fan-out: supervisor → 4 parallel domain generators
    graph_builder.add_edge("iac_supervisor", "compute_iac_generator")
    graph_builder.add_edge("iac_supervisor", "network_iac_generator")
    graph_builder.add_edge("iac_supervisor", "storage_iac_generator")
    graph_builder.add_edge("iac_supervisor", "database_iac_generator")

    # Fan-in: all generators → synthesizer
    graph_builder.add_edge("compute_iac_generator", "iac_synthesizer")
    graph_builder.add_edge("network_iac_generator", "iac_synthesizer")
    graph_builder.add_edge("storage_iac_generator", "iac_synthesizer")
    graph_builder.add_edge("database_iac_generator", "iac_synthesizer")

    graph_builder.add_edge("iac_synthesizer", END)

    if checkpointer is None:
        return graph_builder.compile()
    return graph_builder.compile(checkpointer=checkpointer)
