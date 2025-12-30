"""
Core exceptions for the GPTase framework
"""


class GPTaseException(Exception):
    """Base exception for GPTase framework."""

    pass


class AgentException(GPTaseException):
    """Exception related to agent operations."""

    pass


class ExecutionException(GPTaseException):
    """Exception related to code execution."""

    pass


class MemoryException(GPTaseException):
    """Exception related to memory operations."""

    pass


class ModelException(GPTaseException):
    """Exception related to model operations."""

    pass


class ToolException(GPTaseException):
    """Exception related to tool operations."""

    pass


class ConfigurationError(GPTaseException):
    """Exception related to configuration and environment issues."""

    pass
