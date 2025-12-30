"""
Base Agent class with common functionality for all agents
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentMessage(BaseModel):
    """Standard message format for agent communication."""

    sender: str
    recipient: str
    content: Any
    message_type: str = "general"
    timestamp: datetime = None
    metadata: Dict[str, Any] = {}

    def __init__(self, **data):
        super().__init__(**data)
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AgentState(BaseModel):
    """Agent state tracking."""

    agent_id: str
    status: str = "idle"  # idle, working, waiting, error
    current_task: Optional[str] = None
    capabilities: List[str] = []
    performance_metrics: Dict[str, float] = {}


class BaseAgent(ABC):
    """Abstract base class for all agents in the framework."""

    def __init__(
        self,
        agent_id: str,
        memory_manager: MemoryManager,
        tool_registry: ToolRegistry,
        capabilities: List[str] = None,
    ):
        self.agent_id = agent_id
        self.memory = memory_manager
        self.tools = tool_registry
        self.capabilities = capabilities or []
        self.state = AgentState(agent_id=agent_id, capabilities=self.capabilities)
        self.logger = logging.getLogger(f"{__name__}.{agent_id}")

    async def send_message(
        self,
        recipient: str,
        content: Any,
        message_type: str = "general",
        metadata: Dict = None,
    ) -> None:
        """Send a message to another agent."""
        message = AgentMessage(
            sender=self.agent_id,
            recipient=recipient,
            content=content,
            message_type=message_type,
            metadata=metadata or {},
        )

        self.logger.info(f"Sending {message_type} message to {recipient}")
        await self.memory.store_message(message)

    async def receive_message(self, timeout: float = None) -> Optional[AgentMessage]:
        """Receive a message for this agent."""
        return await self.memory.get_next_message(self.agent_id, timeout)

    async def update_status(self, status: str, current_task: str = None) -> None:
        """Update agent status."""
        self.state.status = status
        if current_task:
            self.state.current_task = current_task
        self.logger.debug(f"Status updated to: {status}")

    async def record_performance(self, metric: str, value: float) -> None:
        """Record performance metrics."""
        self.state.performance_metrics[metric] = value
        await self.memory.store_agent_state(self.state)

    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task - must be implemented by each agent."""
        pass

    async def health_check(self) -> Dict[str, Any]:
        """Health check for the agent."""
        return {
            "agent_id": self.agent_id,
            "status": self.state.status,
            "capabilities": self.capabilities,
            "memory_usage": await self.memory.get_usage(),
            "timestamp": datetime.now().isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(id={self.agent_id}, status={self.state.status})"
        )

    async def shutdown(self) -> None:
        await self.update_status("idle")
