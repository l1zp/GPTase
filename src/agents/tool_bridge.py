"""Bridge GPTase tools to Claude Agent SDK MCP format.

This module provides the ToolBridge class that converts GPTase's tool registry
into SDK-compatible tool functions decorated with @tool and wrapped for MCP server use.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ToolBridge:
    """Converts GPTase tools to SDK-compatible format.

    This bridge enables GPTase tools registered in the ToolRegistry to be used
    with Claude Agent SDK's MCP server system. It handles:
    - Converting tool schemas to SDK format
    - Wrapping tool execution for async SDK calls
    - Managing tool result conversion

    Attributes:
        tool_registry: GPTase ToolRegistry instance.
        _wrapped_tools: Cache of wrapped tool functions.
    """

    def __init__(self, tool_registry):
        """Initialize the tool bridge.

        Args:
            tool_registry: GPTase ToolRegistry instance.
        """
        self.tool_registry = tool_registry
        self._wrapped_tools: Dict[str, Callable] = {}

    def to_sdk_tools(self, tool_names: Optional[List[str]] = None) -> List[Callable]:
        """Convert registered tools to SDK @tool decorated functions.

        Args:
            tool_names: Optional list of specific tool names to convert.
                       If None, converts all registered tools.

        Returns:
            List of SDK-compatible tool functions.
        """
        sdk_tools = []

        # Determine which tools to convert
        if tool_names:
            tools_to_convert = {
                name: self.tool_registry.get_tool(name)
                for name in tool_names if self.tool_registry.get_tool(name) is not None
            }
        else:
            tools_to_convert = self.tool_registry._tools

        for name, tool_instance in tools_to_convert.items():
            if name in self._wrapped_tools:
                sdk_tools.append(self._wrapped_tools[name])
            else:
                sdk_tool = self._wrap_tool(name, tool_instance)
                self._wrapped_tools[name] = sdk_tool
                sdk_tools.append(sdk_tool)

        return sdk_tools

    def _wrap_tool(self, name: str, gptase_tool) -> Callable:
        """Wrap a GPTase tool as SDK tool.

        Creates an async function that:
        1. Accepts SDK-style args dict
        2. Calls the GPTase tool's safe_execute
        3. Returns SDK-style content blocks

        Args:
            name: Tool name.
            gptase_tool: GPTase BaseTool instance.

        Returns:
            SDK-compatible tool function.
        """
        # Try to import SDK tool decorator
        try:
            from claude_agent_sdk import tool as sdk_tool_decorator
            use_sdk_decorator = True
        except ImportError:
            use_sdk_decorator = False
            logger.warning(
                "claude-agent-sdk not installed. Using fallback tool wrapper.")

        # Get tool schema for parameter types
        schema = gptase_tool.get_schema()
        description = gptase_tool.description

        if use_sdk_decorator:
            # Build type annotations from schema
            param_types = self._build_param_types(schema)

            @sdk_tool_decorator(name, description, param_types)
            async def sdk_handler(args: dict) -> dict:
                return await self._execute_wrapped_tool(gptase_tool, args)

            return sdk_handler
        else:
            # Fallback without decorator
            async def fallback_handler(args: dict) -> dict:
                return await self._execute_wrapped_tool(gptase_tool, args)

            # Attach metadata
            fallback_handler.__name__ = name
            fallback_handler.__doc__ = description
            fallback_handler._tool_schema = schema

            return fallback_handler

    async def _execute_wrapped_tool(self, gptase_tool, args: dict) -> dict:
        """Execute a GPTase tool and convert result to SDK format.

        Args:
            gptase_tool: GPTase BaseTool instance.
            args: Tool arguments from SDK.

        Returns:
            SDK-style response dict with content blocks.
        """
        try:
            result = await gptase_tool.safe_execute(**args)

            if result.status.value == "success":
                return {
                    "content": [{
                        "type": "text",
                        "text": self._format_result_data(result.data),
                    }],
                    "is_error":
                    False,
                }
            else:
                return {
                    "content": [{
                        "type":
                        "text",
                        "text":
                        f"Tool error: {result.error_message or 'Unknown error'}",
                    }],
                    "is_error":
                    True,
                }

        except asyncio.TimeoutError:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Tool '{gptase_tool.name}' timed out",
                }],
                "is_error":
                True,
            }
        except Exception as e:
            logger.error(f"Tool execution error in {gptase_tool.name}: {e}")
            return {
                "content": [{
                    "type": "text",
                    "text": f"Tool execution failed: {str(e)}",
                }],
                "is_error": True,
            }

    def _build_param_types(self, schema: Dict[str, Any]) -> Dict[str, type]:
        """Build type annotations from JSON schema.

        Args:
            schema: JSON schema dictionary.

        Returns:
            Dictionary mapping parameter names to Python types.
        """
        param_types = {}
        properties = schema.get("properties", {})

        type_mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        for param_name, param_spec in properties.items():
            json_type = param_spec.get("type", "string")
            param_types[param_name] = type_mapping.get(json_type, str)

        return param_types

    def _format_result_data(self, data: Any) -> str:
        """Format tool result data as string for SDK response.

        Args:
            data: Result data from tool execution.

        Returns:
            String representation of the data.
        """
        import json

        if data is None:
            return "Success (no output)"

        if isinstance(data, str):
            return data

        if isinstance(data, (dict, list)):
            try:
                return json.dumps(data, indent=2, default=str)
            except (TypeError, ValueError):
                return str(data)

        return str(data)

    def get_tool_schema_for_sdk(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get SDK-compatible schema for a tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            SDK-compatible schema dict or None if tool not found.
        """
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return None

        gptase_schema = tool.get_schema()

        # Convert to SDK format (mostly compatible, but ensure structure)
        return {
            "name": tool_name,
            "description": tool.description,
            "input_schema": {
                "type": "object",
                "properties": gptase_schema.get("properties", {}),
                "required": gptase_schema.get("required", []),
            },
        }

    def list_bridgeable_tools(self) -> List[str]:
        """List all tools that can be bridged to SDK.

        Returns:
            List of tool names that have valid schemas.
        """
        valid_tools = []

        for name, tool in self.tool_registry._tools.items():
            try:
                schema = tool.get_schema()
                if schema and "properties" in schema:
                    valid_tools.append(name)
            except Exception as e:
                logger.warning(f"Tool {name} has invalid schema: {e}")

        return valid_tools


def create_sdk_tools_from_registry(
    tool_registry,
    tool_names: Optional[List[str]] = None,
) -> List[Callable]:
    """Convenience function to create SDK tools from a registry.

    Args:
        tool_registry: GPTase ToolRegistry instance.
        tool_names: Optional list of specific tools to convert.

    Returns:
        List of SDK-compatible tool functions.
    """
    bridge = ToolBridge(tool_registry)
    return bridge.to_sdk_tools(tool_names)
