"""Bridge GPTase tools to Claude Agent SDK format.

This module converts GPTase's ToolRegistry tools into SDK-compatible
tool functions and MCP servers.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ToolBridge:
    """Converts GPTase tools to SDK-compatible format.

    This bridge enables GPTase tools registered in the ToolRegistry to be used
    with Claude Agent SDK. It handles schema conversion, async execution,
    and result formatting.
    """

    def __init__(self, tool_registry):
        """Initialize the tool bridge.

        Args:
            tool_registry: GPTase ToolRegistry instance.
        """
        self.tool_registry = tool_registry
        self._wrapped_tools = {}

    def to_sdk_tools(self,
                     tool_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Convert registered tools to SDK-compatible tool definitions.

        Args:
            tool_names: Optional list of specific tool names to convert.
                       If None, converts all registered tools.

        Returns:
            List of SDK-compatible tool definition dicts.
        """
        names = tool_names or list(self.tool_registry._tools.keys())
        sdk_tools = []

        for name in names:
            tool = self.tool_registry.get_tool(name)
            if tool is None:
                logger.warning(f"Tool '{name}' not found in registry, skipping")
                continue

            schema = self._build_tool_schema(name, tool)
            if schema:
                sdk_tools.append(schema)
                self._wrapped_tools[name] = tool

        return sdk_tools

    def create_mcp_servers(self, tool_names: List[str]) -> List[Any]:
        """Create MCP servers for GPTase tools.

        Args:
            tool_names: List of tool names to bridge.

        Returns:
            List of MCP server instances.
        """
        try:
            from fastmcp import FastMCP

            mcp = FastMCP("gptase-tools")

            for name in tool_names:
                tool = self.tool_registry.get_tool(name)
                if tool is None:
                    continue

                # Register tool with MCP server
                self._register_mcp_tool(mcp, name, tool)

            return [mcp]

        except ImportError:
            logger.warning("fastmcp not installed, MCP bridging unavailable. "
                           "Install with: pip install fastmcp")
            return []

    def _register_mcp_tool(self, mcp, name: str, tool) -> None:
        """Register a GPTase tool with an MCP server.

        Args:
            mcp: FastMCP server instance.
            name: Tool name.
            tool: GPTase BaseTool instance.
        """
        description = getattr(tool, 'description', name)

        @mcp.tool(name=name, description=description)
        async def handler(**kwargs):
            return await self._execute_tool(tool, kwargs)

    async def _execute_tool(self, tool, args: dict) -> str:
        """Execute a GPTase tool and return result as string.

        Args:
            tool: GPTase BaseTool instance.
            args: Tool arguments.

        Returns:
            String result for SDK consumption.
        """
        try:
            if asyncio.iscoroutinefunction(tool.execute):
                result = await tool.execute(**args)
            else:
                result = tool.execute(**args)

            # Format result
            if hasattr(result, 'data'):
                data = result.data
            else:
                data = result

            if isinstance(data, (dict, list)):
                return json.dumps(data, ensure_ascii=False, indent=2)
            return str(data)

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return json.dumps({"error": str(e)})

    def _build_tool_schema(self, name: str, tool) -> Optional[Dict[str, Any]]:
        """Build SDK-compatible schema for a tool.

        Args:
            name: Tool name.
            tool: GPTase BaseTool instance.

        Returns:
            Schema dict or None if tool has no valid schema.
        """
        schema = getattr(tool, 'input_schema', None)
        if schema is None:
            schema = getattr(tool, 'schema', None)

        return {
            "name": name,
            "description": getattr(tool, 'description', ''),
            "input_schema": schema or {
                "type": "object",
                "properties": {}
            },
        }

    def list_bridgeable_tools(self) -> List[str]:
        """List all tools that can be bridged to SDK.

        Returns:
            List of tool names that have valid schemas.
        """
        return [
            name for name, tool in self.tool_registry._tools.items()
            if self._build_tool_schema(name, tool) is not None
        ]
