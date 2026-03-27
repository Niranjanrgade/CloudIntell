"""Debate graph builder and routing condition.

This module constructs the debate graph — a post-generation phase that takes
completed AWS and Azure architecture summaries and orchestrates a multi-round
structured debate between provider advocates, concluded by a neutral judge.

Graph topology::

    START
      │
      ▼
    debate_setup  (increment round, prepare rebuttal context)
      │
      ├─→ aws_advocate ──────────┐
      │                          ├─→ debate_round_synthesizer  (fan-in)
      └─→ azure_advocate ────────┘
      │
      ▼
    [debate_round_condition]
      │ "continue" → debate_setup  (next round)
      │ "finish"   ↓
      ▼
    debate_judge  (neutral verdict)
      │
      ▼
    END

The graph requires **two** ``RuntimeContext`` instances (one per provider)
because each advocate needs access to its provider's tools (RAG + web search).
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.agents.debate_agents import (
    aws_advocate,
    azure_advocate,
    debate_judge,
    debate_round_synthesizer,
    debate_setup,
)
from cloudy_intell.schemas.models import State

__all__ = ["build_debate_graph"]


def debate_round_condition(state: dict) -> str:
    """Route after each debate round: continue or finish.

    Returns ``"continue"`` if the current round is below the maximum,
    otherwise ``"finish"`` to proceed to the judge.
    """
    current_round = state.get("current_debate_round", 0)
    max_rounds = state.get("max_debate_rounds", 2)
    if current_round < max_rounds:
        return "continue"
    return "finish"


def build_debate_graph(
    aws_ctx: RuntimeContext,
    azure_ctx: RuntimeContext,
    checkpointer: Any | None = None,
):
    """Build and compile the debate graph.

    Args:
        aws_ctx: RuntimeContext wired to AWS provider tools.
        azure_ctx: RuntimeContext wired to Azure provider tools.
        checkpointer: Optional LangGraph checkpointer.  When ``None`` the
                       graph runs without persistence (used by ``langgraph dev``).

    Returns:
        A compiled ``CompiledGraph``.
    """

    graph = StateGraph(State)

    # ── Nodes ────────────────────────────────────────────────────────────
    # debate_setup uses a shared context (aws_ctx here, but it only reads
    # state scalars — no provider-specific tools needed).
    graph.add_node("debate_setup", debate_setup(aws_ctx))
    graph.add_node("aws_advocate", aws_advocate(aws_ctx))
    graph.add_node("azure_advocate", azure_advocate(azure_ctx))
    graph.add_node("debate_round_synthesizer", debate_round_synthesizer(aws_ctx))
    graph.add_node("debate_judge", debate_judge(aws_ctx))

    # ── Edges ────────────────────────────────────────────────────────────
    graph.add_edge(START, "debate_setup")

    # Fan-out: debate_setup → both advocates in parallel
    graph.add_edge("debate_setup", "aws_advocate")
    graph.add_edge("debate_setup", "azure_advocate")

    # Fan-in: both advocates → round synthesizer
    graph.add_edge("aws_advocate", "debate_round_synthesizer")
    graph.add_edge("azure_advocate", "debate_round_synthesizer")

    # Conditional: continue debating or proceed to judge
    graph.add_conditional_edges(
        "debate_round_synthesizer",
        debate_round_condition,
        {"continue": "debate_setup", "finish": "debate_judge"},
    )

    graph.add_edge("debate_judge", END)

    if checkpointer is None:
        return graph.compile()
    return graph.compile(checkpointer=checkpointer)
