"""Sandbox-specific exceptions.

This module defines exceptions related to sandbox execution environments.
"""


class SandboxError(Exception):
    """Base exception for sandbox-related errors."""

    pass


class SandboxTimeoutError(SandboxError):
    """Exception raised when sandbox execution exceeds time limit."""

    def __init__(self, timeout: int, message: str = None):
        self.timeout = timeout
        self.message = message or f"Sandbox execution timed out after {timeout} seconds"
        super().__init__(self.message)


class SandboxResourceError(SandboxError):
    """Exception raised when sandbox resource limits are exceeded."""

    def __init__(self, resource: str, limit: str, message: str = None):
        self.resource = resource
        self.limit = limit
        self.message = message or f"Sandbox resource limit exceeded: {resource} > {limit}"
        super().__init__(self.message)


class SandboxExecutionError(SandboxError):
    """Exception raised when code execution fails in sandbox."""

    def __init__(self,
                 message: str,
                 return_code: int = None,
                 stdout: str = None,
                 stderr: str = None):
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        self.message = message
        super().__init__(self.message)


class SandboxNotAvailableError(SandboxError):
    """Exception raised when sandbox provider is not configured."""

    def __init__(self, message: str = "No sandbox provider configured"):
        self.message = message
        super().__init__(self.message)


class SandboxLanguageError(SandboxError):
    """Exception raised when an unsupported language is requested."""

    def __init__(self, language: str, supported: list = None):
        self.language = language
        self.supported = supported or []
        if self.supported:
            self.message = (f"Unsupported language: {language}. "
                            f"Supported: {', '.join(self.supported)}")
        else:
            self.message = f"Unsupported language: {language}"
        super().__init__(self.message)
