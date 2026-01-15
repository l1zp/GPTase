"""Memory Manager - Central memory management for all agents."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.memory.storage import LocalMemoryStorage
from src.memory.storage import MemoryStorage
from src.memory.types import ConversationMemory
from src.memory.types import Memory
from src.memory.types import MemoryType
from src.memory.types import TaskMemory

# Default limits and thresholds
DEFAULT_CONVERSATION_LIMIT = 50
DEFAULT_TASK_LIMIT = 20
DEFAULT_SEARCH_LIMIT = 100
DEFAULT_MAX_AGE_DAYS = 30
MAX_PREVIEW_LENGTH = 100

# Task memory ID prefix
TASK_MEMORY_PREFIX = "task"

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

    Attributes:
        storage: Backend storage implementation.
        config: Optional configuration dictionary.
        _message_queues: Async queues per agent for inter-agent messaging.
        _agent_states: Cached agent state dictionaries.
    """

    def __init__(self,
                 storage: Optional[MemoryStorage] = None,
                 config: Optional[Dict] = None) -> None:
        self.storage = storage or LocalMemoryStorage()
        self.config = config or {}
        self._message_queues: Dict[str, asyncio.Queue] = {}
        self._agent_states: Dict[str, Dict] = {}

    async def store_memory(self, memory: Memory) -> str:
        """Store any type of memory.

        Args:
            memory: Memory instance to store.

        Returns:
            ID of the stored memory.
        """
        return await self.storage.store(memory)

    async def retrieve_memory(self, memory_id: str) -> Optional[Memory]:
        """Retrieve a memory by ID.

        Args:
            memory_id: Memory identifier.

        Returns:
            Memory instance or None if not found.
        """
        return await self.storage.retrieve(memory_id)

    async def store_message(self, message: ConversationMemory) -> str:
        """Store a conversation message.

        Args:
            message: Conversation memory to store.

        Returns:
            ID of the stored message.
        """
        return await self.store_memory(message)

    async def get_conversation_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = DEFAULT_CONVERSATION_LIMIT,
        since: Optional[datetime] = None,
    ) -> List[ConversationMemory]:
        """Get conversation history for an agent.

        Args:
            agent_id: Filter by agent participation (speaker or recipient).
            limit: Maximum number of messages to return.
            since: Only return messages after this timestamp.

        Returns:
            List of conversation memories.
        """
        query = {"type": MemoryType.CONVERSATION}

        if agent_id:
            query.update({"$or": [{"speaker": agent_id}, {"recipient": agent_id}]})

        if since:
            query["after"] = since

        memories = await self.storage.search(query)
        return memories[:limit]

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
        task_memory = TaskMemory(
            id=f"{TASK_MEMORY_PREFIX}_{task_id}_{datetime.now().isoformat()}",
            task_id=task_id,
            agent_id=agent_id,
            content=result,
            status=status,
            error=error,
            execution_time=execution_time,
            tools_used=tools_used or [],
            type=MemoryType.TASK,
        )
        return await self.store_memory(task_memory)

    async def get_task_history(self,
                               agent_id: Optional[str] = None,
                               limit: int = DEFAULT_TASK_LIMIT) -> List[TaskMemory]:
        """Get task execution history.

        Args:
            agent_id: Filter by agent ID.
            limit: Maximum number of tasks to return.

        Returns:
            List of task memories.
        """
        query = {"type": MemoryType.TASK}
        if agent_id:
            query["agent_id"] = agent_id

        memories = await self.storage.search(query)
        return memories[:limit]

    async def store_agent_state(self, agent_state: Dict[str, Any]) -> None:
        """Store current agent state in cache.

        Args:
            agent_state: Agent state dictionary.
        """
        agent_id = agent_state.get("agent_id")
        if agent_id:
            self._agent_states[agent_id] = {
                **agent_state,
                "last_updated": datetime.now().isoformat(),
            }

    async def get_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get current agent state from cache.

        Args:
            agent_id: Agent identifier.

        Returns:
            Agent state dictionary or None if not found.
        """
        return self._agent_states.get(agent_id)

    async def get_next_message(
            self,
            agent_id: str,
            timeout: Optional[float] = None) -> Optional[ConversationMemory]:
        """Get the next message for an agent.

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

    async def send_message(self, recipient: str, message: ConversationMemory) -> None:
        """Send a message to an agent's queue.

        Args:
            recipient: Recipient agent ID.
            message: Message to send.
        """
        if recipient not in self._message_queues:
            self._message_queues[recipient] = asyncio.Queue()

        await self._message_queues[recipient].put(message)
        await self.store_message(message)

    async def search_memories(
        self,
        query: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        tags: Optional[List[str]] = None,
        min_importance: Optional[float] = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> List[Memory]:
        """Search across all memories.

        Args:
            query: Content search term.
            memory_type: Filter by memory type.
            tags: Filter by tags (all must match).
            min_importance: Minimum importance threshold.
            limit: Maximum results to return.

        Returns:
            List of matching memories.
        """
        search_query: Dict[str, Any] = {}

        if query:
            search_query["content_contains"] = query
        if memory_type:
            search_query["type"] = memory_type
        if tags:
            search_query["tags"] = tags
        if min_importance:
            search_query["min_importance"] = min_importance

        memories = await self.storage.search(search_query)
        return memories[:limit]

    async def get_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics.

        Returns:
            Dictionary with total count, type distribution, and size info.
        """
        all_memories = await self.storage.list_all()

        type_counts: Dict[str, int] = {}
        total_size = 0

        for memory in all_memories:
            memory_type = memory.type
            type_counts[memory_type] = type_counts.get(memory_type, 0) + 1
            total_size += len(str(memory.content))

        return {
            "total_memories": len(all_memories),
            "type_distribution": type_counts,
            "total_size_bytes": total_size,
            "storage_type": type(self.storage).__name__,
        }

    async def cleanup_old_memories(self,
                                   max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> int:
        """Clean up old, low-importance memories.

        Args:
            max_age_days: Maximum age in days for memories to keep.

        Returns:
            Number of memories deleted.
        """
        if hasattr(self.storage, "cleanup_old_memories"):
            return await self.storage.cleanup_old_memories(max_age_days)
        return 0

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
    content_str = str(content)
    if len(content_str) > MAX_PREVIEW_LENGTH:
        return content_str[:MAX_PREVIEW_LENGTH] + "..."
    return content_str
