"""
Model type definitions and data structures
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


# Multimodal content types for vision support
class TextContent(BaseModel):
    """Text content in a multimodal message."""
    type: Literal["text"] = "text"
    text: str


class ImageUrlContent(BaseModel):
    """Image URL content in a multimodal message."""
    type: Literal["image_url"] = "image_url"
    image_url: Dict[str, str]  # {"url": "data:image/jpeg;base64,..."}


# Union type for multimodal content
MultimodalContent = Union[TextContent, ImageUrlContent, Dict[str, Any]]


class ModelProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    LOCAL = "local"


class ModelRole(str, Enum):
    """Model roles for different tasks."""

    PLANNER = "planner"
    EXECUTOR = "executor"
    TOOL_MANAGER = "tool_manager"
    MEMORY_MANAGER = "memory_manager"
    GENERAL = "general"
    VISION = "vision"
    EXTRACTION = "extraction"
    DOCUMENT_ANALYSIS = "document_analysis"


class ThinkingConfig(BaseModel):
    """Configuration for thinking/reasoning mode."""

    type: str = Field(default="disabled",
                      description="Thinking mode: 'enabled' or 'disabled'")


class ModelConfig(BaseModel):
    """Configuration for LLM models."""

    provider: str = ModelProvider.OPENAI
    model_name: str = "gpt-4"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 2000
    timeout: int = 30
    max_retries: int = 3
    system_prompt: Optional[str] = None
    persist_response: bool = False

    # Thinking mode configuration - supports both new and legacy formats
    thinking: Optional[ThinkingConfig] = Field(
        default=None, description="Thinking configuration (new format)")
    enable_thinking: bool = Field(
        default=False,
        description="Enable reasoning/thinking mode (legacy format)",
    )

    # Provider-specific settings
    provider_config: Dict[str, Any] = {}

    def is_thinking_enabled(self) -> bool:
        """Check if thinking mode is enabled.

        Checks in order:
        1. New 'thinking.type' format
        2. Legacy 'enable_thinking' format
        3. Provider config 'extra_body.enable_thinking'

        Returns:
            True if thinking mode is enabled, False otherwise.
        """
        if self.thinking is not None:
            return self.thinking.type.lower() == "enabled"
        if self.enable_thinking:
            return True
        # Check provider_config.extra_body.enable_thinking
        if self.provider_config:
            extra_body = self.provider_config.get("extra_body", {})
            return extra_body.get("enable_thinking", False)
        return False


class ModelResponse(BaseModel):
    """Response from LLM models."""

    content: str
    reasoning_content: Optional[str] = None
    usage: Dict[str, int] = Field(default_factory=dict)
    model: str
    provider: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StreamChunk(BaseModel):
    """A single chunk in a streaming response."""

    content: str = ""
    reasoning_content: str = ""
    is_thinking: bool = False
    is_complete: bool = False
    chunk_index: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)

    def save_json(
        self,
        file_path: Union[str, "os.PathLike[str]"],
        *,
        indent: int = 2,
        ensure_ascii: bool = False,
    ) -> str:
        """Save the response to a local JSON file.

        Returns the absolute file path.
        """
        import json
        from pathlib import Path

        path = Path(file_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = self.model_dump()

        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=indent, ensure_ascii=ensure_ascii)

        return str(path)
