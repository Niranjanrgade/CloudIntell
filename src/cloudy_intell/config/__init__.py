"""Configuration package for Cloudy-Intell.

Exports application settings (``AppSettings``, ``get_settings``), provider
metadata (``ProviderMeta``, ``AWS_META``, ``AZURE_META``, ``DOMAINS``), and
the LLM model catalog (``AVAILABLE_MODELS``, ``ModelInfo``) used throughout
the application to drive provider-specific behavior.
"""

from .models import AVAILABLE_MODELS, ModelInfo, get_all_models, get_models_for_tier, serialize_catalog
from .provider_meta import AZURE_META, AWS_META, DOMAINS, ProviderMeta, ProviderName, get_provider_meta
from .settings import AppSettings, get_settings

__all__ = [
    "AVAILABLE_MODELS",
    "ModelInfo",
    "get_all_models",
    "get_models_for_tier",
    "serialize_catalog",
    "AppSettings",
    "get_settings",
    "ProviderMeta",
    "ProviderName",
    "AWS_META",
    "AZURE_META",
    "DOMAINS",
    "get_provider_meta",
]