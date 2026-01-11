"""
Executor agent for task implementation and execution
"""

from typing import Any, Dict, List

from ..base import BaseAgent


class ExecutorAgent(BaseAgent):
    """Agent responsible for task implementation and execution."""

    def __init__(self, agent_id: str, memory_manager, tool_registry):
        super().__init__(
            agent_id,
            memory_manager,
            tool_registry,
            ["task_execution", "implementation", "testing", "debugging"],
        )

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task."""
        task_description = task.get("description", "")

        results = []
        execution_steps = [{
            "tool": "code_writer",
            "parameters": {
                "file_path": "./executor_demo.py",
                "content": "print('Hello from ExecutorAgent')",
                "overwrite": True,
            },
        }]
        for step in execution_steps:
            tool_name = step.get("tool")
            parameters = step.get("parameters", {})
            result = await self.tools.execute_tool(tool_name, parameters)
            results.append(result.model_dump())

        return {
            "status": "success",
            "results": results,
            "summary": f"Successfully executed task: {task_description}",
        }
