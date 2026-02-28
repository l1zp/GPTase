"""Sandbox execution module for safe code execution.

This module provides a pluggable sandbox system for executing code
in isolated environments. The system supports multiple backends
(local subprocess, Docker, etc.) through a unified interface.

Quick Start:
    from src.sandbox import LocalSandbox, SandboxProvider

    # Configure the provider
    SandboxProvider.configure(LocalSandbox, timeout=30)

    # Get sandbox instance
    sandbox = SandboxProvider.get_sandbox()

    # Execute code
    result = await sandbox.execute("print('hello')")
    print(result.stdout)

Classes:
    Sandbox: Abstract base class for sandbox implementations.
    LocalSandbox: Local subprocess-based sandbox implementation.
    SandboxProvider: Singleton manager for sandbox instances.
    SandboxConfig: Configuration dataclass for sandbox settings.
    ExecutionResult: Result dataclass from code execution.

Exceptions:
    SandboxError: Base exception for sandbox errors.
    SandboxTimeoutError: Execution timeout error.
    SandboxExecutionError: Code execution error.
    SandboxLanguageError: Unsupported language error.
    SandboxNotAvailableError: Sandbox not configured error.
"""

from .base import ExecutionResult
from .base import Sandbox
from .base import SandboxConfig
from .base import SandboxStatus
from .exceptions import SandboxError
from .exceptions import SandboxExecutionError
from .exceptions import SandboxLanguageError
from .exceptions import SandboxNotAvailableError
from .exceptions import SandboxTimeoutError
from .local_sandbox import LocalSandbox
from .provider import get_sandbox
from .provider import SandboxProvider

__all__ = [
    # Base classes
    "Sandbox",
    "SandboxConfig",
    "SandboxStatus",
    "ExecutionResult",
    # Implementations
    "LocalSandbox",
    # Provider
    "SandboxProvider",
    "get_sandbox",
    # Exceptions
    "SandboxError",
    "SandboxTimeoutError",
    "SandboxExecutionError",
    "SandboxLanguageError",
    "SandboxNotAvailableError",
]
