"""
Docker executor for containerized execution
"""

import asyncio
import json
import tempfile
import os
from typing import Any, Dict
from src.executors.base import BaseExecutor, ExecutionResult

class DockerExecutor(BaseExecutor):
    """Executor for Docker containerized execution."""
    
    def __init__(self, timeout: int = 60, image: str = "python:3.11-slim"):
        super().__init__("docker_executor", timeout)
        self.default_image = image
        
    async def execute(self, code: str, **kwargs) -> ExecutionResult:
        """Execute code in Docker container."""
        
        if not self.validate_code(code):
            return ExecutionResult.error("Invalid code format")
            
        # Prepare container configuration
        image = kwargs.get('image', self.default_image)
        working_dir = kwargs.get('working_dir', '/workspace')
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
                
            # Get absolute path
            abs_temp_file = os.path.abspath(temp_file)
            
            # Prepare Docker command
            container_name = f"execution-{int(asyncio.get_event_loop().time())}"
            
            # Build Docker command
            docker_cmd = [
                "docker", "run",
                "--rm",
                "--name", container_name,
                "-v", f"{os.path.dirname(abs_temp_file)}:/workspace",
                "-w", working_dir,
                "--network", "none",  # Disable network for security
                image,
                "python", os.path.basename(temp_file)
            ]
            
            # Execute Docker command
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return ExecutionResult.success(
                    output=stdout.decode('utf-8'),
                    exit_code=process.returncode,
                    metadata={
                        "container": container_name,
                        "image": image,
                        "working_dir": working_dir
                    }
                )
            else:
                return ExecutionResult.error(
                    error=stderr.decode('utf-8'),
                    exit_code=process.returncode,
                    metadata={
                        "container": container_name,
                        "image": image,
                        "working_dir": working_dir
                    }
                )
                
        except FileNotFoundError:
            return ExecutionResult.error("Docker not found. Please install Docker.")
        except Exception as e:
            return ExecutionResult.error(str(e))
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file)
            except:
                pass
                
    def validate_code(self, code: str) -> bool:
        """Validate code format."""
        # Basic validation - not empty
        return bool(code.strip())
        
    def get_capabilities(self) -> list[str]:
        """Return supported capabilities."""
        return [
            "docker_execution",
            "containerized_sandbox",
            "isolated_environment",
            "custom_images",
            "volume_mounting"
        ]

class DockerBuildExecutor(BaseExecutor):
    """Executor for building and running Docker containers."""
    
    def __init__(self, timeout: int = 300):
        super().__init__("docker_build_executor", timeout)
        
    async def execute(self, dockerfile_content: str, **kwargs) -> ExecutionResult:
        """Build and run Docker container from Dockerfile."""
        
        try:
            # Create temporary directory
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                dockerfile_path = os.path.join(temp_dir, "Dockerfile")
                
                # Write Dockerfile
                with open(dockerfile_path, 'w') as f:
                    f.write(dockerfile_content)
                    
                # Build Docker image
                image_name = f"custom-build-{int(asyncio.get_event_loop().time())}"
                
                build_cmd = [
                    "docker", "build",
                    "-t", image_name,
                    temp_dir
                ]
                
                build_process = await asyncio.create_subprocess_exec(
                    *build_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                build_stdout, build_stderr = await build_process.communicate()
                
                if build_process.returncode != 0:
                    return ExecutionResult.error(
                        error=f"Build failed: {build_stderr.decode('utf-8')}",
                        exit_code=build_process.returncode
                    )
                
                # Run the container
                run_cmd = [
                    "docker", "run",
                    "--rm",
                    image_name
                ]
                
                run_process = await asyncio.create_subprocess_exec(
                    *run_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                run_stdout, run_stderr = await run_process.communicate()
                
                if run_process.returncode == 0:
                    return ExecutionResult.success(
                        output=run_stdout.decode('utf-8'),
                        exit_code=run_process.returncode,
                        metadata={
                            "image": image_name,
                            "build_output": build_stdout.decode('utf-8')
                        }
                    )
                else:
                    return ExecutionResult.error(
                        error=run_stderr.decode('utf-8'),
                        exit_code=run_process.returncode
                    )
                    
        except FileNotFoundError:
            return ExecutionResult.error("Docker not found. Please install Docker.")
        except Exception as e:
            return ExecutionResult.error(str(e))
            
    def validate_code(self, code: str) -> bool:
        """Validate Dockerfile format."""
        return bool(code.strip()) and "FROM" in code.upper()
        
    def get_capabilities(self) -> list[str]:
        """Return supported capabilities."""
        return [
            "docker_build",
            "custom_containers",
            "dockerfile_execution",
            "image_creation",
            "container_building"
        ]