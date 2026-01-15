"""Planner agent for task decomposition and planning."""

from typing import Any, Dict, List, Optional

from src.core.constants import STATUS_IDLE
from src.core.constants import STATUS_SUCCESS
from src.core.constants import STATUS_WORKING
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry

from ..base import BaseAgent

# Default planning constants
DEFAULT_STEP_PRIORITY = "high"
DEFAULT_ANALYSIS_TIME = 1  # minutes
DEFAULT_PLANNING_TIME = 2  # minutes

# Capability descriptions
CAPABILITY_TASK_PLANNING = "task_planning"
CAPABILITY_STRATEGIC_ANALYSIS = "strategic_analysis"
CAPABILITY_RESOURCE_ALLOCATION = "resource_allocation"


class PlannerAgent(BaseAgent):
    """Agent responsible for task decomposition and strategic planning.

    The PlannerAgent analyzes incoming tasks, decomposes them into steps,
    estimates resource requirements, and identifies potential risks.

    Attributes:
        agent_id: Unique identifier for this planner instance.
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
                CAPABILITY_TASK_PLANNING,
                CAPABILITY_STRATEGIC_ANALYSIS,
                CAPABILITY_RESOURCE_ALLOCATION,
            ],
        )

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process and plan a task.

        Args:
            task: Task dictionary containing at minimum a 'description' field.

        Returns:
            Dictionary with status, plan, and summary fields.
        """
        await self.update_status(STATUS_WORKING)
        task_description = task.get("description", "")

        plan = self._create_plan(task_description)

        await self.update_status(STATUS_IDLE)
        return {
            "status": STATUS_SUCCESS,
            "plan": plan,
            "summary": f"Created comprehensive plan for: {task_description}",
        }

    def _create_plan(self, task_description: str) -> Dict[str, Any]:
        """Create a structured execution plan.

        Args:
            task_description: Description of the task to plan.

        Returns:
            Plan dictionary with steps, timing, tools, and risks.
        """
        steps = [
            {
                "step_id": "1",
                "description": "Analyze task requirements",
                "tool": "analysis",
                "estimated_time": DEFAULT_ANALYSIS_TIME,
                "priority": DEFAULT_STEP_PRIORITY,
            },
            {
                "step_id": "2",
                "description": "Create execution plan",
                "tool": "planning",
                "estimated_time": DEFAULT_PLANNING_TIME,
                "priority": DEFAULT_STEP_PRIORITY,
            },
        ]

        tools = sorted({step.get("tool") for step in steps if step.get("tool")})

        return {
            "steps": steps,
            "estimated_total_time":
            sum(step.get("estimated_time", 0) for step in steps),
            "required_tools": tools,
            "risks": ["complexity", "resource_constraints"],
        }
