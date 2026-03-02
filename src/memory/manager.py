import asyncio
from datetime import datetime
import json
from typing import Any, Dict, List, Optional

from src.memory.models import AgentMessage
from src.memory.models import AgentState
from src.memory.models import AgentTask
from src.memory.storage import ConversationStorage

# Default limits and thresholds
DEFAULT_CONVERSATION_LIMIT = 50
DEFAULT_TASK_LIMIT = 20
DEFAULT_SEARCH_LIMIT = 100
DEFAULT_MAX_AGE_DAYS = 30
MAX_PREVIEW_LENGTH = 100

# Summary limits
SUMMARY_CONVERSATION_LIMIT_AGENT = 100
SUMMARY_TASK_LIMIT_AGENT = 50
SUMMARY_CONVERSATION_LIMIT_GLOBAL = 50
SUMMARY_TASK_LIMIT_GLOBAL = 25
SUMMARY_RECENT_COUNT = 5


class MemoryManager:
    """Central memory management system for all agents.

    The MemoryManager provides a unified interface for storing, retrieving,
    and searching memories. It handles conversation messages, task results,
    agent states, and provides message passing between agents.

    Now backed by ConversationStorage (SQLite) instead of JSON files.

    Attributes:
        storage: Backend SQLite storage implementation.
        config: Optional configuration dictionary.
        _message_queues: Async queues per agent for inter-agent messaging.
    """

    def __init__(self,
                 storage: Optional[ConversationStorage] = None,
                 config: Optional[Any] = None) -> None:
        # Generate db_path safely whether config is dict or pydantic object
        db_path = "data/conversations.db"
        if config:
            if isinstance(config, dict):
                db_path = config.get("db_path", db_path)
            else:
                db_path = getattr(config, "db_path", db_path)

        self.storage = storage or ConversationStorage(db_path=db_path)
        self.config = config or {}
        self._message_queues: Dict[str, asyncio.Queue] = {}
        # agent_states are now persisted in SQLite, no longer cached in memory here

    async def initialize(self) -> None:
        """Initialize the underlying storage."""
        await self.storage.initialize()

    async def store_message(self, message: AgentMessage) -> str:
        """Store a conversation message.

        Args:
            message: AgentMessage to store.

        Returns:
            ID of the stored message.
        """
        return await self.storage.store_agent_message(message)

    async def get_conversation_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = DEFAULT_CONVERSATION_LIMIT,
        since: Optional[datetime] = None,
    ) -> List[AgentMessage]:
        """Get conversation history for an agent.

        Args:
            agent_id: Filter by agent participation (speaker or recipient).
            limit: Maximum number of messages to return.
            since: Only return messages after this timestamp.

        Returns:
            List of conversation messages.
        """
        raw_msgs = await self.storage.get_agent_messages(agent_id=agent_id,
                                                         limit=limit,
                                                         since=since)
        # Convert dictionary rows back to AgentMessage objects
        messages = []
        for row in raw_msgs:
            # Parse timestamp back to datetime
            ts = datetime.fromisoformat(row["timestamp"])
            messages.append(
                AgentMessage(
                    id=row["id"],
                    speaker=row["speaker"],
                    recipient=row["recipient"],
                    content=row["content"],
                    message_type=row["message_type"],
                    metadata=row["metadata"],
                    timestamp=ts,
                ))
        return messages

    async def store_task_result(
        self,
        task_id: str,
        agent_id: str,
        result: Any,
        status: str = "completed",
        error: Optional[str] = None,
        execution_time: Optional[float] = None,
        tools_used: Optional[List[str]] = None,
    ) -> str:
        """Store task execution result.

        Args:
            task_id: Task identifier.
            agent_id: Agent that executed the task.
            result: Task result content.
            status: Task status (completed, failed, etc.).
            error: Error message if status is failed.
            execution_time: Execution time in seconds.
            tools_used: List of tools used during execution.

        Returns:
            ID of the stored task memory.
        """
        # Ensure result is stringifiable if it isn't already
        content_str = json.dumps(result) if not isinstance(result, str) else result

        task = AgentTask(
            task_id=task_id,
            agent_id=agent_id,
            content=content_str,
            status=status,
            error=error,
            execution_time=execution_time,
            tools_used=tools_used or [],
        )
        return await self.storage.store_agent_task(task)

    async def get_task_history(self,
                               agent_id: Optional[str] = None,
                               limit: int = DEFAULT_TASK_LIMIT) -> List[AgentTask]:
        """Get task execution history.

        Args:
            agent_id: Filter by agent ID.
            limit: Maximum number of tasks to return.

        Returns:
            List of agent tasks.
        """
        raw_tasks = await self.storage.get_agent_tasks(agent_id=agent_id, limit=limit)
        tasks = []
        for row in raw_tasks:
            ts = datetime.fromisoformat(row["timestamp"])
            tasks.append(
                AgentTask(
                    id=row["id"],
                    task_id=row["task_id"],
                    agent_id=row["agent_id"],
                    content=row["content"],
                    status=row["status"],
                    error=row["error"],
                    execution_time=row["execution_time"],
                    tools_used=row["tools_used"],
                    timestamp=ts,
                ))
        return tasks

    async def store_agent_state(self, agent_state) -> str:
        """Store current agent state in SQLite.

        Args:
            agent_state: Agent state as dict or Pydantic BaseModel (AgentState).
        """
        # Support both dict and Pydantic model inputs
        if hasattr(agent_state, "agent_id"):
            agent_id = agent_state.agent_id
            state_data = (agent_state.model_dump() if hasattr(
                agent_state, "model_dump") else dict(agent_state))
        else:
            agent_id = agent_state.get("agent_id")
            state_data = agent_state

        if agent_id:
            state = AgentState(
                agent_id=agent_id,
                state_data=json.dumps(state_data),
            )
            return await self.storage.store_agent_state(state)
        return ""

    async def get_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get current agent state from SQLite.

        Args:
            agent_id: Agent identifier.

        Returns:
            Agent state dictionary or None if not found.
        """
        return await self.storage.get_agent_state(agent_id)

    async def get_next_message(
            self,
            agent_id: str,
            timeout: Optional[float] = None) -> Optional[AgentMessage]:
        """Get the next message for an agent from memory queue.

        Args:
            agent_id: Agent identifier.
            timeout: Maximum time to wait in seconds.

        Returns:
            Next message or None if timeout expires.
        """
        if agent_id not in self._message_queues:
            self._message_queues[agent_id] = asyncio.Queue()

        try:
            if timeout:
                message = await asyncio.wait_for(self._message_queues[agent_id].get(),
                                                 timeout=timeout)
            else:
                message = await self._message_queues[agent_id].get()
            return message
        except asyncio.TimeoutError:
            return None

    async def send_message(self, recipient: str, message: AgentMessage) -> None:
        """Send a message to an agent's queue.

        Args:
            recipient: Recipient agent ID.
            message: Message to send.
        """
        if recipient not in self._message_queues:
            self._message_queues[recipient] = asyncio.Queue()

        await self._message_queues[recipient].put(message)
        await self.store_message(message)

    async def get_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics.

        Returns:
            Dictionary with total count info.
        """
        # Simple proxy statistics since we moved everything to SQLite
        conversations = await self.storage.list_conversations(limit=1)
        tasks = await self.storage.get_agent_tasks(limit=1)

        return {
            "has_conversations": len(conversations) > 0,
            "has_tasks": len(tasks) > 0,
            "storage_type": type(self.storage).__name__,
        }

    async def create_memory_summary(self,
                                    agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a summary of memories for an agent or overall.

        Args:
            agent_id: Optional agent ID to filter by.

        Returns:
            Dictionary with counts and recent entries.
        """
        if agent_id:
            conversation_limit = SUMMARY_CONVERSATION_LIMIT_AGENT
            task_limit = SUMMARY_TASK_LIMIT_AGENT
            conversation_history = await self.get_conversation_history(
                agent_id, limit=conversation_limit)
            task_history = await self.get_task_history(agent_id, limit=task_limit)
        else:
            conversation_limit = SUMMARY_CONVERSATION_LIMIT_GLOBAL
            task_limit = SUMMARY_TASK_LIMIT_GLOBAL
            conversation_history = await self.get_conversation_history(
                limit=conversation_limit)
            task_history = await self.get_task_history(limit=task_limit)

        return {
            "conversation_count":
            len(conversation_history),
            "task_count":
            len(task_history),
            "recent_conversations": [{
                "speaker": msg.speaker,
                "type": msg.message_type,
                "preview": _preview_content(msg.content),
                "timestamp": msg.timestamp.isoformat(),
            } for msg in conversation_history[:SUMMARY_RECENT_COUNT]],
            "recent_tasks": [{
                "task_id": task.task_id,
                "status": task.status,
                "execution_time": task.execution_time,
                "tools_used": task.tools_used,
            } for task in task_history[:SUMMARY_RECENT_COUNT]],
        }


def _preview_content(content: Any) -> str:
    """Create a preview string from content.

    Args:
        content: Content to preview.

    Returns:
        Preview string with ellipsis if truncated.
    """
    content_str = str(content) if not isinstance(content, dict) else json.dumps(content)
    if len(content_str) > MAX_PREVIEW_LENGTH:
        return content_str[:MAX_PREVIEW_LENGTH] + "..."
    return content_str
