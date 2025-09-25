"""
Base executor interface and result structures - Fixed version
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from enum import Enum
import time

class ExecutionStatus(str, Enum):
    """Execution status codes."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RUNNING = "running"

class ExecutionResult:
    """Result from task execution."""
    
    def __init__(
        self,
        status: ExecutionStatus,
        output: str = "",
        error: Optional[str] = None,
        exit_code: Optional[int] = None,
        execution_time: float = 0.0,
        metadata: Dict[str, Any] = None
    ):
        self.status = status
        self.output = output
        self.error = error
        self.exit_code = exit_code
        self.execution_time = execution_time
        self.metadata = metadata or {}
        
    def __repr__(self) -> str:
        return f"ExecutionResult(status={self.status}, exit_code={self.exit_code})"
        
    def __eq__(self, other) -> bool:
        if not isinstance(other, ExecutionResult):
            return False
        return (
            self.status == other.status
            and self.exit_code == other.exit_code
            and self.error == other.error
        )

class BaseExecutor(ABC):
    """Abstract base class for all executors."""
    
    def __init__(self, name: str, timeout: int = 30):
        self.name = name
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
    @abstractmethod
    async def execute(self, code: str, **kwargs) -> ExecutionResult:
        """Execute the given code/task."""
        pass
        
    async def safe_execute(self, code: str, **kwargs) -> ExecutionResult:
        """Execute with timeout and error handling."""
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(
                self.execute(code, **kwargs),
                timeout=self.timeout
            )
            result.execution_time = time.time() - start_time
            return result
            
        except asyncio.TimeoutError:
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                error=f"Execution timed out after {self.timeout} seconds",
                execution_time=self.timeout
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error=str(e),
                exit_code=1
            )
            
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """List of capabilities this executor supports."""
        pass
        
    @abstractmethod
    def validate_code(self, code: str) -> bool:
        """Validate if the code can be executed by this executor."""
        pass
        
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', timeout={self.timeout})"