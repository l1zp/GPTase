"""Tool base class and registry."""

from abc import ABC
from abc import abstractmethod
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic import Field

logger = logging.getLogger(__name__)


class ToolCall(BaseModel):
    """A tool call requested by the LLM.

    Attributes:
        id: Unique identifier from the LLM.
        name: Tool name (e.g., "Read", "Bash").
        arguments: Parsed JSON arguments.
    """

    id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Result from executing a tool.

    Attributes:
        tool_call_id: ID of the tool call this result is for.
        name: Name of the tool that was executed.
        content: Output or error message.
        is_error: Whether the execution resulted in an error.
    """

    tool_call_id: str
    name: str
    content: str
    is_error: bool = False


class ToolDefinition(BaseModel):
    """Tool definition for OpenAI function calling.

    Attributes:
        type: Always "function" for OpenAI-compatible APIs.
        function: Function definition with name, description, and parameters.
    """

    type: str = "function"
    function: Dict[str, Any]  # name, description, parameters (JSON Schema)


class BaseTool(ABC):
    """Abstract base class for tools.

    All tools must implement get_schema() and execute() methods.

    Attributes:
        name: Tool name (e.g., "Read", "Bash").
        description: Human-readable description of what the tool does.
    """

    name: str
    description: str

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Return OpenAI-compatible JSON Schema for this tool.

        Returns:
            A dictionary representing the JSON Schema for the tool parameters.
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """Execute the tool and return result as string.

        Args:
            **kwargs: Tool-specific arguments.

        Returns:
            The result of the tool execution as a string.
        """
        pass

    def to_tool_definition(self) -> ToolDefinition:
        """Convert to OpenAI tool definition format.

        Returns:
            A ToolDefinition instance.
        """
        return ToolDefinition(
            type="function",
            function={
                "name": self.name,
                "description": self.description,
                "parameters": self.get_schema(),
            },
        )


class ToolRegistry:
    """Registry for managing available tools.

    Tools are registered globally and can be retrieved by name.
    Supports permission restrictions per agent.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._permissions: Dict[str, List[str]] = {}  # tool_name -> allowed agents

    def register(
        self,
        tool: BaseTool,
        allowed_agents: Optional[List[str]] = None,
    ) -> None:
        """Register a tool with optional permission restrictions.

        Args:
            tool: The tool instance to register.
            allowed_agents: Optional list of agent IDs that can use this tool.
                           If None, all agents can use the tool.
        """
        self._tools[tool.name] = tool
        if allowed_agents:
            self._permissions[tool.name] = allowed_agents
        logger.debug("Registered tool: %s", tool.name)

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name.

        Args:
            name: The tool name.

        Returns:
            The tool instance, or None if not found.
        """
        return self._tools.get(name)

    def get_schemas(self, tool_names: List[str]) -> List[Dict[str, Any]]:
        """Get OpenAI-compatible schemas for specified tools.

        Args:
            tool_names: List of tool names to get schemas for.

        Returns:
            List of tool definition dictionaries.
        """
        schemas = []
        for name in tool_names:
            tool = self._tools.get(name)
            if tool:
                schemas.append(tool.to_tool_definition().model_dump())
            else:
                logger.warning("Tool not found in registry: %s", name)
        return schemas

    def is_allowed(self, tool_name: str, agent_id: str) -> bool:
        """Check if an agent is allowed to use a tool.

        Args:
            tool_name: The tool name.
            agent_id: The agent ID.

        Returns:
            True if the agent is allowed to use the tool.
        """
        if tool_name not in self._permissions:
            return True  # No restriction means allowed
        return agent_id in self._permissions[tool_name]

    def list_tools(self) -> List[str]:
        """List all registered tool names.

        Returns:
            List of tool names.
        """
        return list(self._tools.keys())


# Global registry instance
_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry.

    Returns:
        The global ToolRegistry instance with default tools registered.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
        # Import here to avoid circular import
        from gptase.tools.handlers import register_default_tools

        register_default_tools(_global_registry)
    return _global_registry
