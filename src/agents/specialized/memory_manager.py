"""Memory manager agent for memory and learning management."""

from typing import Any, Dict, List

from src.core.constants import STATUS_IDLE
from src.core.constants import STATUS_SUCCESS
from src.core.constants import STATUS_WORKING
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry

from ..base import BaseAgent

# Cleanup recommendations
CLEANUP_RECOMMENDATIONS = [
    "Archive old conversation memories",
    "Optimize task memory storage",
    "Clean up temporary memories",
]

# Capability descriptions
CAPABILITY_MEMORY_MANAGEMENT = "memory_management"
CAPABILITY_LEARNING = "learning"
CAPABILITY_SUMMARIZATION = "summarization"
CAPABILITY_ANALYSIS = "analysis"


class MemoryManagerAgent(BaseAgent):
    """Agent responsible for memory management and learning.

    The MemoryManagerAgent monitors memory usage, provides summaries,
    and offers cleanup recommendations for optimizing memory performance.

    Attributes:
        agent_id: Unique identifier for this memory manager instance.
        memory_manager: Manager for persistent storage and messaging.
        tool_registry: Registry of available tools.
    """

    def __init__(
        self,
        agent_id: str,
        memory_manager: MemoryManager,
        tool_registry: ToolRegistry,
    ) -> None:
        super().__init__(
            agent_id,
            memory_manager,
            tool_registry,
            [
                CAPABILITY_MEMORY_MANAGEMENT,
                CAPABILITY_LEARNING,
                CAPABILITY_SUMMARIZATION,
                CAPABILITY_ANALYSIS,
            ],
        )

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manage memory and learning.

        Args:
            task: Task dictionary containing at minimum a 'description' field.

        Returns:
            Dictionary with status, report, and summary.
        """
        await self.update_status(STATUS_WORKING)
        task_description = task.get("description", "")

        memory_summary = await self.memory.create_memory_summary()
        total_memories = (memory_summary.get("conversation_count", 0)
                          + memory_summary.get("task_count", 0))

        report = {
            "total_memories": total_memories,
            "recent_conversations": memory_summary.get("recent_conversations", []),
            "recent_tasks": memory_summary.get("recent_tasks", []),
            "cleanup_recommendations": CLEANUP_RECOMMENDATIONS,
        }

        await self.update_status(STATUS_IDLE)
        return {
            "status": STATUS_SUCCESS,
            "report": report,
            "summary":
            f"Managed {total_memories} memories for task: {task_description}",
        }
