"""
Base tool interface and result structures
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from enum import Enum

class ToolStatus(str, Enum):
    """Tool execution status."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

class ToolResult(BaseModel):
    """Result from tool execution."""
    status: ToolStatus
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}
    execution_time: float = 0.0
    
    @classmethod
    def success(cls, data: Any, metadata: Dict = None, execution_time: float = 0.0) -> "ToolResult":
        """Create a successful result."""
        return cls(
            status=ToolStatus.SUCCESS,
            data=data,
            metadata=metadata or {},
            execution_time=execution_time
        )
        
    @classmethod
    def error(cls, error: str, metadata: Dict = None, execution_time: float = 0.0) -> "ToolResult":
        """Create an error result."""
        return cls(
            status=ToolStatus.ERROR,
            error=error,
            metadata=metadata or {},
            execution_time=execution_time
        )

class BaseTool(ABC):
    """Abstract base class for all tools."""
    
    def __init__(self, name: str, description: str, timeout: int = 30):
        self.name = name
        self.description = description
        self.timeout = timeout
        
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass
        
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        pass
        
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate parameters against schema."""
        schema = self.get_schema()
        required_params = schema.get("required", [])
        
        for param in required_params:
            if param not in parameters:
                return False
                
        return True
        
    async def safe_execute(self, **kwargs) -> ToolResult:
        """Execute tool with timeout and error handling."""
        try:
            import asyncio
            
            # Set up timeout
            if "timeout" in kwargs:
                timeout = kwargs.pop("timeout")
            else:
                timeout = self.timeout
                
            # Execute with timeout
            start_time = asyncio.get_event_loop().time()
            
            try:
                result = await asyncio.wait_for(
                    self.execute(**kwargs),
                    timeout=timeout
                )
                
                end_time = asyncio.get_event_loop().time()
                result.execution_time = end_time - start_time
                
                return result
                
            except asyncio.TimeoutError:
                return ToolResult.error(
                    f"Tool execution timed out after {timeout} seconds",
                    execution_time=timeout
                )
                
        except Exception as e:
            return ToolResult.error(str(e))
            
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"