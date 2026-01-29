"""Simple tool creation utilities for function-based tools.

This module provides utilities to create tools from simple functions without
requiring full class inheritance. This reduces boilerplate for straightforward
tools that don't need complex initialization or state management.
"""

import inspect
from typing import Any, Callable, Dict

from src.tools.base import BaseTool
from src.tools.base import ToolResult


class FunctionTool(BaseTool):
    """Tool created from a simple function.

    Allows creating tools without full class inheritance. Useful for simple,
    stateless tools where the function logic is self-contained.

    Attributes:
        name: Tool name.
        description: Tool description.
        timeout: Execution timeout in seconds.
        _func: The wrapped async function.
        _schema: JSON schema for parameters.
    """

    def __init__(
        self,
        name: str,
        func: Callable,
        description: str,
        schema: Dict[str, Any],
        timeout: int = 30,
    ):
        """Initialize from a function.

        Args:
            name: Tool name.
            func: Async function to execute.
            description: Tool description.
            schema: JSON schema for parameters.
            timeout: Execution timeout in seconds.
        """
        super().__init__(name, description, timeout)
        self._func = func
        self._schema = schema

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the wrapped function.

        Args:
            **kwargs: Function parameters.

        Returns:
            ToolResult with function output or error.
        """
        try:
            result = await self._func(**kwargs)
            if isinstance(result, ToolResult):
                return result
            return ToolResult.success(result)
        except Exception as e:
            return ToolResult.error(str(e))

    def get_schema(self) -> Dict[str, Any]:
        """Return the provided schema.

        Returns:
            JSON schema dictionary.
        """
        return self._schema


def tool(
    name: str,
    description: str,
    timeout: int = 30,
    schema: Dict[str, Any] = None,
):
    """Decorator to create a tool from a function.

    Provides a simple way to convert async functions into tools without
    creating a full class. Automatically builds schema from function
    signature if not provided.

    Usage:
        @tool(name="calculator", description="Perform math calculations")
        async def calculate(expression: str) -> Dict[str, Any]:
            result = eval(expression)
            return {"result": result}

        # The function is now a FunctionTool that can be registered
        tool_registry.register_tools([calculate])

    Args:
        name: Tool name.
        description: Tool description.
        timeout: Execution timeout in seconds.
        schema: Optional JSON schema for parameters. If not provided,
            will be built from function signature.

    Returns:
        Decorator function that converts the target function to a FunctionTool.
    """

    def decorator(func: Callable) -> FunctionTool:
        # Build schema from function signature if not provided
        if schema is None:
            final_schema = _build_schema_from_function(func)
        else:
            final_schema = schema

        return FunctionTool(
            name=name,
            func=func,
            description=description,
            schema=final_schema,
            timeout=timeout,
        )

    return decorator


def _build_schema_from_function(func: Callable) -> Dict[str, Any]:
    """Build JSON schema from function signature.

    Args:
        func: Function to analyze.

    Returns:
        JSON schema dictionary.
    """
    sig = inspect.signature(func)
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        # Skip 'self' parameter if present
        if param_name == "self":
            continue

        # Determine type (default to string for simplicity)
        param_type = "string"
        if param.annotation != inspect.Parameter.empty:
            annotation_str = str(param.annotation)
            if "int" in annotation_str:
                param_type = "integer"
            elif "float" in annotation_str or "double" in annotation_str:
                param_type = "number"
            elif "bool" in annotation_str:
                param_type = "boolean"
            elif "dict" in annotation_str.lower():
                param_type = "object"

        properties[param_name] = {"type": param_type}

        # Check if parameter is required
        if param.default == inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }
