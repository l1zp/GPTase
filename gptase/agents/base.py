"""Base Agent class with common functionality for all agents."""

from abc import ABC
from abc import abstractmethod
import asyncio
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from gptase.core.constants import DEFAULT_MESSAGE_TIMEOUT
from gptase.core.constants import DEFAULT_MESSAGE_TYPE
from gptase.core.constants import STATUS_ERROR
from gptase.core.constants import STATUS_IDLE
from gptase.memory.manager import MemoryManager

logger = logging.getLogger(__name__)


class AgentMessage(BaseModel):
    """Standard message format for agent communication.

    Attributes:
        sender: ID of the sending agent.
        recipient: ID of the receiving agent.
        content: Message payload (can be any type).
        message_type: Type of message (default: DEFAULT_MESSAGE_TYPE).
        timestamp: When the message was created (auto-set if not provided).
        metadata: Additional contextual information.
    """

    sender: str
    recipient: str
    content: Any
    message_type: str = DEFAULT_MESSAGE_TYPE
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = {}

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AgentState(BaseModel):
    """Agent state tracking.

    Attributes:
        agent_id: Unique identifier for the agent.
        status: Current agent status (one of STATUS_* constants).
        current_task: Description of the current task being processed.
        capabilities: List of agent capabilities/skills.
        performance_metrics: Dictionary of performance metric names to values.
    """

    agent_id: str
    status: str = STATUS_IDLE
    current_task: Optional[str] = None
    capabilities: List[str] = []
    performance_metrics: Dict[str, float] = {}


class BaseAgent(ABC):
    """Abstract base class for all agents in the framework.

    BaseAgent provides common functionality for message passing, state management,
    health checks, and performance tracking. Subclasses must implement the
    process_task method to define their specific behavior.

    Attributes:
        AGENT_NAME: Class attribute declaring the agent's name for model config lookup.
        agent_id: Unique identifier for this agent instance.
        memory: MemoryManager for persistent storage and messaging.
        model_manager: ModelManager instance for LLM operations.
        capabilities: List of capability descriptions for this agent.
        state: Current agent state (status, metrics, etc.).
        logger: Logger instance specific to this agent.
    """

    # Subclasses should override this to declare their agent name
    AGENT_NAME: Optional[str] = None

    def __init__(
        self,
        agent_id: str,
        memory_manager: MemoryManager,
        model_manager=None,
        capabilities: Optional[List[str]] = None,
    ) -> None:
        self.agent_id = agent_id
        self.memory = memory_manager
        self.model_manager = model_manager
        self.capabilities = capabilities or []
        self.state = AgentState(agent_id=agent_id, capabilities=self.capabilities)
        self.logger = logging.getLogger(f"{__name__}.{agent_id}")

    async def send_message(
        self,
        recipient: str,
        content: Any,
        message_type: str = DEFAULT_MESSAGE_TYPE,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a message to another agent.

        Args:
            recipient: ID of the agent to receive the message.
            content: Message payload.
            message_type: Type of message for routing/filtering.
            metadata: Optional additional context.
        """
        message = AgentMessage(
            sender=self.agent_id,
            recipient=recipient,
            content=content,
            message_type=message_type,
            metadata=metadata or {},
        )

        self.logger.info("Sending %s message to %s", message_type, recipient)
        await self.memory.store_message(message)

    async def receive_message(self,
                              timeout: float = DEFAULT_MESSAGE_TIMEOUT
                              ) -> Optional[AgentMessage]:
        """Receive a message for this agent.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            The received AgentMessage or None if timeout expires.
        """
        return await self.memory.get_next_message(self.agent_id, timeout)

    async def update_status(self,
                            status: str,
                            current_task: Optional[str] = None) -> None:
        """Update agent status.

        Args:
            status: New status value (should be one of STATUS_* constants).
            current_task: Optional description of current task.
        """
        self.state.status = status
        if current_task is not None:
            self.state.current_task = current_task
        self.logger.debug("Status updated to: %s", status)

    async def record_performance(self, metric: str, value: float) -> None:
        """Record a performance metric.

        Args:
            metric: Name of the metric (e.g., "tasks_completed").
            value: Numeric value to record.
        """
        self.state.performance_metrics[metric] = value
        await self.memory.store_agent_state(self.state)

    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task - must be implemented by each agent.

        Args:
            task: Task specification as a dictionary.

        Returns:
            Task result as a dictionary.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check for the agent.

        Returns:
            Dictionary containing agent_id, status, capabilities, memory_usage,
            and current timestamp.
        """
        return {
            "agent_id": self.agent_id,
            "status": self.state.status,
            "capabilities": self.capabilities,
            "memory_usage": await self.memory.get_usage(),
            "timestamp": datetime.now().isoformat(),
        }

    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return (
            f"{self.__class__.__name__}(id={self.agent_id}, status={self.state.status})"
        )

    async def shutdown(self) -> None:
        """Clean up resources before shutdown.

        Sets agent status to idle. Subclasses may override to perform
        additional cleanup.
        """
        self.state.status = STATUS_IDLE
        self.state.current_task = None
