"""
Memory type definitions and data structures
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class MemoryType(str, Enum):
    """Types of memory storage."""

    CONVERSATION = "conversation"
    TASK = "task"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class Memory(BaseModel):
    """Base memory structure."""

    id: str
    type: MemoryType
    content: Any
    metadata: Dict[str, Any] = {}
    timestamp: datetime = None
    importance: float = 0.5  # 0-1 scale
    tags: List[str] = []

    def __init__(self, **data):
        super().__init__(**data)
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ConversationMemory(Memory):
    """Memory for conversation history."""

    type: MemoryType = MemoryType.CONVERSATION
    speaker: str
    recipient: str
    message_type: str = "general"

    class Config:
        use_enum_values = True


class TaskMemory(Memory):
    """Memory for task execution history."""

    type: MemoryType = MemoryType.TASK
    task_id: str
    agent_id: str
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    tools_used: List[str] = []

    class Config:
        use_enum_values = True


class EpisodicMemory(Memory):
    """Memory for specific events and experiences."""

    type: MemoryType = MemoryType.EPISODIC
    event_type: str
    participants: List[str] = []
    location: Optional[str] = None
    emotions: List[str] = []

    class Config:
        use_enum_values = True


class SemanticMemory(Memory):
    """Memory for facts and knowledge."""

    type: MemoryType = MemoryType.SEMANTIC
    category: str
    confidence: float = 0.8
    source: str = "agent_learning"
    related_concepts: List[str] = []

    class Config:
        use_enum_values = True


class ProceduralMemory(Memory):
    """Memory for procedures and how-to knowledge."""

    type: MemoryType = MemoryType.PROCEDURAL
    skill_name: str
    steps: List[Dict[str, Any]] = []
    prerequisites: List[str] = []
    success_rate: float = 0.0

    class Config:
        use_enum_values = True
