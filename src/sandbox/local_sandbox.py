"""Local subprocess-based sandbox implementation.

This module provides a simple sandbox implementation that executes code
in local subprocesses with timeout and resource management.
"""

import asyncio
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional

from .base import ExecutionResult
from .base import Sandbox
from .base import SandboxConfig
from .base import SandboxStatus
from .exceptions import SandboxExecutionError
from .exceptions import SandboxLanguageError
from .exceptions import SandboxTimeoutError

logger = logging.getLogger(__name__)

# Default supported languages with their executors
DEFAULT_LANGUAGE_EXECUTORS = {
    "python": ["python3", "-c"],
    "python3": ["python3", "-c"],
    "bash": ["bash", "-c"],
    "shell": ["bash", "-c"],
    "sh": ["sh", "-c"],
}


class LocalSandbox(Sandbox):
    """Local subprocess-based sandbox implementation.

    Executes code in local subprocesses with configurable timeouts and
    environment isolation. Suitable for trusted code execution where
    container-level isolation is not required.

    Warning:
        This implementation does not provide strong isolation. Only use
        with trusted code or in development environments. For production
        use with untrusted code, consider a containerized sandbox.
    """

    def __init__(
        self,
        timeout: int = 30,
        working_dir: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        language_executors: Optional[Dict[str, List[str]]] = None,
        **kwargs,
    ):
        """Initialize local sandbox.

        Args:
            timeout: Default execution timeout in seconds.
            working_dir: Default working directory for execution.
            env_vars: Default environment variables.
            language_executors: Mapping of language -> [command, args...].
            **kwargs: Additional arguments passed to SandboxConfig.
        """
        config = SandboxConfig(
            timeout=timeout,
            working_dir=working_dir,
            env_vars=env_vars or {},
            **kwargs,
        )
        super().__init__(config)
        self.language_executors = language_executors or DEFAULT_LANGUAGE_EXECUTORS
        self._temp_files: List[str] = []

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        """Execute code in a subprocess.

        Args:
            code: Code to execute.
            language: Programming language.
            timeout: Override default timeout.
            working_dir: Override default working directory.
            env_vars: Additional environment variables.

        Returns:
            ExecutionResult with output and status.

        Raises:
            SandboxLanguageError: If language is not supported.
        """
        language = language.lower()

        if not self.validate_language(language):
            raise SandboxLanguageError(language, list(self.language_executors.keys()))

        exec_timeout = timeout or self.config.timeout
        exec_working_dir = working_dir or self.config.working_dir

        # Merge environment variables
        exec_env = os.environ.copy()
        exec_env.update(self.config.env_vars)
        if env_vars:
            exec_env.update(env_vars)

        # Get executor command
        executor = self.language_executors.get(language)
        if not executor:
            raise SandboxLanguageError(language, list(self.language_executors.keys()))

        # Build command
        cmd = executor + [code]

        logger.debug(f"Executing {language} code with timeout {exec_timeout}s")

        start_time = asyncio.get_event_loop().time()

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=exec_working_dir,
                env=exec_env,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(),
                                                    timeout=exec_timeout)

            end_time = asyncio.get_event_loop().time()
            execution_time = end_time - start_time

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if process.returncode == 0:
                return ExecutionResult(
                    status=SandboxStatus.SUCCESS,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    return_code=process.returncode,
                    execution_time=execution_time,
                )
            else:
                return ExecutionResult(
                    status=SandboxStatus.ERROR,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    return_code=process.returncode,
                    execution_time=execution_time,
                    metadata={"error_type": "execution_error"},
                )

        except asyncio.TimeoutError:
            end_time = asyncio.get_event_loop().time()
            raise SandboxTimeoutError(
                exec_timeout, f"Execution timed out after {exec_timeout} seconds")

        except Exception as e:
            end_time = asyncio.get_event_loop().time()
            logger.error(f"Execution error: {e}")
            raise SandboxExecutionError(str(e),
                                        metadata={"error_type": type(e).__name__})

    async def execute_file(
        self,
        file_path: str,
        language: str = "python",
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        """Execute a file in a subprocess.

        Args:
            file_path: Path to the file to execute.
            language: Programming language.
            timeout: Override default timeout.
            working_dir: Override default working directory.
            env_vars: Additional environment variables.

        Returns:
            ExecutionResult with output and status.
        """
        language = language.lower()

        if not self.validate_language(language):
            raise SandboxLanguageError(language, list(self.language_executors.keys()))

        exec_timeout = timeout or self.config.timeout
        exec_working_dir = working_dir or self.config.working_dir or os.path.dirname(
            file_path)

        # Merge environment variables
        exec_env = os.environ.copy()
        exec_env.update(self.config.env_vars)
        if env_vars:
            exec_env.update(env_vars)

        # Build command based on language
        if language in ("python", "python3"):
            cmd = ["python3", file_path]
        elif language in ("bash", "shell", "sh"):
            cmd = ["bash", file_path]
        else:
            raise SandboxLanguageError(language, list(self.language_executors.keys()))

        logger.debug(f"Executing file {file_path} with timeout {exec_timeout}s")

        start_time = asyncio.get_event_loop().time()

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=exec_working_dir,
                env=exec_env,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(),
                                                    timeout=exec_timeout)

            end_time = asyncio.get_event_loop().time()
            execution_time = end_time - start_time

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if process.returncode == 0:
                return ExecutionResult(
                    status=SandboxStatus.SUCCESS,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    return_code=process.returncode,
                    execution_time=execution_time,
                )
            else:
                return ExecutionResult(
                    status=SandboxStatus.ERROR,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    return_code=process.returncode,
                    execution_time=execution_time,
                    metadata={"error_type": "execution_error"},
                )

        except asyncio.TimeoutError:
            raise SandboxTimeoutError(
                exec_timeout, f"File execution timed out after {exec_timeout} seconds")

        except Exception as e:
            logger.error(f"File execution error: {e}")
            raise SandboxExecutionError(str(e))

    async def cleanup(self) -> None:
        """Clean up temporary files created during execution."""
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_file}: {e}")

        self._temp_files.clear()

    async def is_available(self) -> bool:
        """Check if sandbox is available.

        Returns:
            True if python3 is available in PATH.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "python3",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except Exception:
            return False

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages.

        Returns:
            List of supported language identifiers.
        """
        return list(self.language_executors.keys())

    async def execute_with_temp_file(
        self,
        code: str,
        language: str = "python",
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        suffix: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute code by writing to a temp file first.

        Useful for longer code or code that requires file-based execution.

        Args:
            code: Code to execute.
            language: Programming language.
            timeout: Override default timeout.
            working_dir: Override default working directory.
            env_vars: Additional environment variables.
            suffix: File suffix (e.g., '.py'). Auto-detected if not provided.

        Returns:
            ExecutionResult with output and status.
        """
        language = language.lower()

        # Determine file suffix
        if suffix is None:
            suffix_map = {
                "python": ".py",
                "python3": ".py",
                "bash": ".sh",
                "shell": ".sh",
                "sh": ".sh",
            }
            suffix = suffix_map.get(language, ".txt")

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
            f.write(code)
            temp_file = f.name

        self._temp_files.append(temp_file)

        try:
            return await self.execute_file(
                temp_file,
                language=language,
                timeout=timeout,
                working_dir=working_dir,
                env_vars=env_vars,
            )
        finally:
            # Clean up immediately after execution
            try:
                os.unlink(temp_file)
                self._temp_files.remove(temp_file)
            except Exception:
                pass
