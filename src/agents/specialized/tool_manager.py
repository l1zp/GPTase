"""
Tool manager agent for resource and tool management
"""

from typing import Dict, Any, List
from ..base import BaseAgent

class ToolManagerAgent(BaseAgent):
    """Agent responsible for tool management and optimization."""
    
    def __init__(self, agent_id: str, memory_manager, tool_registry):
        super().__init__(agent_id, memory_manager, tool_registry, ["tool_management", "resource_optimization", "troubleshooting", "integration"])
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manage tools and resources."""
        task_description = task.get("description", "")
        
        available_tools = self.tools.list_tools()
        
        report = {
            "available_tools": available_tools,
            "tool_status": {tool: "ready" for tool in available_tools},
            "recommendations": [
                f"Use {tool} for {task_description}"
                for tool in available_tools 
                if any(keyword in task_description.lower() for keyword in tool.split('_'))
            ]
        }
        
        return {
            "status": "success",
            "report": report,
            "summary": f"Analyzed {len(available_tools)} tools for task: {task_description}"
        }
