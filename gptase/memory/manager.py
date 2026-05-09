"""Thin facade over ConversationStorage.

After the L1 #15 dead-code purge, MemoryManager owns only:

- Lifecycle (initialize / close), passing through to storage.
- Agent state and working-memory upsert/lookup, with light dict<->pydantic
  conversion so callers can pass either shape.
- A get_usage() smoke probe consumed by AgentOrchestrator.get_system_status.

All other historic surface (in-memory async message queues, message-history
queries, summary builders) was unused or broken and has been removed; see
the immediately prior refactor commit for the audit.
"""

from datetime import datetime
import json
from typing import Any, Dict, Optional

from gptase.memory.models import AgentWorkingMemory
from gptase.memory.models import PersistedAgentState
from gptase.memory.storage import ConversationStorage


class MemoryManager:
    """Central memory management facade.

    Backed by ConversationStorage (SQLite). Accepts either a dict or
    pydantic config object for db_path resolution.

    Attributes:
        storage: Backend SQLite storage implementation.
        config: Optional configuration dictionary or pydantic model.
    """

    def __init__(self,
                 storage: Optional[ConversationStorage] = None,
                 config: Optional[Any] = None) -> None:
        # Generate db_path safely whether config is dict or pydantic object.
        db_path = "data/conversations.db"
        if config:
            if isinstance(config, dict):
                db_path = config.get("db_path", db_path)
            else:
                db_path = getattr(config, "db_path", db_path)

        self.storage = storage or ConversationStorage(db_path=db_path)
        self.config = config or {}

    async def initialize(self) -> None:
        """Initialize the underlying storage."""
        await self.storage.initialize()

    async def close(self) -> None:
        """Close the underlying storage connection.

        Should be called before program exit to prevent aiosqlite
        'Event loop is closed' errors.
        """
        if self.storage:
            await self.storage.close()

    async def store_agent_state(self, agent_state) -> str:
        """Store current agent state in SQLite.

        Args:
            agent_state: Agent state as dict or Pydantic BaseModel.
        """
        # Support both dict and Pydantic model inputs.
        if hasattr(agent_state, "agent_id"):
            agent_id = agent_state.agent_id
            # mode='json' is needed so pydantic models with datetime / enum
            # fields produce JSON-serializable primitives — otherwise the
            # downstream json.dumps raises TypeError.
            state_data = (agent_state.model_dump(mode="json") if hasattr(
                agent_state, "model_dump") else dict(agent_state))
        else:
            agent_id = agent_state.get("agent_id")
            state_data = agent_state

        if agent_id:
            state = PersistedAgentState(
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

    async def store_agent_working_memory(self, memory_state) -> str:
        """Store compressed working memory for an agent.

        Args:
            memory_state: AgentWorkingMemory instance or a dict that can
                be unpacked into one.
        """
        memory = (memory_state if isinstance(memory_state, AgentWorkingMemory) else
                  AgentWorkingMemory(**memory_state))
        return await self.storage.store_agent_working_memory(memory)

    async def get_agent_working_memory(self,
                                       agent_id: str) -> Optional[AgentWorkingMemory]:
        """Retrieve compressed working memory for an agent."""
        row = await self.storage.get_agent_working_memory(agent_id)
        if row is None:
            return None
        return AgentWorkingMemory(
            agent_id=row["agent_id"],
            summary=row["summary"],
            metadata=row["metadata"],
            last_updated=datetime.fromisoformat(row["last_updated"]),
        )

    async def get_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics for AgentOrchestrator.get_system_status."""
        conversations = await self.storage.list_conversations(limit=1)
        return {
            "has_conversations": len(conversations) > 0,
            "storage_type": type(self.storage).__name__,
        }
