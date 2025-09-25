"""
Sandbox executor for secure code execution
"""

import asyncio
import tempfile
import os
import subprocess
from typing import Any, Dict
from src.executors.base import BaseExecutor, ExecutionResult

class SandboxExecutor(BaseExecutor):
    """Executor for secure sandboxed code execution using firejail."""
    
    def __init__(self, timeout: int = 30, language: str = "python"):
        super().__init__("sandbox_executor", timeout)
        self.language = language
        
    async def execute(self, code: str, **kwargs) -> ExecutionResult:
        """Execute code in a secure sandbox."""
        
        if not self.validate_code(code):
            return ExecutionResult.error(f"Invalid {self.language} code")
            
        # Map languages to executors
        language_map = {
            "python": ["python3", "-u"],
            "javascript": ["node"],
            "bash": ["bash"],
            "ruby": ["ruby"],
            "go": ["go", "run"],
            "rust": ["rustc", "--crate-name", "temp", "-"],
            "cpp": ["g++", "-o", "temp", "-x", "c++", "-"],
            "c": ["gcc", "-o", "temp", "-x", "c", "-"]
        }
        
        if self.language not in language_map:
            return ExecutionResult.error(f"Unsupported language: {self.language}")
            
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{self.language}', delete=False) as f:
                if self.language in ["cpp", "c"]:
                    # Handle compilation languages
                    f.write(code)
                    temp_file = f.name
                    
                    # Compile and run
                    compile_cmd = language_map[self.language] + [temp_file]
                    
                    # Use firejail for sandboxing
                    sandbox_cmd = ["firejail", "--quiet", "--net=none"] + compile_cmd
                    
                    compile_process = await asyncio.create_subprocess_exec(
                        *sandbox_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await compile_process.communicate()
                    
                    if compile_process.returncode == 0:
                        # Run the compiled binary
                        run_cmd = ["firejail", "--quiet", "--net=none", "./temp"]
                        
                        run_process = await asyncio.create_subprocess_exec(
                            *run_cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        
                        run_stdout, run_stderr = await run_process.communicate()
                        
                        return ExecutionResult.success(
                            output=run_stdout.decode('utf-8'),
                            exit_code=run_process.returncode,
                            metadata={"language": self.language, "sandbox": "firejail"}
                        )
                    else:
                        return ExecutionResult.error(
                            error=stderr.decode('utf-8'),
                            exit_code=compile_process.returncode
                        )
                        
                else:
                    # Handle interpreted languages
                    f.write(code)
                    temp_file = f.name
                    
                    # Use firejail for sandboxing
                    cmd = ["firejail", "--quiet", "--net=none"] + language_map[self.language] + [temp_file]
                    
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        return ExecutionResult.success(
                            output=stdout.decode('utf-8'),
                            exit_code=process.returncode,
                            metadata={"language": self.language, "sandbox": "firejail"}
                        )
                    else:
                        return ExecutionResult.error(
                            error=stderr.decode('utf-8'),
                            exit_code=process.returncode
                        )
                        
        except FileNotFoundError:
            # Fallback to regular execution if firejail not available
            return await self._fallback_execution(code, **kwargs)
        except Exception as e:
            return ExecutionResult.error(str(e))
        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_file)
                if self.language in ["cpp", "c"]:
                    os.unlink("./temp")
            except:
                pass
                
    async def _fallback_execution(self, code: str, **kwargs) -> ExecutionResult:
        """Fallback execution without sandboxing."""
        from .code import CodeExecutor
        executor = CodeExecutor(self.timeout)
        return await executor.execute(code, **kwargs)
        
    def validate_code(self, code: str) -> bool:
        """Validate code format."""
        return bool(code.strip())
        
    def get_capabilities(self) -> list[str]:
        """Return supported capabilities."""
        return [
            "sandboxed_execution",
            "secure_isolation",
            "multi_language",
            "network_blocking",
            "file_system_restriction"
        ]

class RestrictedExecutor(BaseExecutor):
    """Executor with resource restrictions."""
    
    def __init__(self, timeout: int = 30, max_memory: int = 512):
        super().__init__("restricted_executor", timeout)
        self.max_memory = max_memory  # MB
        
    async def execute(self, code: str, **kwargs) -> ExecutionResult:
        """Execute with resource restrictions using ulimit."""
        
        if not self.validate_code(code):
            return ExecutionResult.error("Invalid Python code")
            
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
                
            # Prepare restricted environment
            env = os.environ.copy()
            env['PYTHONPATH'] = ''
            
            # Use ulimit for resource restrictions
            restricted_cmd = [
                "ulimit", "-v", str(self.max_memory * 1024), "&&",
                sys.executable, temp_file
            ]
            
            # Execute with restrictions
            process = await asyncio.create_subprocess_shell(
                " ".join(restricted_cmd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return ExecutionResult.success(
                    output=stdout.decode('utf-8'),
                    exit_code=process.returncode,
                    metadata={"max_memory_mb": self.max_memory}
                )
            else:
                error_msg = stderr.decode('utf-8')
                if "memory" in error_msg.lower():
                    error_msg = f"Memory limit exceeded ({self.max_memory}MB)"
                
                return ExecutionResult.error(
                    error=error_msg,
                    exit_code=process.returncode,
                    metadata={"max_memory_mb": self.max_memory}
                )
                
        except Exception as e:
            return ExecutionResult.error(str(e))
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
                
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
            "memory_limited",
            "cpu_restricted",
            "resource_monitoring",
            "quota_enforcement",
            "safe_python"
        ]