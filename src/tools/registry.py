"""
Tool Registry - Central management for all available tools
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type
from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Registry for managing all available tools."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._tool_categories: Dict[str, List[str]] = {}
        
    def register_tool(self, tool: BaseTool, category: str = "general") -> None:
        """Register a tool with the registry."""
        self._tools[tool.name] = tool
        
        if category not in self._tool_categories:
            self._tool_categories[category] = []
        self._tool_categories[category].append(tool.name)
        
        logger.info(f"Registered tool: {tool.name} in category: {category}")
        
    def register_tools(self, tools: List[BaseTool], category: str = "general") -> None:
        """Register multiple tools."""
        for tool in tools:
            self.register_tool(tool, category)
            
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)
        
    def list_tools(self, category: str = None) -> List[str]:
        """List all available tools, optionally filtered by category."""
        if category:
            return self._tool_categories.get(category, [])
        return list(self._tools.keys())
        
    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """Get all tools in a category."""
        tool_names = self._tool_categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]
        
    def get_all_categories(self) -> List[str]:
        """Get all tool categories."""
        return list(self._tool_categories.keys())
        
    async def execute_tool(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any],
        timeout: int = None
    ) -> ToolResult:
        """Execute a tool with given parameters."""
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult.error(f"Tool '{tool_name}' not found")
            
        if not tool.validate_parameters(parameters):
            return ToolResult.error(f"Invalid parameters for tool '{tool_name}'")
            
        logger.info(f"Executing tool: {tool_name} with params: {parameters}")
        
        # Use custom timeout if provided
        if timeout:
            parameters = {**parameters, "timeout": timeout}
            
        return await tool.safe_execute(**parameters)
        
    async def execute_tools_batch(
        self, 
        tool_calls: List[Dict[str, Any]]
    ) -> List[ToolResult]:
        """Execute multiple tools in parallel."""
        tasks = []
        
        for call in tool_calls:
            tool_name = call.get("tool")
            parameters = call.get("parameters", {})
            timeout = call.get("timeout")
            
            task = self.execute_tool(tool_name, parameters, timeout)
            tasks.append(task)
            
        return await asyncio.gather(*tasks, return_exceptions=True)
        
    def get_tool_descriptions(self) -> Dict[str, Dict[str, Any]]:
        """Get descriptions for all tools."""
        descriptions = {}
        
        for name, tool in self._tools.items():
            descriptions[name] = {
                "description": tool.description,
                "schema": tool.get_schema(),
                "timeout": tool.timeout
            }
            
        return descriptions
        
    def get_tools_for_capabilities(self, capabilities: List[str]) -> List[str]:
        """Get tools that match given capabilities."""
        matching_tools = []
        
        for tool_name, tool in self._tools.items():
            # Simple capability matching based on tool name and description
            tool_desc = f"{tool.name} {tool.description}".lower()
            
            for capability in capabilities:
                if capability.lower() in tool_desc:
                    matching_tools.append(tool_name)
                    break
                    
        return matching_tools
        
    def validate_tool_call(self, tool_name: str, parameters: Dict[str, Any]) -> tuple[bool, str]:
        """Validate if a tool call is valid."""
        tool = self.get_tool(tool_name)
        if not tool:
            return False, f"Tool '{tool_name}' not found"
            
        if not tool.validate_parameters(parameters):
            schema = tool.get_schema()
            required = schema.get("required", [])
            return False, f"Missing required parameters: {required}"
            
        return True, ""
        
    def __len__(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)
        
    def __repr__(self) -> str:
        return f"ToolRegistry(tools={len(self._tools)}, categories={len(self._tool_categories)})"