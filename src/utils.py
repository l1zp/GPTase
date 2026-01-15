"""Utility functions for common operations."""

import os
from typing import Any, Dict

from src.core.config import load_template_config
from src.core.exceptions import ConfigurationError
from src.models.model import Model
from src.models.types import ModelConfig
from src.models.types import ModelProvider

# Configuration constants
_PLACEHOLDER_PREFIX = "$"
_DEFAULT_MODEL_NAME = "gpt-4o-mini"
_DEFAULT_TEMPERATURE = 0.7
_DEFAULT_MAX_TOKENS = 1000
_DEFAULT_TIMEOUT = 300

# Environment variable names for API keys
_ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
_ENV_GPTASE_API_KEY = "GPTASE_OPENAI_API_KEY"
_ENV_API_KEY = "API_KEY"


def _resolve_api_key(template_config: Dict[str, Any]) -> str:
    """Resolve API key from template configuration or environment variables.

    Resolution priority:
    1. Template value (if not a placeholder)
    2. API_KEY environment variable
    3. OPENAI_API_KEY environment variable
    4. GPTASE_OPENAI_API_KEY environment variable

    Args:
        template_config: Loaded template configuration dictionary.

    Returns:
        Resolved API key string.

    Raises:
        ConfigurationError: If no valid API key can be resolved.
    """
    tpl_key = template_config.get("api_key", "") or ""
    is_placeholder = (isinstance(tpl_key, str)
                      and tpl_key.strip().startswith(_PLACEHOLDER_PREFIX))

    if tpl_key and not is_placeholder:
        return tpl_key

    # Check environment variables in priority order
    api_key = (os.getenv(_ENV_API_KEY) or os.getenv(_ENV_OPENAI_API_KEY)
               or os.getenv(_ENV_GPTASE_API_KEY) or "")

    if not api_key:
        raise ConfigurationError(
            f"Missing OpenAI API key. Set {_ENV_OPENAI_API_KEY} or {_ENV_API_KEY} "
            "environment variable, or add api_key in config/llm_config.template.json.")

    return api_key


def _build_model_config(template_config: Dict[str, Any], api_key: str) -> ModelConfig:
    """Build ModelConfig from template and resolved API key.

    Args:
        template_config: Loaded template configuration dictionary.
        api_key: Resolved API key.

    Returns:
        Configured ModelConfig instance.
    """
    return ModelConfig(
        provider=ModelProvider.OPENAI,
        model_name=template_config.get("model_name", _DEFAULT_MODEL_NAME),
        api_key=api_key,
        base_url=template_config.get("base_url"),
        temperature=float(template_config.get("temperature", _DEFAULT_TEMPERATURE)),
        max_tokens=int(template_config.get("max_tokens", _DEFAULT_MAX_TOKENS)),
        timeout=int(template_config.get("timeout", _DEFAULT_TIMEOUT)),
        provider_config=template_config.get("provider_config", {}),
    )


def default_manager() -> Model:
    """Create and configure a default Model instance using OpenAI provider.

    Loads configuration from template and environment variables, prioritizing
    template values when available and valid. Handles API key resolution and
    provides meaningful error messages if configuration is missing.

    Returns:
        Configured Model instance.

    Raises:
        ConfigurationError: If no valid API key can be resolved.
    """
    template = load_template_config()
    api_key = _resolve_api_key(template)
    model_config = _build_model_config(template, api_key)
    return Model(default_config=model_config)
