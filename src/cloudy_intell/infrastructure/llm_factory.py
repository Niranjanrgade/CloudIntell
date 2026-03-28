"""LLM factory functions.

These helpers isolate model configuration and make node modules agnostic to
how model clients are instantiated.  Two distinct LLM instances are created:

- **Reasoning LLM** (gpt-5.4): Used by supervisors for task decomposition and
  by synthesizers for merging domain outputs.  These tasks require strong
  reasoning and structured output capabilities.

- **Execution LLM** (gpt-5.4-mini): Used by domain architects and validators
  for tool-calling loops.  This model is cost-efficient for the high-volume
  tool-call interactions that domain agents perform.

Both models are configured via ``AppSettings`` so the model names can be
overridden via environment variables without code changes.

The ``get_llm`` function supports dynamic model selection at runtime,
supporting OpenAI, Anthropic, and Google models through appropriate
LangChain chat classes.  Instances are cached per model name.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from cloudy_intell.config.models import AVAILABLE_MODELS
from cloudy_intell.config.settings import AppSettings

if TYPE_CHECKING:
    from cloudy_intell.schemas.models import State


def create_reasoning_llm(settings: AppSettings) -> ChatOpenAI:
    """Create the high-reasoning model used by supervisors and synthesizers."""

    return ChatOpenAI(model=settings.llm_reasoning_model)


def create_execution_llm(settings: AppSettings) -> ChatOpenAI:
    """Create the lighter execution model used by domain node calls."""

    return ChatOpenAI(model=settings.llm_execution_model)


@lru_cache(maxsize=32)
def get_llm(model_name: str) -> BaseChatModel:
    """Return a cached LLM instance for *model_name*.

    Supports OpenAI, Anthropic, and Google models.  The provider is
    determined from :data:`AVAILABLE_MODELS`; unknown models are assumed
    OpenAI-compatible.
    """

    info = AVAILABLE_MODELS.get(model_name)
    provider = info.provider if info else "openai"

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic  # type: ignore[import-untyped]

        return ChatAnthropic(model=model_name)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore[import-untyped]

        return ChatGoogleGenerativeAI(model=model_name)

    return ChatOpenAI(model=model_name)


def resolve_reasoning_llm(ctx, state: State) -> BaseChatModel:
    """Return the reasoning LLM, respecting a per-run override in *state*."""

    override = state.get("reasoning_model")
    if override and override != ctx.settings.llm_reasoning_model:
        return get_llm(override)
    return ctx.reasoning_llm


def resolve_execution_llm(ctx, state: State) -> BaseChatModel:
    """Return the execution LLM, respecting a per-run override in *state*."""

    override = state.get("execution_model")
    if override and override != ctx.settings.llm_execution_model:
        return get_llm(override)
    return ctx.mini_llm
