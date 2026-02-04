"""
System-related tools for file and code operations.
"""

import asyncio
import logging
import os
import tempfile
from typing import Any, Dict

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
    """Tool for executing Python code."""

    def __init__(self):
        super().__init__(
            name="code_executor",
            description="Execute Python code and return results",
            timeout=_CODE_EXECUTOR_TIMEOUT,
        )

    async def execute(self, code: str, working_dir: str = None) -> ToolResult:
        """Execute Python code safely.

        Args:
            code: Python code to execute.
            working_dir: Optional working directory for execution.

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

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return ToolResult.success({
                    "output": stdout.decode("utf-8"),
                    "return_code": process.returncode,
                })

            return ToolResult.error(
                f"Code execution failed: {stderr.decode('utf-8')}",
                metadata={"return_code": process.returncode},
            )

        except Exception as e:
            return ToolResult.error(str(e))
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
