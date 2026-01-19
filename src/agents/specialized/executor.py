"""Executor agent for task implementation and execution."""

from typing import Any, Dict

from src.agents.base import BaseAgent
from src.core.constants import STATUS_IDLE
from src.core.constants import STATUS_SUCCESS
from src.core.constants import STATUS_WORKING
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry

# Default execution parameters
DEFAULT_DEMO_FILE_PATH = "./executor_demo.py"
DEFAULT_DEMO_CONTENT = "print('Hello from ExecutorAgent')"

# Capability descriptions
CAPABILITY_TASK_EXECUTION = "task_execution"
CAPABILITY_IMPLEMENTATION = "implementation"
CAPABILITY_TESTING = "testing"
CAPABILITY_DEBUGGING = "debugging"


class ExecutorAgent(BaseAgent):
    """Agent responsible for task implementation and execution.

    The ExecutorAgent takes planned tasks and executes them by coordinating
    with available tools. It handles code writing, execution, and result
    aggregation.

    Attributes:
        agent_id: Unique identifier for this executor instance.
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
                CAPABILITY_TASK_EXECUTION,
                CAPABILITY_IMPLEMENTATION,
                CAPABILITY_TESTING,
                CAPABILITY_DEBUGGING,
            ],
        )

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task.

        Args:
            task: Task dictionary containing at minimum a 'description' field.
                May also contain 'execution_steps' with custom steps to run.

        Returns:
            Dictionary with status, results list, and summary.
        """
        await self.update_status(STATUS_WORKING)
        task_description = task.get("description", "")

        execution_steps = task.get(
            "execution_steps",
            [
                {
                    "tool": "code_writer",
                    "parameters": {
                        "file_path": DEFAULT_DEMO_FILE_PATH,
                        "content": DEFAULT_DEMO_CONTENT,
                        "overwrite": True,
                    },
                },
            ],
        )

        results = []
        for step in execution_steps:
            tool_name = step.get("tool")
            parameters = step.get("parameters", {})
            result = await self.tools.execute_tool(tool_name, parameters)
            results.append(result.model_dump())

        await self.update_status(STATUS_IDLE)
        return {
            "status": STATUS_SUCCESS,
            "results": results,
            "summary": f"Successfully executed task: {task_description}",
        }
