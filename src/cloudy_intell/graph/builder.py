"""Graph construction for the architecture workflow."""

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from cloud_intell.agents.context import RuntimeContext
from cloud_intell.agents.domain_nodes import (
    compute_architect,
    compute_validator,
    database_architect,
    database_validator,
    network_architect,
    network_validator,
    storage_architect,
    storage_validator,
)
from cloud_intell.agents.supervisors import architect_supervisor, validator_supervisor
from cloud_intell.agents.synthesizers import (
    architect_synthesizer,
    final_architecture_generator,
    validation_synthesizer,
)
from cloud_intell.graph.routing import iteration_condition
from cloud_intell.schemas.models import InputState, State


def _input_handler(state: State) -> dict:
    """Bridge Studio/API chat messages into graph state fields.

    Allows users to trigger the graph from LangGraph Studio's chat panel
    by simply typing their cloud architecture request.  The node also
    initialises iteration counters so callers don't have to supply them.
    """
    updates: dict = {}

    # If user_problem was not supplied explicitly, pull it from the last
    # HumanMessage in the messages list (LangGraph Studio chat input).
    if not state.get("user_problem"):
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, HumanMessage) or getattr(msg, "type", None) == "human":
                updates["user_problem"] = msg.content
                break

    # Initialise iteration settings to sensible defaults when omitted.
    if not state.get("iteration_count"):
        updates["iteration_count"] = 0
    if not state.get("min_iterations"):
        updates["min_iterations"] = 1
    if not state.get("max_iterations"):
        updates["max_iterations"] = 3

    return updates


def build_graph(ctx: RuntimeContext, checkpointer: Any | None = None):
    """Build and compile LangGraph using modularized node factories."""

    graph_builder = StateGraph(State, input=InputState)

    # Input handler — bridges Studio chat messages to state fields.
    graph_builder.add_node("input_handler", _input_handler)

    # Architect nodes
    graph_builder.add_node("architect_supervisor", architect_supervisor(ctx))
    graph_builder.add_node("compute_architect", compute_architect(ctx))
    graph_builder.add_node("network_architect", network_architect(ctx))
    graph_builder.add_node("storage_architect", storage_architect(ctx))
    graph_builder.add_node("database_architect", database_architect(ctx))
    graph_builder.add_node("architect_synthesizer", architect_synthesizer(ctx))

    # Validator nodes
    graph_builder.add_node("validator_supervisor", validator_supervisor(ctx))
    graph_builder.add_node("compute_validator", compute_validator(ctx))
    graph_builder.add_node("network_validator", network_validator(ctx))
    graph_builder.add_node("storage_validator", storage_validator(ctx))
    graph_builder.add_node("database_validator", database_validator(ctx))
    graph_builder.add_node("validation_synthesizer", validation_synthesizer(ctx))
    graph_builder.add_node("final_architecture_generator", final_architecture_generator(ctx))

    # Architecture generation flow.
    graph_builder.add_edge(START, "input_handler")
    graph_builder.add_edge("input_handler", "architect_supervisor")
    graph_builder.add_edge("architect_supervisor", "compute_architect")
    graph_builder.add_edge("architect_supervisor", "network_architect")
    graph_builder.add_edge("architect_supervisor", "storage_architect")
    graph_builder.add_edge("architect_supervisor", "database_architect")

    graph_builder.add_edge("compute_architect", "architect_synthesizer")
    graph_builder.add_edge("network_architect", "architect_synthesizer")
    graph_builder.add_edge("storage_architect", "architect_synthesizer")
    graph_builder.add_edge("database_architect", "architect_synthesizer")

    # Validation flow.
    graph_builder.add_edge("architect_synthesizer", "validator_supervisor")
    graph_builder.add_edge("validator_supervisor", "compute_validator")
    graph_builder.add_edge("validator_supervisor", "network_validator")
    graph_builder.add_edge("validator_supervisor", "storage_validator")
    graph_builder.add_edge("validator_supervisor", "database_validator")

    graph_builder.add_edge("compute_validator", "validation_synthesizer")
    graph_builder.add_edge("network_validator", "validation_synthesizer")
    graph_builder.add_edge("storage_validator", "validation_synthesizer")
    graph_builder.add_edge("database_validator", "validation_synthesizer")

    # Iteration routing.
    graph_builder.add_conditional_edges(
        "validation_synthesizer",
        iteration_condition,
        {"iterate": "architect_supervisor", "finish": "final_architecture_generator"},
    )
    graph_builder.add_edge("final_architecture_generator", END)

    if checkpointer is None:
        return graph_builder.compile()
    return graph_builder.compile(checkpointer=checkpointer)
