"""
Model type definitions and data structures
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel
from enum import Enum

class ModelProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    CUSTOM = "custom"

class ModelRole(str, Enum):
    """Model roles for different tasks."""
    PLANNER = "planner"
    EXECUTOR = "executor"
    TOOL_MANAGER = "tool_manager"
    MEMORY_MANAGER = "memory_manager"
    GENERAL = "general"

class ModelConfig(BaseModel):
    """Configuration for LLM models."""
    provider: ModelProvider = ModelProvider.OPENAI
    model_name: str = "gpt-4"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 2000
    timeout: int = 30
    max_retries: int = 3
    system_prompt: Optional[str] = None
    
    # Provider-specific settings
    provider_config: Dict[str, Any] = {}

class ModelResponse(BaseModel):
    """Response from LLM models."""
    content: str
    usage: Dict[str, int] = {}
    model: str
    provider: ModelProvider
    metadata: Dict[str, Any] = {}
    
    class Config:
        use_enum_values = True

class ModelQueryRequest(BaseModel):
    """Request to LLM models."""
    messages: List[Dict[str, str]]
    model_config_obj: ModelConfig  # Renamed to avoid conflict
    role: ModelRole = ModelRole.GENERAL
    
    class Config:
        use_enum_values = True