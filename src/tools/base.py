"""Base tool interface and result structures."""

from abc import ABC
from abc import abstractmethod
import asyncio
from enum import Enum
import inspect
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel

from src.core.constants import DEFAULT_TOOL_TIMEOUT


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
    error_message: Optional[
        str] = None  # Renamed from 'error' to avoid conflict with classmethod
    metadata: Dict[str, Any] = {}
    execution_time: float = 0.0

    # Compatibility property for backward compatibility
    @property
    def error(self) -> Optional[str]:
        """Get error message (backward compatibility)."""
        return self.error_message

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
    def from_error(
        cls,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None,
        execution_time: float = 0.0,
    ) -> "ToolResult":
        """Create an error result.

        Args:
            error_message: Error message describing what went wrong.
            metadata: Optional execution metadata.
            execution_time: Time taken in seconds.

        Returns:
            A ToolResult with status ERROR.
        """
        return cls(
            status=ToolStatus.ERROR,
            error_message=error_message,
            metadata=metadata or {},
            execution_time=execution_time,
        )

    # Keep old error() method for backward compatibility (deprecated)
    @classmethod
    def error(
        cls,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None,
        execution_time: float = 0.0,
    ) -> "ToolResult":
        """Create an error result (deprecated: use from_error instead).

        Args:
            error_message: Error message describing what went wrong.
            metadata: Optional execution metadata.
            execution_time: Time taken in seconds.

        Returns:
            A ToolResult with status ERROR.
        """
        return cls.from_error(error_message, metadata, execution_time)


class TrackingMixin:
    """Mixin class for tools that support conversation tracking.

    This mixin provides common initialization and storage for tracking
    parameters used by ModelManager to link LLM calls to extraction
    sessions and workflow steps.

    Attributes:
        agent_id: Optional agent ID for tracking which agent initiated the call.
        agent_name: Optional agent name for getting agent-specific config.
        session_id: Optional session ID for tracking extraction sessions.
        step_id: Optional step ID for tracking workflow steps within sessions.
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ):
        """Initialize tracking parameters."""
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.session_id = session_id
        self.step_id = step_id

    def get_tracking_params(self) -> dict:
        """Get tracking parameters as a dictionary."""
        params = {}
        if self.agent_id is not None:
            params["agent_id"] = self.agent_id
        if self.agent_name is not None:
            params["agent_name"] = self.agent_name
        if self.session_id is not None:
            params["session_id"] = self.session_id
        if self.step_id is not None:
            params["step_id"] = self.step_id
        return params

    def update_tracking(
        self,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> None:
        """Update tracking parameters."""
        if agent_id is not None:
            self.agent_id = agent_id
        if agent_name is not None:
            self.agent_name = agent_name
        if session_id is not None:
            self.session_id = session_id
        if step_id is not None:
            self.step_id = step_id


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
        timeout: int = DEFAULT_TOOL_TIMEOUT,
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
    timeout: int = DEFAULT_TOOL_TIMEOUT,
    schema: Dict[str, Any] = None,
):
    """Decorator to create a tool from a function.

    Provides a simple way to convert async functions into tools without
    creating a full class. Automatically builds schema from function
    signature if not provided.

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
