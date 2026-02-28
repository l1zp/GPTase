"""Tool Registry - Central management for all available tools."""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)

# Default category for uncategorized tools
DEFAULT_CATEGORY = "general"

# Maximum concurrent tool executions
MAX_CONCURRENT_EXECUTIONS = 10

# Error messages
ERROR_TOOL_NOT_FOUND = "Tool '{tool_name}' not found"
ERROR_INVALID_PARAMETERS = "Invalid parameters for tool '{tool_name}'"
ERROR_MISSING_REQUIRED = "Missing required parameters: {required}"


class ToolRegistry:
    """Registry for managing all available tools.

    The ToolRegistry provides centralized tool registration, lookup,
    execution, and categorization. It supports parallel batch execution
    and capability-based tool discovery.

    Attributes:
        _tools: Dictionary mapping tool names to tool instances.
        _tool_categories: Dictionary mapping category names to tool name lists.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._tool_categories: Dict[str, List[str]] = {}

    def register_tool(self, tool: BaseTool, category: str = DEFAULT_CATEGORY) -> None:
        """Register a tool with the registry.

        Args:
            tool: The tool instance to register.
            category: Category name for grouping related tools.
        """
        self._tools[tool.name] = tool

        if category not in self._tool_categories:
            self._tool_categories[category] = []
        self._tool_categories[category].append(tool.name)

        logger.info("Registered tool: %s in category: %s", tool.name, category)

    def register_tools(self,
                       tools: List[BaseTool],
                       category: str = DEFAULT_CATEGORY) -> None:
        """Register multiple tools.

        Args:
            tools: List of tool instances to register.
            category: Category name for grouping related tools.
        """
        for tool in tools:
            self.register_tool(tool, category)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name.

        Args:
            name: Tool identifier.

        Returns:
            Tool instance or None if not found.
        """
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[str]:
        """List all available tools, optionally filtered by category.

        Args:
            category: Optional category to filter by.

        Returns:
            List of tool names.
        """
        if category:
            return self._tool_categories.get(category, [])
        return list(self._tools.keys())

    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """Get all tools in a category.

        Args:
            category: Category name.

        Returns:
            List of tool instances in the category.
        """
        tool_names = self._tool_categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]

    def get_all_categories(self) -> List[str]:
        """Get all tool categories.

        Returns:
            List of category names.
        """
        return list(self._tool_categories.keys())

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        timeout: Optional[int] = None,
    ) -> ToolResult:
        """Execute a tool with given parameters.

        Args:
            tool_name: Name of the tool to execute.
            parameters: Tool-specific parameters.
            timeout: Optional timeout override in seconds.

        Returns:
            ToolResult with execution outcome.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult.from_error(
                ERROR_TOOL_NOT_FOUND.format(tool_name=tool_name))

        if not tool.validate_parameters(parameters):
            return ToolResult.from_error(
                ERROR_INVALID_PARAMETERS.format(tool_name=tool_name))

        logger.info("Executing tool: %s with params: %s", tool_name, parameters)

        if timeout is not None:
            parameters = {**parameters, "timeout": timeout}

        return await tool.safe_execute(**parameters)

    async def execute_tools_batch(self,
                                  tool_calls: List[Dict[str, Any]]) -> List[ToolResult]:
        """Execute multiple tools in parallel.

        Args:
            tool_calls: List of dictionaries with 'tool', 'parameters', and
                optional 'timeout' keys.

        Returns:
            List of ToolResult objects, one per call.
        """
        tasks = [
            self.execute_tool(call.get("tool"), call.get("parameters", {}),
                              call.get("timeout")) for call in tool_calls
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def get_tool_descriptions(self) -> Dict[str, Dict[str, Any]]:
        """Get descriptions for all tools.

        Returns:
            Dictionary mapping tool names to their description, schema, and timeout.
        """
        descriptions = {}
        for name, tool in self._tools.items():
            descriptions[name] = {
                "description": tool.description,
                "schema": tool.get_schema(),
                "timeout": tool.timeout,
            }
        return descriptions

    def get_tools_for_capabilities(self, capabilities: List[str]) -> List[str]:
        """Get tools that match given capabilities.

        Performs simple keyword matching against tool names and descriptions.

        Args:
            capabilities: List of capability keywords to search for.

        Returns:
            List of matching tool names.
        """
        matching_tools = []
        for tool_name, tool in self._tools.items():
            tool_desc = f"{tool.name} {tool.description}".lower()
            if any(capability.lower() in tool_desc for capability in capabilities):
                matching_tools.append(tool_name)
        return matching_tools

    def validate_tool_call(self, tool_name: str,
                           parameters: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate if a tool call is valid.

        Args:
            tool_name: Name of the tool to validate.
            parameters: Parameters to validate.

        Returns:
            Tuple of (is_valid, error_message). Error message is empty if valid.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return False, ERROR_TOOL_NOT_FOUND.format(tool_name=tool_name)

        if not tool.validate_parameters(parameters):
            schema = tool.get_schema()
            required = schema.get("required", [])
            return False, ERROR_MISSING_REQUIRED.format(required=required)

        return True, ""

    def __len__(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)

    def __repr__(self) -> str:
        """Return string representation of the registry."""
        return (f"ToolRegistry(tools={len(self._tools)}, "
                f"categories={len(self._tool_categories)})")
