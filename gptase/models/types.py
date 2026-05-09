"""
Model type definitions and data structures
"""

from typing import Any, Dict, List, Literal, Optional

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


class ModelConfig(BaseModel):
    """Configuration for LLM models.

    Simplified configuration — all models go through an OpenAI-compatible
    API (e.g. aiping.cn). No multi-provider abstraction needed.
    """

    model_name: str = "gpt-4"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 131072
    timeout: int = 30
    max_retries: int = 3

    # Streaming and thinking — top-level flags
    stream: bool = True
    enable_thinking: bool = Field(default=True)
    provider: Optional[Dict[str, Any]] = None


class ToolCall(BaseModel):
    """A tool call requested by the LLM.

    Attributes:
        id: Unique identifier from the LLM.
        name: Tool name (e.g., "Read", "Bash").
        arguments: Raw JSON arguments string.
    """

    id: str
    name: str
    arguments: str  # Raw JSON string from the API


class ModelResponse(BaseModel):
    """Response from LLM models."""

    content: str
    reasoning_content: Optional[str] = None
    usage: Dict[str, int] = Field(default_factory=dict)
    model: str
    provider: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Tool call support for function calling
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: Optional[str] = None  # "stop", "tool_calls", etc.


class StreamChunk(BaseModel):
    """A single chunk in a streaming response."""

    content: str = ""
    reasoning_content: str = ""
    is_thinking: bool = False
    is_complete: bool = False
    chunk_index: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)
