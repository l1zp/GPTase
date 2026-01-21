"""Pydantic models for conversation tracking."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class ConversationStatus(str, Enum):
    """Status of a conversation."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"


class MessageRole(str, Enum):
    """Message roles following OpenAI format."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Conversation(BaseModel):
    """A conversation represents one complete LLM interaction."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    model_name: str
    provider: str
    agent_id: Optional[str] = None
    status: ConversationStatus = ConversationStatus.IN_PROGRESS
    total_duration_seconds: Optional[float] = None
    estimated_cost_usd: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    """A single message in a conversation."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    role: MessageRole
    content: str
    sequence_number: int
    timestamp: datetime = Field(default_factory=datetime.now)


class Response(BaseModel):
    """LLM response with metadata."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    content: str
    reasoning_content: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_seconds: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class StreamChunk(BaseModel):
    """A single streaming chunk for real-time replay."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    response_id: str
    chunk_index: int
    content: str = ""
    reasoning_content: str = ""
    is_thinking: bool = False
    is_complete: bool = False
    timestamp: datetime = Field(default_factory=datetime.now)


class ModelParameters(BaseModel):
    """Model parameters used in a conversation."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    enable_thinking: bool = False
    system_prompt: Optional[str] = None
