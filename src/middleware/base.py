"""Base middleware classes and context management.

This module provides the foundation for middleware components that process
data before and after agent execution. Middleware can be chained together
to create processing pipelines.
"""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from typing import Any, Dict, List, Optional


@dataclass
class MiddlewareContext:
    """Context object passed through middleware chain.

    Contains information about the current request/session that middleware
    can use and modify.

    Attributes:
        thread_id: Unique identifier for the conversation thread.
        agent_id: ID of the agent processing the request.
        agent_name: Human-readable name of the agent.
        session_id: Optional session ID for tracking.
        step_id: Optional step ID within a workflow.
        metadata: Additional context data that middleware can read/modify.
    """

    thread_id: str
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    session_id: Optional[str] = None
    step_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from metadata."""
        return self.metadata.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in metadata."""
        self.metadata[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "thread_id": self.thread_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "session_id": self.session_id,
            "step_id": self.step_id,
            "metadata": self.metadata,
        }


class BaseMiddleware(ABC):
    """Abstract base class for middleware components.

    Middleware components process data as it flows through the system.
    Each middleware can modify both the data and the context before
    passing to the next middleware in the chain.

    Middleware is designed to be lightweight and focused on a single
    responsibility (e.g., file tracking, title generation, logging).
    """

    @property
    def name(self) -> str:
        """Get middleware name (defaults to class name)."""
        return self.__class__.__name__

    @abstractmethod
    async def process(self, context: MiddlewareContext,
                      data: Dict[str, Any]) -> Dict[str, Any]:
        """Process the data.

        Args:
            context: Middleware context with thread/agent information.
            data: The data to process.

        Returns:
            Modified data (can be same as input if no changes needed).
        """
        pass

    async def setup(self) -> None:
        """Called when middleware is initialized.

        Override to perform async initialization tasks.
        """
        pass

    async def teardown(self) -> None:
        """Called when middleware is being removed.

        Override to perform cleanup tasks.
        """
        pass


class MiddlewareChain:
    """Chain of middleware components.

    Executes middleware in order, passing context and data through each.

    Usage:
        chain = MiddlewareChain()
        chain.add(ThreadDataMiddleware())
        chain.add(TitleMiddleware())

        result = await chain.process(context, data)
    """

    def __init__(self):
        """Initialize empty middleware chain."""
        self._middleware: List[BaseMiddleware] = []

    def add(self, middleware: BaseMiddleware) -> "MiddlewareChain":
        """Add middleware to the chain.

        Args:
            middleware: Middleware instance to add.

        Returns:
            Self for method chaining.
        """
        self._middleware.append(middleware)
        return self

    def remove(self, name: str) -> Optional[BaseMiddleware]:
        """Remove middleware by name.

        Args:
            name: Name of middleware to remove.

        Returns:
            Removed middleware or None if not found.
        """
        for i, mw in enumerate(self._middleware):
            if mw.name == name:
                return self._middleware.pop(i)
        return None

    async def process(self, context: MiddlewareContext,
                      data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data through all middleware.

        Args:
            context: Middleware context.
            data: Data to process.

        Returns:
            Processed data after all middleware have run.
        """
        result = data
        for middleware in self._middleware:
            result = await middleware.process(context, result)
        return result

    async def setup_all(self) -> None:
        """Initialize all middleware in the chain."""
        for middleware in self._middleware:
            await middleware.setup()

    async def teardown_all(self) -> None:
        """Teardown all middleware in the chain."""
        for middleware in self._middleware:
            await middleware.teardown()

    def get_middleware(self, name: str) -> Optional[BaseMiddleware]:
        """Get middleware by name.

        Args:
            name: Name of middleware to find.

        Returns:
            Middleware instance or None if not found.
        """
        for mw in self._middleware:
            if mw.name == name:
                return mw
        return None

    def list_middleware(self) -> List[str]:
        """List all middleware names in order.

        Returns:
            List of middleware names.
        """
        return [mw.name for mw in self._middleware]

    def __len__(self) -> int:
        """Get number of middleware in chain."""
        return len(self._middleware)

    def __iter__(self):
        """Iterate over middleware."""
        return iter(self._middleware)
