"""Memory type definitions and data structures."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic import ConfigDict

from gptase.utils.constants import DEFAULT_IMPORTANCE


class MemoryType(str, Enum):
    """Types of memory storage.

    Each memory type serves a different purpose in the agent system:
    - CONVERSATION: Dialog between agents or with users
    - TASK: Task execution history and results
    - EPISODIC: Specific events and experiences
    - SEMANTIC: Facts and knowledge
    - PROCEDURAL: Skills and procedures
    """

    CONVERSATION = "conversation"
    TASK = "task"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class Memory(BaseModel):
    """Base memory structure.

    All memory types inherit from this base class which provides
    common fields like ID, type, content, timestamp, and importance.

    Attributes:
        id: Unique memory identifier.
        type: Memory type from MemoryType enum.
        content: Memory payload (can be any type).
        metadata: Additional contextual information.
        timestamp: When the memory was created (auto-set if None).
        importance: Importance score from 0 to 1.
        tags: List of tags for categorization and search.
    """

    id: str
    type: MemoryType
    content: Any
    metadata: Dict[str, Any] = {}
    timestamp: Optional[datetime] = None
    importance: float = DEFAULT_IMPORTANCE
    tags: List[str] = []

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.timestamp is None:
            self.timestamp = datetime.now()
