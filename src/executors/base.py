"""
Refactored base executor interface - Elegant version
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import time

class ExecutionStatus(str, Enum):
    """Execution status codes."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

@dataclass
class ExecutionResult:
    """Result from task execution."""
    status: ExecutionStatus
    output: str = ""
    error: Optional[str] = None
    exit_code: Optional[int] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @classmethod
    def success(cls, output: str = "", exit_code: int = 0, **metadata) -> "ExecutionResult":
        """Create a successful result."""
        return cls(
            status=ExecutionStatus.SUCCESS,
            output=output,
            exit_code=exit_code,
            metadata=metadata
        )
    
    @classmethod
    def error(cls, error: str, exit_code: int = 1, **metadata) -> "ExecutionResult":
        """Create an error result."""
        return cls(
            status=ExecutionStatus.ERROR,
            error=error,
            exit_code=exit_code,
            metadata=metadata
        )
    
    @classmethod
    def timeout(cls, timeout: float, **metadata) -> "ExecutionResult":
        """Create a timeout result."""
        return cls(
            status=ExecutionStatus.TIMEOUT,
            error=f"Execution timed out after {timeout} seconds",
            execution_time=timeout,
            metadata=metadata
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
            return ExecutionResult.timeout(self.timeout)
        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            return ExecutionResult.error(str(e))
            
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