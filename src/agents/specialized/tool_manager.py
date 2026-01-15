"""Tool manager agent for resource and tool management."""

from typing import Any, Dict, List

from src.core.constants import STATUS_IDLE
from src.core.constants import STATUS_SUCCESS
from src.core.constants import STATUS_WORKING
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry

from ..base import BaseAgent

# Status values
STATUS_READY = "ready"

# Capability descriptions
CAPABILITY_TOOL_MANAGEMENT = "tool_management"
CAPABILITY_RESOURCE_OPTIMIZATION = "resource_optimization"
CAPABILITY_TROUBLESHOOTING = "troubleshooting"
CAPABILITY_INTEGRATION = "integration"


class ToolManagerAgent(BaseAgent):
    """Agent responsible for tool management and optimization.

    The ToolManagerAgent monitors available tools, reports their status,
    and provides recommendations for tool selection based on task requirements.

    Attributes:
        agent_id: Unique identifier for this tool manager instance.
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
                CAPABILITY_TOOL_MANAGEMENT,
                CAPABILITY_RESOURCE_OPTIMIZATION,
                CAPABILITY_TROUBLESHOOTING,
                CAPABILITY_INTEGRATION,
            ],
        )

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manage tools and resources.

        Args:
            task: Task dictionary containing at minimum a 'description' field.

        Returns:
            Dictionary with status, report, and summary.
        """
        await self.update_status(STATUS_WORKING)
        task_description = task.get("description", "")

        available_tools = self.tools.list_tools()
        tool_status = self._create_tool_status_dict(available_tools)
        recommendations = self._generate_recommendations(task_description,
                                                         available_tools)

        report = {
            "available_tools": available_tools,
            "tool_status": tool_status,
            "recommendations": recommendations,
        }

        await self.update_status(STATUS_IDLE)
        return {
            "status":
            STATUS_SUCCESS,
            "report":
            report,
            "summary":
            f"Analyzed {len(available_tools)} tools for task: {task_description}",
        }

    def _create_tool_status_dict(self, available_tools: List[str]) -> Dict[str, str]:
        """Create a dictionary mapping tools to their status.

        Args:
            available_tools: List of tool names.

        Returns:
            Dictionary mapping each tool to STATUS_READY.
        """
        return {tool: STATUS_READY for tool in available_tools}

    def _generate_recommendations(self, task_description: str,
                                  available_tools: List[str]) -> List[str]:
        """Generate tool recommendations based on task description.

        Args:
            task_description: Description of the task.
            available_tools: List of available tool names.

        Returns:
            List of recommendation strings for relevant tools.
        """
        recommendations = []
        task_lower = task_description.lower()

        for tool in available_tools:
            keywords = tool.split("_")
            if any(keyword in task_lower for keyword in keywords):
                recommendations.append(f"Use {tool} for {task_description}")

        return recommendations
