"""
Memory Manager - Central memory management for all agents
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.memory.storage import LocalMemoryStorage, MemoryStorage
from src.memory.types import ConversationMemory, Memory, MemoryType, TaskMemory


class MemoryManager:
    """Central memory management system for all agents."""

    def __init__(self, storage: MemoryStorage = None, config: Dict = None):
        self.storage = storage or LocalMemoryStorage()
        self.config = config or {}
        self._message_queues: Dict[str, asyncio.Queue] = {}
        self._agent_states: Dict[str, Dict] = {}

    async def store_memory(self, memory: Memory) -> str:
        """Store any type of memory."""
        return await self.storage.store(memory)

    async def retrieve_memory(self, memory_id: str) -> Optional[Memory]:
        """Retrieve a memory by ID."""
        return await self.storage.retrieve(memory_id)

    async def store_message(self, message: ConversationMemory) -> str:
        """Store a conversation message."""
        return await self.store_memory(message)

    async def get_conversation_history(
        self, agent_id: str = None, limit: int = 50, since: datetime = None
    ) -> List[ConversationMemory]:
        """Get conversation history for an agent."""
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
        error: str = None,
        execution_time: float = None,
        tools_used: List[str] = None,
    ) -> str:
        """Store task execution result."""
        task_memory = TaskMemory(
            id=f"task_{task_id}_{datetime.now().isoformat()}",
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

    async def get_task_history(
        self, agent_id: str = None, limit: int = 20
    ) -> List[TaskMemory]:
        """Get task execution history."""
        query = {"type": MemoryType.TASK}
        if agent_id:
            query["agent_id"] = agent_id

        memories = await self.storage.search(query)
        return memories[:limit]

    async def store_agent_state(self, agent_state: Dict[str, Any]) -> None:
        """Store current agent state."""
        agent_id = agent_state.get("agent_id")
        if agent_id:
            self._agent_states[agent_id] = {
                **agent_state,
                "last_updated": datetime.now().isoformat(),
            }

    async def get_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get current agent state."""
        return self._agent_states.get(agent_id)

    async def get_next_message(
        self, agent_id: str, timeout: float = None
    ) -> Optional[ConversationMemory]:
        """Get the next message for an agent."""
        if agent_id not in self._message_queues:
            self._message_queues[agent_id] = asyncio.Queue()

        try:
            if timeout:
                message = await asyncio.wait_for(
                    self._message_queues[agent_id].get(), timeout=timeout
                )
            else:
                message = await self._message_queues[agent_id].get()
            return message
        except asyncio.TimeoutError:
            return None

    async def send_message(self, recipient: str, message: ConversationMemory) -> None:
        """Send a message to an agent's queue."""
        if recipient not in self._message_queues:
            self._message_queues[recipient] = asyncio.Queue()

        await self._message_queues[recipient].put(message)
        await self.store_message(message)

    async def search_memories(
        self,
        query: str = None,
        memory_type: MemoryType = None,
        tags: List[str] = None,
        min_importance: float = None,
        limit: int = 100,
    ) -> List[Memory]:
        """Search across all memories."""
        search_query = {}

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
        """Get memory usage statistics."""
        all_memories = await self.storage.list_all()

        type_counts = {}
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

    async def cleanup_old_memories(self, max_age_days: int = 30) -> int:
        """Clean up old, low-importance memories."""
        if hasattr(self.storage, "cleanup_old_memories"):
            return await self.storage.cleanup_old_memories(max_age_days)
        return 0

    async def create_memory_summary(self, agent_id: str = None) -> Dict[str, Any]:
        """Create a summary of memories for an agent or overall."""
        if agent_id:
            conversation_history = await self.get_conversation_history(
                agent_id, limit=100
            )
            task_history = await self.get_task_history(agent_id, limit=50)
        else:
            conversation_history = await self.get_conversation_history(limit=50)
            task_history = await self.get_task_history(limit=25)

        return {
            "conversation_count": len(conversation_history),
            "task_count": len(task_history),
            "recent_conversations": [
                {
                    "speaker": msg.speaker,
                    "type": msg.message_type,
                    "preview": (
                        str(msg.content)[:100] + "..."
                        if len(str(msg.content)) > 100
                        else str(msg.content)
                    ),
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in conversation_history[:5]
            ],
            "recent_tasks": [
                {
                    "task_id": task.task_id,
                    "status": task.status,
                    "execution_time": task.execution_time,
                    "tools_used": task.tools_used,
                }
                for task in task_history[:5]
            ],
        }
