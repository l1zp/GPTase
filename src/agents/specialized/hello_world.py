"""Simple hello world agent using simplified base."""

from typing import Any, Dict

from src.agents.simple import SimpleAgent
from src.models.types import ModelRole


class HelloWorldAgent(SimpleAgent):
    """Simple hello world agent using simplified base.

    Demonstrates the use of SimpleAgent for basic task processing.
    """

    def __init__(self, agent_id: str, memory_manager, tool_registry):
        """Initialize with automatic model setup.

        Args:
            agent_id: Unique agent identifier.
            memory_manager: Memory manager instance.
            tool_registry: Tool registry instance.
        """
        super().__init__(
            agent_id,
            memory_manager,
            tool_registry,
            capabilities=["hello_world"],
            model_role=ModelRole.GENERAL,
        )

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process hello world task.

        Args:
            task: Task dictionary with optional 'prompt' field.

        Returns:
            Standardized response with message from model.
        """

        async def handler(task: Dict[str, Any], agent) -> Dict[str, Any]:
            prompt = task.get("prompt") or "Hello World"
            messages = [{"role": "user", "content": prompt}]
            response = await agent.model_manager.generate(messages,
                                                          role=ModelRole.GENERAL)
            return {
                "message": response.content,
                "model": response.model,
                "provider": response.provider,
            }

        return await super().process_task_with_handler(task, handler)
