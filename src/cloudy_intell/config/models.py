"""Available LLM model catalog.

Defines the set of models users can choose from via the UI.  Each entry
maps a canonical model identifier to display metadata and a provider tag
that controls which LangChain chat class is instantiated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal

ModelProvider = Literal["openai", "anthropic", "google"]
ModelTier = Literal["reasoning", "execution"]


@dataclass(frozen=True)
class ModelInfo:
    """Metadata for a single selectable LLM."""

    id: str
    display_name: str
    provider: ModelProvider
    tier: ModelTier
    description: str = ""


# ── Catalog ─────────────────────────────────────────────────────────────
# Keep sorted by provider → capability (descending).

AVAILABLE_MODELS: Dict[str, ModelInfo] = {
    # OpenAI — GPT-5.4 family (March 2026)
    "gpt-5.4": ModelInfo(
        id="gpt-5.4",
        display_name="GPT-5.4",
        provider="openai",
        tier="reasoning",
        description="Flagship model for complex reasoning, coding, and agentic workflows (1M context)",
    ),
    "gpt-5.4-mini": ModelInfo(
        id="gpt-5.4-mini",
        display_name="GPT-5.4 Mini",
        provider="openai",
        tier="execution",
        description="Strong mini model for coding, computer use, and sub-agents (400K context)",
    ),
    "gpt-5.4-nano": ModelInfo(
        id="gpt-5.4-nano",
        display_name="GPT-5.4 Nano",
        provider="openai",
        tier="execution",
        description="Cheapest GPT-5.4-class model for simple high-volume tasks (400K context)",
    ),
    # Anthropic — Claude 4.6 / 4.5 family (March 2026)
    "claude-opus-4-6": ModelInfo(
        id="claude-opus-4-6",
        display_name="Claude Opus 4.6",
        provider="anthropic",
        tier="reasoning",
        description="Most intelligent model for agents and coding (1M context, extended thinking)",
    ),
    "claude-sonnet-4-6": ModelInfo(
        id="claude-sonnet-4-6",
        display_name="Claude Sonnet 4.6",
        provider="anthropic",
        tier="reasoning",
        description="Best combination of speed and intelligence (1M context, extended thinking)",
    ),
    "claude-haiku-4-5": ModelInfo(
        id="claude-haiku-4-5",
        display_name="Claude Haiku 4.5",
        provider="anthropic",
        tier="execution",
        description="Fastest model with near-frontier intelligence (200K context)",
    ),
    # Google — Gemini 3.x / 2.5 family (March 2026)
    "gemini-3.1-pro-preview": ModelInfo(
        id="gemini-3.1-pro-preview",
        display_name="Gemini 3.1 Pro",
        provider="google",
        tier="reasoning",
        description="Advanced intelligence for complex problem-solving and agentic coding",
    ),
    "gemini-3-flash-preview": ModelInfo(
        id="gemini-3-flash-preview",
        display_name="Gemini 3 Flash",
        provider="google",
        tier="execution",
        description="Frontier-class performance at a fraction of the cost",
    ),
    "gemini-2.5-flash": ModelInfo(
        id="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        provider="google",
        tier="execution",
        description="Best price-performance for low-latency reasoning tasks",
    ),
}


def get_models_for_tier(tier: ModelTier) -> List[ModelInfo]:
    """Return all models suitable for a given tier."""
    return [m for m in AVAILABLE_MODELS.values() if m.tier == tier]


def get_all_models() -> List[ModelInfo]:
    """Return the full catalog as a list."""
    return list(AVAILABLE_MODELS.values())


def serialize_catalog() -> List[dict]:
    """Return JSON-serializable list of all models (for API responses)."""
    return [
        {
            "id": m.id,
            "display_name": m.display_name,
            "provider": m.provider,
            "tier": m.tier,
            "description": m.description,
        }
        for m in AVAILABLE_MODELS.values()
    ]
