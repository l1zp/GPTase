"""Abstract base class for sandbox implementations.

This module defines the interface that all sandbox implementations must follow,
enabling pluggable execution backends (local, Docker, remote, etc.).
"""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class SandboxStatus(str, Enum):
    """Sandbox execution status."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ExecutionResult:
    """Result from sandbox code execution.

    Attributes:
        status: Execution status (success, error, timeout, cancelled).
        stdout: Standard output from execution.
        stderr: Standard error from execution.
        return_code: Process return code.
        execution_time: Time taken in seconds.
        metadata: Additional execution metadata.
    """

    status: SandboxStatus
    stdout: str = ""
    stderr: str = ""
    return_code: Optional[int] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.status == SandboxStatus.SUCCESS

    @property
    def output(self) -> str:
        """Get combined output (stdout + stderr)."""
        if self.stderr:
            return f"{self.stdout}\n{self.stderr}".strip()
        return self.stdout.strip()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution.

    Attributes:
        timeout: Default execution timeout in seconds.
        memory_limit: Memory limit in MB (0 for unlimited).
        cpu_limit: CPU limit as fraction (0 for unlimited).
        network_enabled: Whether network access is allowed.
        working_dir: Working directory for execution.
        env_vars: Environment variables to set.
        allowed_languages: Languages that can be executed.
    """

    timeout: int = 30
    memory_limit: int = 0
    cpu_limit: float = 0.0
    network_enabled: bool = False
    working_dir: Optional[str] = None
    env_vars: Dict[str, str] = None
    allowed_languages: List[str] = None

    def __post_init__(self):
        if self.env_vars is None:
            self.env_vars = {}
        if self.allowed_languages is None:
            self.allowed_languages = ["python", "bash", "shell"]


class Sandbox(ABC):
    """Abstract base class for sandbox implementations.

    A Sandbox provides an isolated environment for executing code safely.
    Implementations can range from local subprocess execution to containerized
    or remote execution environments.

    All methods are async to support both local and remote implementations.
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        """Initialize sandbox with optional configuration.

        Args:
            config: Sandbox configuration. Uses defaults if not provided.
        """
        self.config = config or SandboxConfig()

    @abstractmethod
    async def execute(self,
                      code: str,
                      language: str = "python",
                      timeout: Optional[int] = None,
                      working_dir: Optional[str] = None,
                      env_vars: Optional[Dict[str, str]] = None) -> ExecutionResult:
        """Execute code in the sandbox.

        Args:
            code: Code to execute.
            language: Programming language (python, bash, etc.).
            timeout: Override default timeout in seconds.
            working_dir: Override default working directory.
            env_vars: Additional environment variables.

        Returns:
            ExecutionResult with output and status.

        Raises:
            SandboxTimeoutError: If execution exceeds timeout.
            SandboxLanguageError: If language is not supported.
            SandboxExecutionError: If execution fails.
        """
        pass

    @abstractmethod
    async def execute_file(
            self,
            file_path: str,
            language: str = "python",
            timeout: Optional[int] = None,
            working_dir: Optional[str] = None,
            env_vars: Optional[Dict[str, str]] = None) -> ExecutionResult:
        """Execute a file in the sandbox.

        Args:
            file_path: Path to the file to execute.
            language: Programming language.
            timeout: Override default timeout in seconds.
            working_dir: Override default working directory.
            env_vars: Additional environment variables.

        Returns:
            ExecutionResult with output and status.
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up sandbox resources.

        Called when sandbox is no longer needed to release any resources
        (temp files, containers, connections, etc.).
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if sandbox is available and ready.

        Returns:
            True if sandbox can execute code, False otherwise.
        """
        pass

    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Get list of supported programming languages.

        Returns:
            List of language identifiers (e.g., ["python", "bash"]).
        """
        pass

    def validate_language(self, language: str) -> bool:
        """Validate if language is supported.

        Args:
            language: Language identifier to check.

        Returns:
            True if language is supported.
        """
        supported = self.get_supported_languages()
        return language.lower() in [l.lower() for l in supported]

    async def __aenter__(self) -> "Sandbox":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with cleanup."""
        await self.cleanup()
