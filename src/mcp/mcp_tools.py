"""
MCP Tools implementation for GPTase framework
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from src.agents.orchestrator import AgentOrchestrator
from src.tools.registry import CATEGORY_MCP

logger = logging.getLogger(__name__)


class MCPTools:
    """MCP Tools implementation."""

    def __init__(self, orchestrator: AgentOrchestrator):
        self.orchestrator = orchestrator

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available MCP tools."""
        # 1. Start with hardcoded system-level tasks
        mcp_tools = [
            {
                "name": "execute_task",
                "description": "Execute a task using GPTase multi-agent system",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Task description",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "default": "medium",
                        },
                    },
                    "required": ["description"],
                },
            },
            {
                "name": "get_system_status",
                "description": "Get current system status",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                },
            },
            {
                "name": "list_agents",
                "description": "List all available agents",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                },
            },
        ]

        # 2. Dynamically add tools registered with CATEGORY_MCP
        if self.orchestrator.tool_registry:
            mcp_tool_names = self.orchestrator.tool_registry.list_tools(
                category=CATEGORY_MCP)
            descriptions = self.orchestrator.tool_registry.get_tool_descriptions()

            for name in mcp_tool_names:
                if name in descriptions:
                    tool_info = descriptions[name]
                    mcp_tools.append({
                        "name": name,
                        "description": tool_info["description"],
                        "input_schema": tool_info["schema"],
                    })

        return mcp_tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool."""
        try:
            # Check hardcoded tools first
            if name == "execute_task":
                return await self._execute_task_tool(arguments)
            elif name == "get_system_status":
                return await self._get_system_status_tool(arguments)
            elif name == "list_agents":
                return await self._list_agents_tool(arguments)

            # Fallback to ToolRegistry
            if self.orchestrator.tool_registry:
                tool = self.orchestrator.tool_registry.get_tool(name)
                if tool:
                    # Verify it's actually an MCP tool (optional safety check)
                    mcp_tools = self.orchestrator.tool_registry.list_tools(
                        category=CATEGORY_MCP)
                    if name in mcp_tools:
                        result = await self.orchestrator.tool_registry.execute_tool(
                            name, arguments)
                        return {
                            "content": [{
                                "type":
                                "text",
                                "text":
                                f"Tool '{name}' execution result:\n{json.dumps(result.data, indent=2)}",
                            }]
                        }

            return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            return {"error": str(e)}

    async def _execute_task_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task tool implementation."""
        task = {
            "id": f"mcp_task_{hash(arguments.get('description', ''))}",
            "description": arguments["description"],
            "priority": arguments.get("priority", "medium"),
        }

        result = await self.orchestrator.execute_task(task)
        return {
            "content": [{
                "type":
                "text",
                "text":
                f"Task executed successfully:\n{json.dumps(result, indent=2)}",
            }]
        }

    async def _get_system_status_tool(self, arguments: Dict[str,
                                                            Any]) -> Dict[str, Any]:
        """Get system status tool implementation."""
        status = await self.orchestrator.get_system_status()
        return {
            "content": [{
                "type": "text",
                "text": f"System status:\n{json.dumps(status, indent=2)}",
            }]
        }

    async def _list_agents_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List agents tool implementation."""
        agents = await self.orchestrator.list_available_agents()
        return {
            "content": [{
                "type": "text",
                "text": f"Available agents:\n{json.dumps(agents, indent=2)}",
            }]
        }
