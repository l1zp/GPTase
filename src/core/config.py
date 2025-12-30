"""
Configuration management for the GPTase framework
"""

import json
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from ..models.types import ModelConfig, ModelRole
from .exceptions import ConfigurationError
from .logging import logger, setup_logging

load_dotenv()
setup_logging()


class LLMConfig(BaseModel):
    """Configuration for LLM providers."""

    provider: str = Field(default="openai", description="LLM provider")
    model: str = Field(default="gpt-4", description="Model name")
    api_key: Optional[str] = Field(default=None, description="API key")
    base_url: Optional[str] = Field(default=None, description="Base URL for API")
    temperature: float = Field(default=0.1, description="Temperature for generation")
    max_tokens: int = Field(default=2000, description="Maximum tokens to generate")


class MemoryConfig(BaseModel):
    """Configuration for memory systems."""

    type: str = Field(default="local", description="Memory storage type")
    max_history: int = Field(default=1000, description="Maximum history entries")
    persistence_file: str = Field(
        default="memory_store.json", description="File for persistent storage"
    )


class ToolConfig(BaseModel):
    """Configuration for tool systems."""

    timeout: int = Field(default=30, description="Tool execution timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    sandbox_enabled: bool = Field(default=True, description="Enable code sandboxing")


class ModelConfigExtended(ModelConfig):
    """Extended model configuration for the framework."""

    # Role-specific configurations
    planner_config: Optional[ModelConfig] = None
    executor_config: Optional[ModelConfig] = None
    tool_manager_config: Optional[ModelConfig] = None
    memory_manager_config: Optional[ModelConfig] = None

    class Config:
        use_enum_values = True


class FrameworkConfig(BaseModel):
    """Main framework configuration with model support."""

    llm: ModelConfigExtended = Field(default_factory=ModelConfigExtended)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    log_level: str = Field(default="INFO", description="Logging level")

    class Config:
        env_prefix = "GPTASE_"  # GPTase Framework

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load from environment variables
        if not self.llm.api_key:
            self.llm.api_key = os.getenv("OPENAI_API_KEY") or os.getenv(
                "ANTHROPIC_API_KEY"
            )

    def get_model_config_for_role(self, role: ModelRole) -> ModelConfig:
        """Get model configuration for a specific role."""
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


def load_template_config() -> Dict[str, Any]:
    """Load configuration from the template file with error handling.

    Returns:
        Dict[str, Any]: Parsed JSON configuration contents.
    """
    template_path = os.path.join(
        os.path.dirname(__file__), "../../config/llm_config.template.json"
    )
    template_path = os.path.abspath(template_path)

    try:
        with open(template_path, "r") as f:
            try:
                config_data = json.load(f)
                logger.info(f"Successfully loaded template config from {template_path}")
                return config_data
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error in template config: {str(e)}")
                raise ConfigurationError(
                    f"Invalid template config format: {str(e)}"
                ) from e
    except FileNotFoundError:
        logger.error(f"Template config file not found at {template_path}")
        raise ConfigurationError(
            f"Template config file missing: {template_path}"
        ) from None
    except Exception as e:
        logger.error(f"Unexpected error loading template config: {str(e)}")
        raise ConfigurationError(f"Failed to load template config: {str(e)}") from e
