"""
FastAPI application for the multi-agent framework web interface
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig
from src.mcp.tools import MCPTools


class GPTaseMCPServer:
    """Main FastAPI application for the web interface."""

    def __init__(self, config: Optional[FrameworkConfig] = None):
        self.config = config or FrameworkConfig()
        self.orchestrator = AgentOrchestrator(self.config)
        self.tools = MCPTools(self.orchestrator)

    async def initialize(self) -> Dict[str, Any]:
        """Initialize the MCP server."""
        return {
            "protocol_version": "2024-11-05",
            "capabilities": {
                "tools": {
                    "list_changed": True,
                    "subscribe": True
                },
                "prompts": {
                    "list_changed": True,
                    "subscribe": True
                },
                "resources": {
                    "list_changed": True,
                    "subscribe": True
                },
            },
            "server_info": {
                "name": "gptase-mcp",
                "version": "1.0.0",
                "description": "GPTase Multi-Agent Framework MCP Server",
            },
        }

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Get available MCP tools."""
        return await self.tools.list_tools()

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool."""
        return await self.tools.call_tool(name, arguments)

    async def list_prompts(self) -> List[Dict[str, Any]]:
        """List available MCP prompts."""
        return [
            {
                "name":
                "analyze_task",
                "description":
                "Analyze and plan a task using GPTase agents",
                "arguments": [{
                    "name": "task_description",
                    "description": "Description of the task to analyze",
                    "required": True,
                }],
            },
            {
                "name": "get_system_status",
                "description": "Get current system status",
                "arguments": [],
            },
        ]

    async def get_prompt(self,
                         name: str,
                         arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get an MCP prompt."""
        if name == "analyze_task":
            return await self._analyze_task_prompt(arguments or {})
        elif name == "get_system_status":
            return await self._system_status_prompt()
        else:
            return {"error": f"Unknown prompt: {name}"}

    async def list_resources(self) -> List[Dict[str, Any]]:
        """List available MCP resources."""
        return [
            {
                "uri": "agent://status",
                "name": "Agent Status",
                "description": "Current status of all agents",
            },
            {
                "uri": "memory://summary",
                "name": "Memory Summary",
                "description": "Summary of memory usage",
            },
        ]

    async def get_resource(self, uri: str) -> Dict[str, Any]:
        """Get an MCP resource."""
        if uri == "agent://status":
            return await self.orchestrator.get_system_status()
        elif uri == "memory://summary":
            return await self.orchestrator.get_agent_memory("global")
        else:
            return {"error": f"Unknown resource: {uri}"}

    async def _analyze_task_prompt(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze task prompt handler."""
        task_description = arguments.get("task_description", "")

        task = {
            "id": "mcp_analysis",
            "description": task_description,
            "priority": "high",
        }

        result = await self.orchestrator.execute_task(task)
        return {
            "description": f"Analysis of: {task_description}",
            "messages": [{
                "role": "assistant",
                "content": json.dumps(result, indent=2)
            }],
        }

    async def _system_status_prompt(self) -> Dict[str, Any]:
        """System status prompt handler."""
        status = await self.orchestrator.get_system_status()
        return {
            "description": "Current system status",
            "messages": [{
                "role": "assistant",
                "content": json.dumps(status, indent=2)
            }],
        }

    async def shutdown(self):
        """Shutdown the MCP server."""
        await self.orchestrator.shutdown()
