"""Base tool interface and result structures."""

from abc import ABC
from abc import abstractmethod
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel

from src.core.constants import DEFAULT_TOOL_TIMEOUT

# Tool status values that align with framework status constants
TOOL_STATUS_SUCCESS = "success"
TOOL_STATUS_ERROR = "error"
TOOL_STATUS_TIMEOUT = "timeout"
TOOL_STATUS_CANCELLED = "cancelled"


class ToolStatus(str, Enum):
    """Tool execution status enum.

    Attributes:
        SUCCESS: Tool executed successfully.
        ERROR: Tool execution failed with an error.
        TIMEOUT: Tool execution exceeded time limit.
        CANCELLED: Tool execution was cancelled.
    """

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ToolResult(BaseModel):
    """Result from tool execution.

    Attributes:
        status: The execution status (ToolStatus enum).
        data: Result data (when status is SUCCESS).
        error: Error message (when status is ERROR).
        metadata: Additional information about the execution.
        execution_time: Time taken to execute in seconds.
    """

    status: ToolStatus
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}
    execution_time: float = 0.0

    @classmethod
    def success(
        cls,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        execution_time: float = 0.0,
    ) -> "ToolResult":
        """Create a successful result.

        Args:
            data: Result data to return.
            metadata: Optional execution metadata.
            execution_time: Time taken in seconds.

        Returns:
            A ToolResult with status SUCCESS.
        """
        return cls(
            status=ToolStatus.SUCCESS,
            data=data,
            metadata=metadata or {},
            execution_time=execution_time,
        )

    @classmethod
    def error(
        cls,
        error: str,
        metadata: Optional[Dict[str, Any]] = None,
        execution_time: float = 0.0,
    ) -> "ToolResult":
        """Create an error result.

        Args:
            error: Error message describing what went wrong.
            metadata: Optional execution metadata.
            execution_time: Time taken in seconds.

        Returns:
            A ToolResult with status ERROR.
        """
        return cls(
            status=ToolStatus.ERROR,
            error=error,
            metadata=metadata or {},
            execution_time=execution_time,
        )


class BaseTool(ABC):
    """Abstract base class for all tools.

    BaseTool provides a standard interface for tool implementations including
    timeout handling, parameter validation, and error handling. Subclasses
    must implement the execute and get_schema methods.

    Attributes:
        name: Unique identifier for this tool.
        description: Human-readable description of what the tool does.
        timeout: Default execution timeout in seconds.
    """

    def __init__(self,
                 name: str,
                 description: str,
                 timeout: int = DEFAULT_TOOL_TIMEOUT) -> None:
        self.name = name
        self.description = description
        self.timeout = timeout

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters.

        Returns:
            ToolResult with the execution outcome.
        """
        raise NotImplementedError

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters.

        Returns:
            JSON schema dictionary describing required/optional parameters.
        """
        raise NotImplementedError

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate parameters against schema.

        Args:
            parameters: Parameter dictionary to validate.

        Returns:
            True if all required parameters are present, False otherwise.
        """
        schema = self.get_schema()
        required_params = schema.get("required", [])

        for param in required_params:
            if param not in parameters:
                return False

        return True

    async def safe_execute(self, **kwargs: Any) -> ToolResult:
        """Execute tool with timeout and error handling.

        Wraps the execute method with timeout protection and exception handling.
        Automatically adds execution time to the result.

        Args:
            **kwargs: Tool-specific parameters. May include 'timeout' to override
                the default timeout.

        Returns:
            ToolResult with execution outcome and timing information.
        """
        import asyncio

        timeout = kwargs.pop("timeout", self.timeout)
        start_time = asyncio.get_event_loop().time()

        try:
            result = await asyncio.wait_for(self.execute(**kwargs), timeout=timeout)
            end_time = asyncio.get_event_loop().time()
            result.execution_time = end_time - start_time
            return result

        except asyncio.TimeoutError:
            return ToolResult.error(
                f"Tool execution timed out after {timeout} seconds",
                execution_time=timeout,
            )

        except Exception as e:
            return ToolResult.error(str(e))

    def __repr__(self) -> str:
        """Return string representation of the tool."""
        return f"{self.__class__.__name__}(name='{self.name}')"
