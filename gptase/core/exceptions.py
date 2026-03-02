"""Core exceptions for the GPTase framework.

This module defines the exception hierarchy used throughout the GPTase
framework. All custom exceptions inherit from GPTaseException.
"""


class GPTaseException(Exception):
    """Base exception for GPTase framework.

    All framework-specific exceptions inherit from this class, allowing
    for catching any GPTase-related error with a single except clause.
    """


class AgentException(GPTaseException):
    """Exception related to agent operations.

    Raised when an agent fails to initialize, execute a task, or
    communicate with other agents.
    """


class AgentInitializationError(AgentException):
    """Exception raised when agent initialization fails.

    This is a specific subclass of AgentException for errors that occur
    during agent creation and setup, such as missing configuration files
    or invalid agent definitions.
    """


class ExecutionException(GPTaseException):
    """Exception related to code execution.

    Raised when code execution fails in any of the executor engines
    (Python, Shell, Docker, Sandbox).
    """


class ConfigurationError(GPTaseException):
    """Exception related to configuration and environment issues.

    Raised when configuration is missing, invalid, or environment
    variables are not properly set.
    """
