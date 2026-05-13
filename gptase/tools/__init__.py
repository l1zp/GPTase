"""Tool execution system for non-Claude models.

This module provides tool execution capabilities for agents using
OpenAI-compatible APIs (OpenAI, DeepSeek, etc.).

Usage:
    from gptase.tools import get_tool_registry

    registry = get_tool_registry()
    schemas = registry.get_schemas(["Read", "Bash"])
    tool = registry.get("Read")
    result = await tool.execute(file_path="/path/to/file")
"""

from gptase.tools.base import BaseTool
from gptase.tools.base import get_tool_registry
from gptase.tools.base import ToolRegistry
from gptase.tools.executor import ToolExecutor
from gptase.tools.handlers import BashTool
from gptase.tools.handlers import DelegateTaskTool
from gptase.tools.handlers import GlobTool
from gptase.tools.handlers import GrepTool
from gptase.tools.handlers import ReadTool

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "ToolExecutor",
    "get_tool_registry",
    "ReadTool",
    "GrepTool",
    "GlobTool",
    "BashTool",
    "DelegateTaskTool",
]
