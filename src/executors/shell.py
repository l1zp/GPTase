"""
Refactored shell executor for system commands and scripts
"""

import asyncio
import os
import subprocess
import tempfile
from typing import Any, Dict

from src.executors.base import BaseExecutor, ExecutionResult, ExecutionStatus


class ShellExecutor(BaseExecutor):
    """Executor for shell commands and scripts."""

    def __init__(self, timeout: int = 30, shell: str = None):
        super().__init__("shell_executor", timeout)
        self.shell = shell or ("bash" if os.name != "nt" else "cmd")

    async def execute(self, command: str, **kwargs) -> ExecutionResult:
        """Execute shell commands safely."""

        if not self.validate_code(command):
            return ExecutionResult.error("Invalid or dangerous shell command")

        try:
            # Prepare environment
            env = self._prepare_environment(**kwargs)

            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=kwargs.get("working_dir", None),
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return ExecutionResult.success(
                    output=stdout.decode("utf-8"),
                    exit_code=process.returncode,
                    command=command,
                )
            else:
                return ExecutionResult.error(
                    error=stderr.decode("utf-8") or stdout.decode("utf-8"),
                    exit_code=process.returncode,
                    command=command,
                )

        except Exception as e:
            return ExecutionResult.error(str(e))

    def _prepare_environment(self, **kwargs) -> Dict[str, str]:
        """Prepare safe environment variables."""
        env = os.environ.copy()

        # Add custom environment variables
        custom_env = kwargs.get("env", {})
        env.update(custom_env)

        # Security: Restrict certain variables
        restricted_vars = ["LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"]
        for var in restricted_vars:
            env.pop(var, None)

        return env

    def validate_code(self, command: str) -> bool:
        """Validate shell command safety."""
        # Basic validation - check for dangerous commands
        dangerous_patterns = [
            "rm -rf /",
            "sudo",
            "chmod 777",
            "wget http",
            "curl http",
            "nc -l",
            "netcat",
        ]

        command_lower = command.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in command_lower:
                return False

        return True

    def get_capabilities(self) -> list[str]:
        """Return supported capabilities."""
        return [
            "shell_execution",
            "system_commands",
            "file_operations",
            "process_management",
            "network_tools",
        ]


class BashExecutor(ShellExecutor):
    """Executor specifically for bash commands."""

    def __init__(self, timeout: int = 30):
        super().__init__(timeout, shell="bash")

    def get_capabilities(self) -> list[str]:
        """Return bash-specific capabilities."""
        return [
            "bash_execution",
            "unix_commands",
            "shell_scripts",
            "pipe_operations",
            "environment_variables",
        ]


class PowerShellExecutor(ShellExecutor):
    """Executor for PowerShell commands."""

    def __init__(self, timeout: int = 30):
        super().__init__(timeout, shell="powershell")

    async def execute(self, command: str, **kwargs) -> ExecutionResult:
        """Execute PowerShell commands."""
        # Wrap PowerShell command
        if not command.startswith("powershell"):
            command = f'powershell -Command "{command}"'

        return await super().execute(command, **kwargs)

    def get_capabilities(self) -> list[str]:
        """Return PowerShell-specific capabilities."""
        return [
            "powershell_execution",
            "windows_commands",
            "cmdlets",
            "registry_operations",
            "windows_services",
        ]
