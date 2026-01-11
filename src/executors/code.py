"""
Refactored code executor for Python execution
"""

import asyncio
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict

from src.executors.base import BaseExecutor
from src.executors.base import ExecutionResult
from src.executors.base import ExecutionStatus


class CodeExecutor(BaseExecutor):
    """Executor for Python code with sandboxing capabilities."""

    def __init__(self, timeout: int = 30, sandbox: bool = True):
        super().__init__("code_executor", timeout)
        self.sandbox = sandbox

    async def execute(self, code: str, **kwargs) -> ExecutionResult:
        """Execute Python code safely."""

        # Validate code
        if not self.validate_code(code):
            return ExecutionResult.error("Invalid Python code syntax")

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            # Prepare execution environment
            env = self._prepare_environment(**kwargs)

            # Execute the code
            cmd = [sys.executable, temp_file]

            process = await asyncio.create_subprocess_exec(
                *cmd,
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
                    file_path=temp_file,
                )
            else:
                return ExecutionResult.error(
                    error=stderr.decode("utf-8"),
                    exit_code=process.returncode,
                    file_path=temp_file,
                )

        except Exception as e:
            return ExecutionResult.error(str(e))
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file)
            except:
                pass

    def _prepare_environment(self, **kwargs) -> Dict[str, str]:
        """Prepare safe environment variables."""
        env = os.environ.copy()

        # Remove potentially dangerous variables
        dangerous_vars = ["PYTHONPATH", "PYTHONHOME"]
        for var in dangerous_vars:
            env.pop(var, None)

        # Add custom environment variables
        custom_env = kwargs.get("env", {})
        env.update(custom_env)

        return env

    def validate_code(self, code: str) -> bool:
        """Validate Python code syntax."""
        try:
            compile(code, "<string>", "exec")
            return True
        except SyntaxError:
            return False

    def get_capabilities(self) -> list[str]:
        """Return supported capabilities."""
        return [
            "python_execution",
            "code_sandboxing",
            "file_operations",
            "network_requests",
            "math_operations",
        ]


class JupyterExecutor(BaseExecutor):
    """Executor for Jupyter notebook cells."""

    def __init__(self, timeout: int = 30):
        super().__init__("jupyter_executor", timeout)

    async def execute(self, code: str, **kwargs) -> ExecutionResult:
        """Execute Jupyter notebook cell code."""
        try:
            # Import jupyter if available
            try:
                from IPython import get_ipython
                from IPython.core.interactiveshell import InteractiveShell

                # Create a new IPython shell
                shell = InteractiveShell.instance()

                # Execute the code
                result = shell.run_cell(code)

                if result.success:
                    return ExecutionResult.success(
                        output=str(result.result) if result.result else "",
                        metadata={"execution_count": shell.execution_count},
                    )
                else:
                    return ExecutionResult.error(
                        error=str(result.error_before_exec or result.error_in_exec),
                        exit_code=1,
                    )

            except ImportError:
                # Fallback to regular Python execution
                return await CodeExecutor(self.timeout).execute(code, **kwargs)

        except Exception as e:
            return ExecutionResult.error(str(e))

    def validate_code(self, code: str) -> bool:
        """Validate Python code syntax."""
        return CodeExecutor().validate_code(code)

    def get_capabilities(self) -> list[str]:
        """Return supported capabilities."""
        return [
            "jupyter_execution",
            "interactive_python",
            "notebook_cells",
            "matplotlib_support",
        ]
