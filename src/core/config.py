"""
Configuration management for the GPTase framework
"""

import json
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

from ..models.types import ModelConfig
from ..models.types import ModelRole
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
_DEFAULT_TOOL_TIMEOUT = 30
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_MEMORY_TYPE = "local"
_DEFAULT_MAX_HISTORY = 1000
_DEFAULT_PERSISTENCE_FILE = "memory_store.json"
_DEFAULT_LOG_LEVEL = "INFO"
_ENV_PREFIX = "GPTASE_"

# Environment variable names
_ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
_ENV_ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"

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


class ModelConfigExtended(ModelConfig):
    """Extended model configuration for the framework."""

    planner_config: Optional[ModelConfig] = None
    executor_config: Optional[ModelConfig] = None
    tool_manager_config: Optional[ModelConfig] = None
    memory_manager_config: Optional[ModelConfig] = None

    model_config = ConfigDict(use_enum_values=True)


class FrameworkConfig(BaseModel):
    """Main framework configuration with model support."""

    llm: ModelConfigExtended = Field(default_factory=ModelConfigExtended)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    log_level: str = Field(default=_DEFAULT_LOG_LEVEL, description="Logging level")

    model_config = ConfigDict(env_prefix=_ENV_PREFIX)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_api_key_from_env()

    def _load_api_key_from_env(self) -> None:
        """Load API key from environment variables if not already set."""
        if not self.llm.api_key:
            self.llm.api_key = os.getenv(_ENV_OPENAI_API_KEY) or os.getenv(
                _ENV_ANTHROPIC_API_KEY)

    def get_model_config_for_role(self, role: ModelRole) -> ModelConfig:
        """Get model configuration for a specific role.

        Args:
            role: The model role to get configuration for.

        Returns:
            ModelConfig for the specified role, or default config if not found.
        """
        role_configs = {
            ModelRole.PLANNER: self.llm.planner_config,
            ModelRole.EXECUTOR: self.llm.executor_config,
            ModelRole.TOOL_MANAGER: self.llm.tool_manager_config,
            ModelRole.MEMORY_MANAGER: self.llm.memory_manager_config,
        }

        return role_configs.get(role) or self.llm

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
