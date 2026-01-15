"""
Model type definitions and data structures
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class ModelProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class ModelRole(str, Enum):
    """Model roles for different tasks."""

    PLANNER = "planner"
    EXECUTOR = "executor"
    TOOL_MANAGER = "tool_manager"
    MEMORY_MANAGER = "memory_manager"
    GENERAL = "general"


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

    # Provider-specific settings
    provider_config: Dict[str, Any] = {}


class ModelResponse(BaseModel):
    """Response from LLM models."""

    content: str
    reasoning_content: Optional[str] = None
    usage: Dict[str, int] = Field(default_factory=dict)
    model: str
    provider: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

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

        # Pydantic v2: model_dump(); v1: dict()
        if hasattr(self, "model_dump"):
            payload = self.model_dump()  # type: ignore[attr-defined]
        else:
            payload = self.dict()  # type: ignore[call-arg]

        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=indent, ensure_ascii=ensure_ascii)

        return str(path)

    model_config = ConfigDict(use_enum_values=True)
