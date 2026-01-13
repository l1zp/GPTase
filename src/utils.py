"""Utility functions for common operations."""

import os

from src.core.config import load_template_config
from src.models.model import Model
from src.models.types import ModelConfig, ModelProvider


def default_manager() -> Model:
    """Create and configure a default Model instance using OpenAI provider.

    Loads configuration from template and environment variables, prioritizing
    template values when available and valid. Handles API key resolution and
    provides meaningful error messages if configuration is missing.

    Returns:
        Model: Configured Model instance

    Raises:
        ValueError: If no valid API key can be resolved
    """
    template = load_template_config()

    # Resolve API key: prefer template value unless it's missing/placeholder, then env
    tpl_key = template.get("api_key", "") or ""
    is_placeholder = isinstance(tpl_key, str) and tpl_key.strip().startswith("$")
    api_key = (
        tpl_key
        if (tpl_key and not is_placeholder)
        else (os.getenv("OPENAI_API_KEY") or os.getenv("GPTASE_OPENAI_API_KEY") or "")
    )

    # Abort early if no API key resolved
    if not api_key:
        raise ValueError(
            "Missing OpenAI API key. Set OPENAI_API_KEY env or add api_key in config/llm_config.template.json."
        )

    # Use OpenAI provider (real results), honoring custom base_url if provided
    return Model(
        default_config=ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name=template.get("model_name", "gpt-4o-mini"),
            api_key=api_key,
            base_url=template.get("base_url", None),
            temperature=float(template.get("temperature", 0.7)),
            max_tokens=int(template.get("max_tokens", 1000)),
            timeout=int(template.get("timeout", 300)),
            provider_config=template.get("provider_config", {}),
        )
    )
