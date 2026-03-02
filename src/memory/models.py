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


# --- Models for Agent Memory & Tasks (Merged from src/memory) ---


class MemoryType(str, Enum):
    """Types of memory storage."""
    CONVERSATION = "conversation"
    TASK = "task"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class AgentTask(BaseModel):
    """Represents a task executed by an agent (replaces TaskMemory)."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    agent_id: str
    content: str  # JSON serialized result
    status: str = "pending"
    error: Optional[str] = None
    execution_time: Optional[float] = None
    tools_used: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentState(BaseModel):
    """Represents the cached runtime state of an agent."""
    agent_id: str
    state_data: str  # JSON serialized state dict
    last_updated: datetime = Field(default_factory=datetime.now)


class AgentMessage(BaseModel):
    """Represents an inter-agent message (replaces ConversationMemory)."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    speaker: str
    recipient: str
    content: str  # JSON serialized content
    message_type: str = "default"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
