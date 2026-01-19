"""Simplified agent base for lightweight, stateless agents.

This module provides SimpleAgent, a lightweight alternative to BaseAgent
for simple use cases where the full complexity of BaseAgent is not needed.
SimpleAgent provides automatic model manager initialization and simplified
task processing with automatic status management.
"""

from typing import Any, Callable, Dict, List, Optional

from src.agents.base import BaseAgent
from src.core.constants import STATUS_COMPLETED
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_PROCESSING
from src.core.response_utils import create_error_response
from src.core.response_utils import create_success_response
from src.models.model import Model
from src.models.types import ModelRole
from src.utils import get_model_for_role


class SimpleAgent(BaseAgent):
    """Lightweight agent for simple, stateless operations.

    Provides automatic model manager initialization and simplified task
    processing with automatic status management. Ideal for agents that
    primarily process tasks and return results without complex state
    management or inter-agent communication.

    Attributes:
        agent_id: Unique agent identifier.
        model_manager: Auto-configured model manager.
    """

    def __init__(
        self,
        agent_id: str,
        memory_manager,
        tool_registry,
        capabilities: Optional[List[str]] = None,
        model_role: ModelRole = ModelRole.GENERAL,
    ):
        """Initialize with automatic model setup.

        Args:
            agent_id: Unique agent identifier.
            memory_manager: Memory manager instance.
            tool_registry: Tool registry instance.
            capabilities: Optional list of agent capabilities.
            model_role: Role for model configuration (PLANNER, EXECUTOR, etc.)
        """
        super().__init__(agent_id, memory_manager, tool_registry, capabilities)
        self.model_manager = get_model_for_role(model_role)

    async def process_task_with_handler(
        self,
        task: Dict[str, Any],
        handler: Callable,
        task_key: str = "description",
    ) -> Dict[str, Any]:
        """Process task with automatic status management.

        Handles all status updates, error responses, and success responses
        automatically. Subclasses only need to provide a handler function
        that processes the task and returns a result.

        Args:
            task: Task dictionary.
            handler: Async function that takes (task, agent) and returns result.
                Should be of the form: async def handler(task: Dict, agent: SimpleAgent) -> Any
            task_key: Key to extract from task for status updates (default: "description").

        Returns:
            Standardized response dictionary with status, data/error, agent_id.

        Example:
            class MyAgent(SimpleAgent):
                async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
                    async def handler(task, agent):
                        response = await agent.model_manager.generate(messages)
                        return {"message": response.content}
                    return await super().process_task_with_handler(task, handler)
        """
        task_id = task.get("id") or task.get(task_key, "unknown")

        try:
            await self.update_status(STATUS_PROCESSING, task_id)
            result = await handler(task, self)
            await self.update_status(STATUS_COMPLETED, task_id)
            return create_success_response(
                data=result,
                agent_id=self.agent_id,
                summary=f"Completed task: {task_id}",
            )
        except Exception as e:
            await self.update_status(STATUS_ERROR, task_id)
            return create_error_response(
                error=str(e),
                agent_id=self.agent_id,
                task_id=task_id,
            )
