"""Debate-mode agent factories.

This module provides the five node factories used exclusively by the debate
graph.  The debate is a post-generation phase: it takes the completed AWS and
Azure architecture summaries as input and runs multi-round advocate debates
followed by a neutral judge verdict.

Agent overview:
- **debate_setup**: Increments the round counter and formats prior-round
  arguments so advocates can craft rebuttals.
- **aws_advocate / azure_advocate**: Each advocate argues for its vendor,
  citing unique benefits and countering the opposing side's arguments.
  Advocates use provider-specific tools (web_search + RAG) for evidence.
- **debate_round_synthesizer**: Fan-in node that collects both advocates'
  outputs into the ``debate_rounds`` list.
- **debate_judge**: Neutral evaluator that reviews all rounds and produces
  a structured verdict with per-dimension scores and a recommendation.

All factories follow the same closure pattern used throughout the codebase:
the outer function captures a ``RuntimeContext``, and the inner ``_node``
function matches the LangGraph signature ``(State) -> State``.
"""

import time
from typing import Any, Dict, cast

from langchain_core.messages import HumanMessage, SystemMessage

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.agents.tool_execution import execute_tool_calls
from cloudy_intell.infrastructure.llm_factory import resolve_execution_llm, resolve_reasoning_llm
from cloudy_intell.infrastructure.logging_utils import get_logger
from cloudy_intell.infrastructure.tools import rebind_tools
from cloudy_intell.schemas.models import State

logger = get_logger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _invoke_with_retries(llm, prompt: str, node_name: str, retries: int = 3) -> str:
    """Invoke an LLM with bounded retries (mirrors synthesizers._invoke_with_retries)."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = llm.invoke([SystemMessage(content=prompt)])
            content = getattr(response, "content", "")
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"[{node_name}] Empty response from LLM")
            return content
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries - 1:
                wait_time = 2 ** attempt
                logger.warning(
                    "%s LLM call failed (attempt %s/%s), retrying in %ss: %s",
                    node_name, attempt + 1, retries, wait_time, exc,
                )
                time.sleep(wait_time)
            else:
                logger.error("%s failed after retries: %s", node_name, exc, exc_info=True)
    return f"[{node_name}] Error: {last_error}"


def _format_previous_rounds(debate_rounds: list[Dict[str, Any]]) -> str:
    """Format prior debate rounds into readable context for advocates."""
    if not debate_rounds:
        return ""
    sections = ["\n--- Previous Debate Rounds ---"]
    for r in debate_rounds:
        rnd = r.get("round", "?")
        sections.append(f"\n## Round {rnd}")
        sections.append(f"**AWS Advocate:**\n{r.get('aws_argument', 'N/A')}")
        sections.append(f"**Azure Advocate:**\n{r.get('azure_argument', 'N/A')}")
    return "\n".join(sections)


# ── Node Factories ──────────────────────────────────────────────────────────

def debate_setup(ctx: RuntimeContext):
    """Create the debate setup node that increments round and prepares context.

    This node runs at the start of each debate round.  It increments the
    ``current_debate_round`` counter so advocates and the routing condition
    can track progress.
    """

    def _node(state: State) -> State:
        current_round = state.get("current_debate_round", 0) + 1
        logger.info("Debate setup: starting round %s / %s", current_round, state.get("max_debate_rounds", 2))
        return cast(State, {"current_debate_round": current_round})

    return _node


def aws_advocate(aws_ctx: RuntimeContext):
    """Create the AWS advocate node.

    Round 1: Opening argument — highlights AWS strengths and unique benefits
    for the problem at hand.
    Round 2+: Rebuttal — directly addresses Azure advocate's prior arguments
    and reinforces AWS advantages with evidence.

    Uses AWS-specific web_search + RAG tools via ``execute_tool_calls``.
    """

    provider = aws_ctx.provider

    def _node(state: State) -> State:
        current_round = state.get("current_debate_round", 1)
        user_problem = state.get("user_problem", "")
        aws_summary = state.get("aws_architecture_summary", "No AWS architecture available.")
        azure_summary = state.get("azure_architecture_summary", "No Azure architecture available.")
        previous_rounds = _format_previous_rounds(state.get("debate_rounds", []))

        if current_round == 1:
            system_prompt = f"""You are an {provider.display_name} Solutions Advocate in a structured debate.
Your goal is to argue convincingly why the {provider.display_name} architecture is the superior choice.

## Context
Original Problem: {user_problem}

## Your {provider.display_name} Architecture:
{aws_summary}

## Opponent's Azure Architecture:
{azure_summary}

## Your Task (Opening Argument — Round 1)
1. Present the key advantages of your {provider.display_name} solution over the Azure alternative.
2. Highlight unique {provider.display_name} services and capabilities that Azure cannot match or does less well.
3. Use tools to find specific evidence: pricing advantages, performance benchmarks, service maturity, ecosystem breadth, compliance certifications, global infrastructure.
4. Focus on concrete, factual differentiators — not generic marketing claims.
5. Identify weaknesses in the Azure proposal and explain why your approach is stronger.

Structure your argument with clear sections: Key Advantages, Unique Benefits Over Azure, Evidence, and Conclusion."""
        else:
            system_prompt = f"""You are an {provider.display_name} Solutions Advocate in debate round {current_round}.
Your goal is to rebut the Azure advocate's arguments from the previous round and strengthen your position.

## Context
Original Problem: {user_problem}

## Your {provider.display_name} Architecture:
{aws_summary}

## Opponent's Azure Architecture:
{azure_summary}

{previous_rounds}

## Your Task (Rebuttal — Round {current_round})
1. Directly address and counter each of the Azure advocate's arguments from the previous round.
2. Provide additional evidence supporting {provider.display_name} advantages using tools.
3. Identify any inaccuracies or exaggerations in the Azure advocate's claims.
4. Reinforce your strongest differentiators with fresh evidence.
5. Concede points where Azure genuinely excels, but explain mitigations or why it matters less for this specific problem.

Structure your argument with: Counterpoints to Azure, Additional Evidence, Concessions & Mitigations, and Conclusion."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Present your round {current_round} argument for {provider.display_name}."),
        ]

        try:
            exec_llm = resolve_execution_llm(aws_ctx, state)
            tools = aws_ctx.tools if exec_llm is aws_ctx.mini_llm else rebind_tools(aws_ctx.tools, exec_llm)
            response = execute_tool_calls(
                messages,
                tools.llm_with_all_tools,
                {"web_search": tools.web_search, "RAG_search": tools.rag_search},
                max_iterations=aws_ctx.settings.tool_max_iterations,
                timeout=aws_ctx.settings.tool_timeout_seconds,
                retry_attempts=aws_ctx.settings.llm_retry_attempts,
            )
            argument = getattr(response, "content", "")
            if not argument or not argument.strip():
                argument = f"[aws_advocate] Round {current_round}: Unable to generate argument."
        except Exception as exc:  # noqa: BLE001
            logger.error("[aws_advocate] Error in round %s: %s", current_round, exc, exc_info=True)
            argument = f"[aws_advocate] Error generating round {current_round} argument: {exc}"

        return cast(
            State,
            {
                "architecture_components": {
                    f"aws_debate_round_{current_round}": {
                        "argument": argument,
                        "agent": "aws_advocate",
                        "round": current_round,
                    }
                }
            },
        )

    return _node


def azure_advocate(azure_ctx: RuntimeContext):
    """Create the Azure advocate node.

    Mirror of aws_advocate using Azure-specific tools and provider metadata.
    """

    provider = azure_ctx.provider

    def _node(state: State) -> State:
        current_round = state.get("current_debate_round", 1)
        user_problem = state.get("user_problem", "")
        aws_summary = state.get("aws_architecture_summary", "No AWS architecture available.")
        azure_summary = state.get("azure_architecture_summary", "No Azure architecture available.")
        previous_rounds = _format_previous_rounds(state.get("debate_rounds", []))

        if current_round == 1:
            system_prompt = f"""You are an {provider.display_name} Solutions Advocate in a structured debate.
Your goal is to argue convincingly why the {provider.display_name} architecture is the superior choice.

## Context
Original Problem: {user_problem}

## Your {provider.display_name} Architecture:
{azure_summary}

## Opponent's AWS Architecture:
{aws_summary}

## Your Task (Opening Argument — Round 1)
1. Present the key advantages of your {provider.display_name} solution over the AWS alternative.
2. Highlight unique {provider.display_name} services and capabilities that AWS cannot match or does less well.
3. Use tools to find specific evidence: pricing advantages, performance benchmarks, enterprise integration (Active Directory, Microsoft 365, hybrid cloud), compliance certifications, developer experience.
4. Focus on concrete, factual differentiators — not generic marketing claims.
5. Identify weaknesses in the AWS proposal and explain why your approach is stronger.

Structure your argument with clear sections: Key Advantages, Unique Benefits Over AWS, Evidence, and Conclusion."""
        else:
            system_prompt = f"""You are an {provider.display_name} Solutions Advocate in debate round {current_round}.
Your goal is to rebut the AWS advocate's arguments from the previous round and strengthen your position.

## Context
Original Problem: {user_problem}

## Your {provider.display_name} Architecture:
{azure_summary}

## Opponent's AWS Architecture:
{aws_summary}

{previous_rounds}

## Your Task (Rebuttal — Round {current_round})
1. Directly address and counter each of the AWS advocate's arguments from the previous round.
2. Provide additional evidence supporting {provider.display_name} advantages using tools.
3. Identify any inaccuracies or exaggerations in the AWS advocate's claims.
4. Reinforce your strongest differentiators with fresh evidence.
5. Concede points where AWS genuinely excels, but explain mitigations or why it matters less for this specific problem.

Structure your argument with: Counterpoints to AWS, Additional Evidence, Concessions & Mitigations, and Conclusion."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Present your round {current_round} argument for {provider.display_name}."),
        ]

        try:
            exec_llm = resolve_execution_llm(azure_ctx, state)
            tools = azure_ctx.tools if exec_llm is azure_ctx.mini_llm else rebind_tools(azure_ctx.tools, exec_llm)
            response = execute_tool_calls(
                messages,
                tools.llm_with_all_tools,
                {"web_search": tools.web_search, "RAG_search": tools.rag_search},
                max_iterations=azure_ctx.settings.tool_max_iterations,
                timeout=azure_ctx.settings.tool_timeout_seconds,
                retry_attempts=azure_ctx.settings.llm_retry_attempts,
            )
            argument = getattr(response, "content", "")
            if not argument or not argument.strip():
                argument = f"[azure_advocate] Round {current_round}: Unable to generate argument."
        except Exception as exc:  # noqa: BLE001
            logger.error("[azure_advocate] Error in round %s: %s", current_round, exc, exc_info=True)
            argument = f"[azure_advocate] Error generating round {current_round} argument: {exc}"

        return cast(
            State,
            {
                "architecture_components": {
                    f"azure_debate_round_{current_round}": {
                        "argument": argument,
                        "agent": "azure_advocate",
                        "round": current_round,
                    }
                }
            },
        )

    return _node


def debate_round_synthesizer(ctx: RuntimeContext):
    """Create the fan-in node that collects both advocates' arguments for the round.

    Reads the latest debate-round entries from ``architecture_components``
    (keyed as ``aws_debate_round_N`` and ``azure_debate_round_N``) and
    appends a structured round dict to ``debate_rounds``.
    """

    def _node(state: State) -> State:
        current_round = state.get("current_debate_round", 1)
        components = state.get("architecture_components", {})

        aws_key = f"aws_debate_round_{current_round}"
        azure_key = f"azure_debate_round_{current_round}"

        aws_argument = components.get(aws_key, {}).get("argument", "No AWS argument for this round.")
        azure_argument = components.get(azure_key, {}).get("argument", "No Azure argument for this round.")

        round_entry: Dict[str, Any] = {
            "round": current_round,
            "aws_argument": aws_argument,
            "azure_argument": azure_argument,
        }

        logger.info("Debate round %s synthesized.", current_round)
        return cast(State, {"debate_rounds": [round_entry]})

    return _node


def debate_judge(ctx: RuntimeContext):
    """Create the neutral judge node that evaluates the full debate.

    The judge reviews both architecture summaries and all debate rounds,
    then produces a structured verdict with:
    - Per-dimension scores (cost, scalability, security, reliability,
      developer experience, enterprise readiness)
    - Narrative analysis of each side's strongest and weakest arguments
    - A final recommendation with rationale
    - Scenarios where each provider would be the better choice
    """

    def _node(state: State) -> State:
        user_problem = state.get("user_problem", "")
        aws_summary = state.get("aws_architecture_summary", "N/A")
        azure_summary = state.get("azure_architecture_summary", "N/A")
        debate_rounds = state.get("debate_rounds", [])

        rounds_text = ""
        for r in debate_rounds:
            rnd = r.get("round", "?")
            rounds_text += f"\n## Round {rnd}\n"
            rounds_text += f"### AWS Advocate\n{r.get('aws_argument', 'N/A')}\n"
            rounds_text += f"### Azure Advocate\n{r.get('azure_argument', 'N/A')}\n"

        prompt = f"""You are a neutral Cloud Architecture Judge evaluating a structured debate between an AWS advocate and an Azure advocate.

## Original Problem
{user_problem}

## AWS Proposed Architecture
{aws_summary}

## Azure Proposed Architecture
{azure_summary}

## Debate Transcript
{rounds_text}

## Your Task
Produce a comprehensive, balanced verdict:

1. **Dimension Scores** (rate each provider 1-10 for this specific problem):
   - Cost Efficiency
   - Scalability & Performance
   - Security & Compliance
   - Reliability & Availability
   - Developer Experience
   - Enterprise Readiness
   - Service Maturity for Required Components

2. **Argument Analysis**:
   - Strongest arguments from each side
   - Weakest or unsupported claims from each side
   - Points where one side effectively countered the other

3. **Final Recommendation**:
   - Which provider is the better fit for this specific problem and why
   - Key deciding factors
   - What the losing side would need to offer to change the recommendation

4. **Scenario Guidance**:
   - Scenarios where the other provider would be the better choice
   - Hybrid considerations (using both providers)

Be rigorous, evidence-based, and fair. Cite specific arguments from the debate transcript."""

        verdict = _invoke_with_retries(resolve_reasoning_llm(ctx, state), prompt, "debate_judge")

        return cast(
            State,
            {
                "debate_summary": verdict,
                "architecture_summary": verdict,
            },
        )

    return _node
