"""
System-related tools for file and code operations.
"""

import asyncio
import logging
import os
import tempfile
from typing import Any, Dict, Optional

from src.core.constants import Timeouts
from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)

# Use centralized timeout constants
_CODE_WRITER_TIMEOUT = Timeouts.CODE_WRITER
_CODE_EXECUTOR_TIMEOUT = Timeouts.CODE_EXECUTOR
_FILE_MANAGER_TIMEOUT = Timeouts.FILE_MANAGER

# File action constants
_FILE_ACTIONS = ["read", "list", "create_dir", "delete", "exists"]


def _get_sandbox():
    """Get sandbox instance lazily to avoid circular imports.

    Returns:
        Sandbox instance if configured, None otherwise.
    """
    try:
        from src.sandbox import SandboxProvider
        if SandboxProvider.is_configured():
            return SandboxProvider.get_sandbox()
    except ImportError:
        pass
    return None


class CodeWriterTool(BaseTool):
    """Tool for writing code to files."""

    def __init__(self):
        super().__init__(
            name="code_writer",
            description="Write code content to a specified file path",
            timeout=_CODE_WRITER_TIMEOUT,
        )

    async def execute(self,
                      file_path: str,
                      content: str,
                      overwrite: bool = False) -> ToolResult:
        """Write code to a file.

        Args:
            file_path: Path where to write the file.
            content: Code content to write.
            overwrite: Whether to overwrite existing file.

        Returns:
            ToolResult with file path and size.
        """
        try:
            file_path = file_path if os.path.isabs(file_path) else os.path.abspath(
                file_path)

            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            if os.path.exists(file_path) and not overwrite:
                return ToolResult.error(
                    f"File {file_path} already exists and overwrite=False")

            with open(file_path, "w") as f:
                f.write(content)

            return ToolResult.success({
                "file_path": file_path,
                "size": len(content),
                "created": True
            })

        except Exception as e:
            return ToolResult.error(str(e))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path where to write the file"
                },
                "content": {
                    "type": "string",
                    "description": "Code content to write"
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to overwrite existing file",
                    "default": False
                },
            },
            "required": ["file_path", "content"],
        }


class CodeExecutorTool(BaseTool):
    """Tool for executing Python code using sandbox.

    Uses the configured sandbox provider if available, otherwise falls back
    to direct subprocess execution.
    """

    def __init__(self, sandbox=None):
        """Initialize CodeExecutorTool.

        Args:
            sandbox: Optional sandbox instance. If not provided, will use
                     SandboxProvider if configured, or fall back to subprocess.
        """
        super().__init__(
            name="code_executor",
            description="Execute Python code and return results",
            timeout=_CODE_EXECUTOR_TIMEOUT,
        )
        self._sandbox = sandbox

    @property
    def sandbox(self):
        """Get sandbox instance (lazy initialization)."""
        if self._sandbox is None:
            self._sandbox = _get_sandbox()
        return self._sandbox

    async def execute(
        self,
        code: str,
        working_dir: str = None,
        language: str = "python",
        timeout: Optional[int] = None,
    ) -> ToolResult:
        """Execute code safely.

        Args:
            code: Code to execute.
            working_dir: Optional working directory for execution.
            language: Programming language (default: python).
            timeout: Optional timeout override in seconds.

        Returns:
            ToolResult with output or error message.
        """
        exec_timeout = timeout or self.timeout

        # Try sandbox execution first
        sandbox = self.sandbox
        if sandbox is not None:
            try:
                result = await sandbox.execute(
                    code=code,
                    language=language,
                    timeout=exec_timeout,
                    working_dir=working_dir,
                )
                if result.success:
                    return ToolResult.success(
                        {
                            "output": result.stdout,
                            "return_code": result.return_code,
                            "execution_time": result.execution_time,
                        },
                        metadata=result.metadata,
                    )
                else:
                    return ToolResult.from_error(
                        f"Code execution failed: {result.stderr}",
                        metadata={
                            "return_code": result.return_code,
                            "execution_time": result.execution_time,
                            **result.metadata,
                        },
                    )
            except Exception as e:
                logger.warning(
                    f"Sandbox execution failed: {e}, falling back to subprocess")

        # Fallback to direct subprocess execution
        return await self._execute_subprocess(code, working_dir, exec_timeout)

    async def _execute_subprocess(
        self,
        code: str,
        working_dir: str = None,
        timeout: int = None,
    ) -> ToolResult:
        """Execute code using subprocess (fallback method).

        Args:
            code: Python code to execute.
            working_dir: Optional working directory for execution.
            timeout: Timeout in seconds.

        Returns:
            ToolResult with output or error message.
        """
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_file = f.name

            if working_dir:
                os.chdir(working_dir)

            process = await asyncio.create_subprocess_exec(
                "python3",
                temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout or self.timeout,
            )

            if process.returncode == 0:
                return ToolResult.success({
                    "output": stdout.decode("utf-8"),
                    "return_code": process.returncode,
                })

            return ToolResult.from_error(
                f"Code execution failed: {stderr.decode('utf-8')}",
                metadata={"return_code": process.returncode},
            )

        except asyncio.TimeoutError:
            return ToolResult.from_error(
                f"Code execution timed out after {timeout} seconds",
                metadata={"timeout": timeout},
            )
        except Exception as e:
            return ToolResult.from_error(str(e))
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for code execution",
                    "default": None
                },
                "language": {
                    "type": "string",
                    "description": "Programming language (python, bash)",
                    "default": "python"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": None
                },
            },
            "required": ["code"],
        }


class FileManagerTool(BaseTool):
    """Tool for file system operations."""

    def __init__(self):
        super().__init__(
            name="file_manager",
            description="Manage files and directories",
            timeout=_FILE_MANAGER_TIMEOUT,
        )

    async def execute(self, action: str, path: str, **kwargs) -> ToolResult:
        """Perform file system operations.

        Args:
            action: File operation to perform (read, list, create_dir, delete, exists).
            path: File or directory path.

        Returns:
            ToolResult with operation result.
        """
        try:
            if action == "read":
                with open(path, "r") as f:
                    content = f.read()
                return ToolResult.success({"content": content, "size": len(content)})

            if action == "list":
                items = os.listdir(path)
                return ToolResult.success({"items": items, "count": len(items)})

            if action == "create_dir":
                os.makedirs(path, exist_ok=True)
                return ToolResult.success({"created": path})

            if action == "delete":
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    import shutil
                    shutil.rmtree(path)
                return ToolResult.success({"deleted": path})

            if action == "exists":
                return ToolResult.success({
                    "exists": os.path.exists(path),
                    "is_file": os.path.isfile(path),
                    "is_dir": os.path.isdir(path),
                })

            return ToolResult.error(f"Unknown action: {action}")

        except Exception as e:
            return ToolResult.error(str(e))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _FILE_ACTIONS,
                    "description": "File operation to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path"
                },
            },
            "required": ["action", "path"],
        }
