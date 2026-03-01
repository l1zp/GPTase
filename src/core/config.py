"""
Configuration management for the GPTase framework
"""

import json
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from ..models.types import ModelConfig
from ..models.types import ModelRole
from ..models.types import ThinkingConfig
from .constants import Timeouts
from .exceptions import ConfigurationError
from .logging import logger
from .logging import setup_logging

load_dotenv()
setup_logging()

# Constants
_DEFAULT_PROVIDER = "openai"
_DEFAULT_MODEL = "gpt-4"
_DEFAULT_TEMPERATURE = 0.1
_DEFAULT_MAX_TOKENS = 2000
_DEFAULT_TOOL_TIMEOUT = Timeouts.TOOL
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_MEMORY_TYPE = "local"
_DEFAULT_MAX_HISTORY = 1000
_DEFAULT_PERSISTENCE_FILE = "memory_store.json"
_DEFAULT_LOG_LEVEL = "INFO"
_ENV_PREFIX = "GPTASE_"

_ENV_OPENAI_API_KEY = "OPENAI_API_KEY"

# Path configuration
_CONFIG_RELATIVE_PATH = "../../config/llm_config.template.json"


class LLMConfig(BaseModel):
    """Configuration for LLM providers."""

    provider: str = Field(default=_DEFAULT_PROVIDER, description="LLM provider")
    model: str = Field(default=_DEFAULT_MODEL, description="Model name")
    api_key: Optional[str] = Field(default=None, description="API key")
    base_url: Optional[str] = Field(default=None, description="Base URL for API")
    temperature: float = Field(default=_DEFAULT_TEMPERATURE,
                               description="Temperature for generation")
    max_tokens: int = Field(default=_DEFAULT_MAX_TOKENS,
                            description="Maximum tokens to generate")


class MemoryConfig(BaseModel):
    """Configuration for memory systems."""

    type: str = Field(default=_DEFAULT_MEMORY_TYPE, description="Memory storage type")
    max_history: int = Field(default=_DEFAULT_MAX_HISTORY,
                             description="Maximum history entries")
    persistence_file: str = Field(default=_DEFAULT_PERSISTENCE_FILE,
                                  description="File for persistent storage")


class ToolConfig(BaseModel):
    """Configuration for tool systems."""

    timeout: int = Field(default=_DEFAULT_TOOL_TIMEOUT,
                         description="Tool execution timeout in seconds")
    max_retries: int = Field(default=_DEFAULT_MAX_RETRIES,
                             description="Maximum retry attempts")
    sandbox_enabled: bool = Field(default=True, description="Enable code sandboxing")


class SandboxConfig(BaseModel):
    """Configuration for sandbox execution environment."""

    enabled: bool = Field(default=True, description="Enable sandbox for code execution")
    type: str = Field(default="local",
                      description="Sandbox type (local, docker, remote)")
    timeout: int = Field(default=30, description="Default execution timeout in seconds")
    memory_limit: int = Field(default=0,
                              description="Memory limit in MB (0 for unlimited)")
    network_enabled: bool = Field(default=False,
                                  description="Allow network access in sandbox")
    working_dir: Optional[str] = Field(default=None,
                                       description="Default working directory")


class MiddlewareConfig(BaseModel):
    """Configuration for middleware systems."""

    enabled: bool = Field(default=True, description="Enable middleware processing")
    thread_data_dir: str = Field(default="data/threads",
                                 description="Base directory for thread data")
    auto_title: bool = Field(default=True, description="Auto-generate thread titles")


class ConversationTrackingConfig(BaseModel):
    """Configuration for conversation tracking."""

    enabled: bool = Field(default=False, description="Enable conversation tracking")
    db_path: str = Field(default="data/conversations.db", description="Database path")


class FrameworkConfig(BaseModel):
    """Framework configuration.

    Provides a flat configuration structure with support for role-specific
    model overrides.
    """

    # LLM settings - flattened structure
    llm_provider: str = Field(default=_DEFAULT_PROVIDER, description="LLM provider")
    llm_model: str = Field(default=_DEFAULT_MODEL, description="Model name")
    llm_api_key: Optional[str] = Field(default=None, description="API key")
    llm_base_url: Optional[str] = Field(default=None, description="Base URL for API")
    llm_temperature: float = Field(default=_DEFAULT_TEMPERATURE,
                                   description="Temperature for generation")
    llm_max_tokens: int = Field(default=_DEFAULT_MAX_TOKENS,
                                description="Maximum tokens to generate")
    llm_timeout: Optional[int] = Field(
        default=None, description="Timeout for API requests in seconds")
    llm_thinking: Optional[ThinkingConfig] = Field(
        default=None, description="Thinking configuration (new format)")
    llm_enable_thinking: bool = Field(
        default=False,
        description=
        "Enable thinking/reasoning mode (legacy format, superseded by llm_thinking)",
    )
    llm_provider_config: Dict[str, Any] = Field(default_factory=dict,
                                                description="Provider-specific config")

    # Optional per-role model overrides
    planner_model: Optional[str] = Field(default=None,
                                         description="Model override for planner")
    executor_model: Optional[str] = Field(default=None,
                                          description="Model override for executor")
    tool_manager_model: Optional[str] = Field(
        default=None, description="Model override for tool manager")
    memory_manager_model: Optional[str] = Field(
        default=None, description="Model override for memory manager")

    # Per-agent model configurations (Agent Name → Model Config)
    # Allows different agents to use different models
    agent_models: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Model configurations for specific agents by name")

    # Other configuration
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    middleware: MiddlewareConfig = Field(default_factory=MiddlewareConfig)
    log_level: str = Field(default=_DEFAULT_LOG_LEVEL, description="Logging level")
    conversation_tracking: ConversationTrackingConfig = Field(
        default_factory=ConversationTrackingConfig,
        description="Conversation tracking settings",
    )

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
            "enable_thinking": "llm_enable_thinking",
            "thinking": "llm_thinking",
            "provider_config": "llm_provider_config",
            "timeout": "llm_timeout",
        }

        mapped_config = {}
        for json_key, value in config.items():
            framework_key = field_mapping.get(json_key, json_key)

            # Convert thinking dict to ThinkingConfig object
            if framework_key == "llm_thinking" and isinstance(value, dict):
                mapped_config[framework_key] = ThinkingConfig(**value)
            else:
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
            self.llm_api_key = os.getenv(_ENV_OPENAI_API_KEY)

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
        if agent_name not in self.agent_models:
            # No specific config for this agent, use default
            return None

        agent_config = self.agent_models[agent_name]

        # Map JSON field names to ModelConfig field names
        field_mapping = {
            "model_name": "model_name",
            "api_key": "api_key",
            "base_url": "base_url",
            "temperature": "temperature",
            "max_tokens": "max_tokens",
            "timeout": "timeout",
            "enable_thinking": "enable_thinking",
            "provider_config": "provider_config",
            "provider": "provider",
        }

        # Build ModelConfig kwargs from agent config, falling back to self defaults
        mc_kwargs: Dict[str, Any] = {
            "provider": self.llm_provider,
            "model_name": self.llm_model,
            "api_key": self.llm_api_key,
            "base_url": self.llm_base_url,
            "temperature": self.llm_temperature,
            "max_tokens": self.llm_max_tokens,
            "timeout": self.llm_timeout or 600,
            "thinking": self.llm_thinking,
            "enable_thinking": self.llm_enable_thinking,
            "provider_config": self.llm_provider_config,
        }

        # Override with agent-specific values
        for json_key, mc_key in field_mapping.items():
            if json_key in agent_config:
                value = agent_config[json_key]
                if json_key == "thinking" and isinstance(value, dict):
                    mc_kwargs[mc_key] = ThinkingConfig(**value)
                else:
                    mc_kwargs[mc_key] = value

        return ModelConfig(**mc_kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return self.model_dump()


def _get_template_config_path() -> str:
    """Get the absolute path to the template configuration file.

    Returns:
        Absolute path to the template config file.
    """
    template_path = os.path.join(os.path.dirname(__file__), _CONFIG_RELATIVE_PATH)
    return os.path.abspath(template_path)


def load_template_config() -> Dict[str, Any]:
    """Load configuration from the template file with error handling.

    Returns:
        Parsed JSON configuration contents.

    Raises:
        ConfigurationError: If the file is missing or cannot be parsed.
    """
    template_path = _get_template_config_path()

    try:
        with open(template_path, "r") as f:
            try:
                config_data = json.load(f)
                logger.info("Successfully loaded template config from %s",
                            template_path)
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
