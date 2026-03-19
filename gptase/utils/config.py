"""
Configuration management for the GPTase framework
"""

import json
import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from ..models.types import ModelConfig
from .exceptions import ConfigurationError

load_dotenv()

logger = logging.getLogger(__name__)

# Constants
_DEFAULT_MODEL = "gpt-4"
_DEFAULT_BASE_URL = "https://aiping.cn/api/v1"
_DEFAULT_TEMPERATURE = 0.1
_DEFAULT_MAX_TOKENS = 2000
_DEFAULT_MEMORY_TYPE = "local"
_DEFAULT_MAX_HISTORY = 1000
_DEFAULT_LOG_LEVEL = "INFO"
_ENV_PREFIX = "GPTASE_"

_ENV_API_KEY = "OPENAI_API_KEY"

# Path configuration
_CONFIG_RELATIVE_PATH = "../../config/llm_config.template.json"


class MemoryConfig(BaseModel):
    """Configuration for memory systems."""

    type: str = Field(default=_DEFAULT_MEMORY_TYPE, description="Memory storage type")
    max_history: int = Field(default=_DEFAULT_MAX_HISTORY,
                             description="Maximum history entries")


class FrameworkConfig(BaseModel):
    """Framework configuration.

    Provides a flat configuration structure with support for agent-specific
    model overrides. All models go through OpenAI-compatible APIs.
    """

    # LLM settings - flattened structure
    llm_model: str = Field(default=_DEFAULT_MODEL, description="Model name")
    llm_api_key: Optional[str] = Field(default=None, description="API key")
    llm_base_url: Optional[str] = Field(default=_DEFAULT_BASE_URL,
                                        description="Base URL for API")
    llm_temperature: float = Field(default=_DEFAULT_TEMPERATURE,
                                   description="Temperature for generation")
    llm_max_tokens: int = Field(default=_DEFAULT_MAX_TOKENS,
                                description="Maximum tokens to generate")
    llm_timeout: Optional[int] = Field(
        default=None, description="Timeout for API requests in seconds")
    llm_stream: bool = Field(default=True, description="Enable streaming")
    llm_enable_thinking: bool = Field(default=True,
                                      description="Enable reasoning/thinking mode")

    # Per-agent model configurations (Agent Name → Model Config)
    # Allows different agents to use different models
    agent_models: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Model configurations for specific agents by name")

    # Other configuration
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    log_level: str = Field(default=_DEFAULT_LOG_LEVEL, description="Logging level")

    model_config = ConfigDict(env_prefix=_ENV_PREFIX)

    def __init__(self, **kwargs):
        # Always normalize field names (from JSON format to FrameworkConfig format)
        normalized_kwargs = self._normalize_field_names(kwargs)

        # Load template config if no explicit config provided
        if not normalized_kwargs:
            template_config = self._load_template_config()
            normalized_kwargs = template_config

        super().__init__(**normalized_kwargs)
        self._load_api_key_from_env()

    def _normalize_field_names(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize JSON field names to FrameworkConfig field names.

        Args:
            config: Configuration dictionary with JSON field names.

        Returns:
            Configuration dictionary with FrameworkConfig field names.
        """
        if not config:
            return config

        # Map JSON field names to FrameworkConfig field names
        field_mapping = {
            "model_name": "llm_model",
            "api_key": "llm_api_key",
            "base_url": "llm_base_url",
            "temperature": "llm_temperature",
            "max_tokens": "llm_max_tokens",
            "timeout": "llm_timeout",
            "stream": "llm_stream",
            "enable_thinking": "llm_enable_thinking",
        }

        mapped_config = {}
        for json_key, value in config.items():
            framework_key = field_mapping.get(json_key, json_key)
            # Skip legacy fields that are no longer needed
            if json_key in ("provider", "thinking", "provider_config"):
                continue
            mapped_config[framework_key] = value

        return mapped_config

    def _load_template_config(self) -> Dict[str, Any]:
        """Load configuration from the template file with field name normalization.

        Returns:
            Normalized configuration dictionary.

        Raises:
            ConfigurationError: If the file is missing or cannot be parsed.
        """
        try:
            config_data = load_template_config()
            return self._normalize_field_names(config_data)
        except Exception:
            # If template loading fails, return empty dict to use defaults
            logger.debug("Could not load template config, using defaults")
            return {}

    def _load_api_key_from_env(self) -> None:
        """Load API key from environment variables if not already set."""
        if not self.llm_api_key:
            self.llm_api_key = os.getenv(_ENV_API_KEY)

    def to_model_config(self) -> ModelConfig:
        """Convert this FrameworkConfig to a ModelConfig using default LLM settings."""
        return ModelConfig(
            model_name=self.llm_model,
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
            temperature=self.llm_temperature,
            max_tokens=self.llm_max_tokens,
            timeout=self.llm_timeout or 600,
            stream=self.llm_stream,
            enable_thinking=self.llm_enable_thinking,
        )

    def get_config_for_agent(self, agent_name: str) -> Optional[ModelConfig]:
        """Get model configuration for a specific agent by name.

        This allows different agents to use different models based on their
        AGENT_NAME class attribute. Configuration is looked up from the
        'agent_models' field in the config file.

        Args:
            agent_name: The agent name (e.g., "vision_image_analyzer").

        Returns:
            ModelConfig for the agent, or None if no specific config is found.
        """
        agent_config = None
        normalized_names = [
            agent_name,
            agent_name.replace("-", "_"),
            agent_name.replace("_", "-")
        ]

        for name in normalized_names:
            if name in self.agent_models:
                agent_config = self.agent_models[name]
                break

        if not agent_config:
            # No specific config for this agent, use default
            return None

        # Fields that can be overridden per agent
        override_fields = [
            "model_name",
            "api_key",
            "base_url",
            "temperature",
            "max_tokens",
            "timeout",
            "stream",
            "enable_thinking",
        ]

        # Build ModelConfig kwargs from defaults, then override with agent-specific values
        mc_kwargs: Dict[str, Any] = self.to_model_config().model_dump()

        # Override with agent-specific values
        for field in override_fields:
            if field in agent_config:
                mc_kwargs[field] = agent_config[field]

        return ModelConfig(**mc_kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return self.model_dump()


# Environment variable for custom config file path
_ENV_LLM_CONFIG = "GPTASE_LLM_CONFIG"


def _get_template_config_path() -> str:
    """Get the absolute path to the template configuration file.

    Checks for custom config via GPTASE_LLM_CONFIG environment variable first,
    falls back to default template if not set.

    Returns:
        Absolute path to the template config file.
    """
    # Check for custom config via environment variable
    custom_config = os.getenv(_ENV_LLM_CONFIG)
    if custom_config:
        # Support both absolute and relative paths
        if os.path.isabs(custom_config):
            return custom_config
        # Resolve relative path from project root (parent of gptase package)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        return os.path.abspath(os.path.join(project_root, custom_config))

    # Fall back to default template
    template_path = os.path.join(os.path.dirname(__file__), _CONFIG_RELATIVE_PATH)
    return os.path.abspath(template_path)


def load_template_config() -> Dict[str, Any]:
    """Load configuration from the template file with error handling.

    Uses GPTASE_LLM_CONFIG environment variable if set, otherwise uses
    the default template config.

    Returns:
        Parsed JSON configuration contents.

    Raises:
        ConfigurationError: If the file is missing or cannot be parsed.
    """
    template_path = _get_template_config_path()
    config_source = os.getenv(_ENV_LLM_CONFIG, "default template")

    try:
        with open(template_path, "r") as f:
            try:
                config_data = json.load(f)
                logger.info("Successfully loaded config from %s (source: %s)",
                            template_path, config_source)
                return config_data
            except json.JSONDecodeError as e:
                logger.error("JSON parsing error in template config: %s", e)
                raise ConfigurationError(f"Invalid template config format: {e}") from e
    except FileNotFoundError:
        logger.error("Template config file not found at %s", template_path)
        raise ConfigurationError(
            f"Template config file missing: {template_path}") from None
    except Exception as e:
        logger.error("Unexpected error loading template config: %s", e)
        raise ConfigurationError(f"Failed to load template config: {e}") from e
