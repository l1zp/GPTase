"""Memory type definitions and data structures."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic import ConfigDict

from gptase.core.constants import DEFAULT_IMPORTANCE
from gptase.core.constants import DEFAULT_MESSAGE_TYPE
from gptase.core.constants import DEFAULT_SEMANTIC_CONFIDENCE

# Default learning source
DEFAULT_LEARNING_SOURCE = "agent_learning"


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


class ConversationMemory(Memory):
    """Memory for conversation history between agents.

    Tracks messages sent between agents including speaker,
    recipient, and message type.

    Attributes:
        type: Fixed to CONVERSATION.
        speaker: ID of the message sender.
        recipient: ID of the message recipient.
        message_type: Type of message (default, request, etc.).
    """

    type: MemoryType = MemoryType.CONVERSATION
    speaker: str
    recipient: str
    message_type: str = DEFAULT_MESSAGE_TYPE

    model_config = ConfigDict(use_enum_values=True)


class TaskMemory(Memory):
    """Memory for task execution history.

    Records task execution including status, results,
    execution time, and tools used.

    Attributes:
        type: Fixed to TASK.
        task_id: Task identifier.
        agent_id: Agent that executed the task.
        status: Task status (pending, in_progress, completed, failed).
        result: Task result content (alias for content).
        error: Error message if status is failed.
        execution_time: Execution time in seconds.
        tools_used: List of tools used during execution.
    """

    type: MemoryType = MemoryType.TASK
    task_id: str
    agent_id: str
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    tools_used: List[str] = []

    model_config = ConfigDict(use_enum_values=True)


class EpisodicMemory(Memory):
    """Memory for specific events and experiences.

    Stores episodic memories about specific events with
    participants, location, and emotional context.

    Attributes:
        type: Fixed to EPISODIC.
        event_type: Type of event.
        participants: List of agent IDs involved.
        location: Optional location description.
        emotions: List of emotion tags.
    """

    type: MemoryType = MemoryType.EPISODIC
    event_type: str
    participants: List[str] = []
    location: Optional[str] = None
    emotions: List[str] = []

    model_config = ConfigDict(use_enum_values=True)


class SemanticMemory(Memory):
    """Memory for facts and knowledge.

    Stores semantic knowledge with confidence scoring
    and source attribution.

    Attributes:
        type: Fixed to SEMANTIC.
        category: Knowledge category.
        confidence: Confidence in the knowledge (0-1).
        source: Source of the knowledge.
        related_concepts: List of related concept IDs.
    """

    type: MemoryType = MemoryType.SEMANTIC
    category: str
    confidence: float = DEFAULT_SEMANTIC_CONFIDENCE
    source: str = DEFAULT_LEARNING_SOURCE
    related_concepts: List[str] = []

    model_config = ConfigDict(use_enum_values=True)


class ProceduralMemory(Memory):
    """Memory for procedures and how-to knowledge.

    Stores procedural knowledge with steps, prerequisites,
    and success rate tracking.

    Attributes:
        type: Fixed to PROCEDURAL.
        skill_name: Name of the skill/procedure.
        steps: List of procedure steps.
        prerequisites: Required skills or conditions.
        success_rate: Historical success rate (0-1).
    """

    type: MemoryType = MemoryType.PROCEDURAL
    skill_name: str
    steps: List[Dict[str, Any]] = []
    prerequisites: List[str] = []
    success_rate: float = 0.0

    model_config = ConfigDict(use_enum_values=True)
