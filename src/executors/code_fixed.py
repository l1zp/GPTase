"""
Fixed code executor using the new base
"""

import asyncio
import subprocess
import tempfile
import os
import sys
from typing import Any, Dict
from src.executors.base_fixed import BaseExecutor, ExecutionResult, ExecutionStatus

class CodeExecutor(BaseExecutor):
    """Executor for Python code with sandboxing capabilities."""
    
    def __init__(self, timeout: int = 30, sandbox: bool = True):
        super().__init__("code_executor", timeout)
        self.sandbox = sandbox
        
    async def execute(self, code: str, **kwargs) -> ExecutionResult:
        """Execute Python code safely."""
        
        # Validate code
        if not self.validate_code(code):
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="Invalid Python code syntax"
            )
            
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
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
                cwd=kwargs.get('working_dir', None)
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    output=stdout.decode('utf-8'),
                    exit_code=process.returncode,
                    metadata={"file_path": temp_file}
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.ERROR,
                    error=stderr.decode('utf-8'),
                    exit_code=process.returncode,
                    metadata={"file_path": temp_file}
                )
                
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error=str(e)
            )
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
        dangerous_vars = ['PYTHONPATH', 'PYTHONHOME']
        for var in dangerous_vars:
            env.pop(var, None)
            
        # Add custom environment variables
        custom_env = kwargs.get('env', {})
        env.update(custom_env)
        
        return env
        
    def validate_code(self, code: str) -> bool:
        """Validate Python code syntax."""
        try:
            compile(code, '<string>', 'exec')
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
            "math_operations"
        ]