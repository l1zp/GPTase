"""Pydantic models for conversation tracking."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel
from pydantic import Field


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


class ExtractionSessionStatus(str, Enum):
    """Status of an extraction session."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ExtractionStepStatus(str, Enum):
    """Status of an extraction step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionSession(BaseModel):
    """An extraction session groups related LLM calls into a workflow."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    document_path: str
    extraction_type: str
    agent_id: str
    status: ExtractionSessionStatus = ExtractionSessionStatus.IN_PROGRESS
    total_llm_calls: int = 0
    phase: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class ExtractionSessionStep(BaseModel):
    """A step within an extraction session."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    step_name: str
    step_phase: str
    conversation_id: Optional[str] = None
    status: ExtractionStepStatus = ExtractionStepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    step_order: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Final extracted result for a session."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    result_type: str
    content: str
    created_at: datetime = Field(default_factory=datetime.now)


class PersistedAgentState(BaseModel):
    """Represents the cached runtime state of an agent persisted to SQLite.

    Renamed from AgentState to avoid collision with
    gptase.agents.base.AgentState (in-memory runtime state).
    """
    agent_id: str
    state_data: str  # JSON serialized state dict
    last_updated: datetime = Field(default_factory=datetime.now)


class AgentMessage(BaseModel):
    """Represents an inter-agent message.

    Unified model used by both agents (BaseAgent.send_message) and
    memory storage (ConversationStorage.store_agent_message).
    Field 'sender' is used consistently (was 'speaker' in storage layer).
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    sender: str
    recipient: str
    content: Any  # Message payload (can be any type)
    message_type: str = "default"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[datetime] = None

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AgentWorkingMemory(BaseModel):
    """Persistent working memory summary for a named agent."""

    agent_id: str
    summary: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.now)
