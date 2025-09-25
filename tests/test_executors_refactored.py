"""
Refactored tests for the executor system - More reliable and elegant
"""

import pytest
import asyncio
import os
from executors.base import ExecutionStatus
from executors.code import CodeExecutor
from executors.shell import ShellExecutor

@pytest.mark.asyncio
async def test_code_executor_success():
    """Test successful Python code execution."""
    executor = CodeExecutor(timeout=5)
    
    result = await executor.execute("print('Hello, World!')")
    
    assert result.status == ExecutionStatus.SUCCESS
    assert "Hello, World!" in result.output
    assert result.exit_code == 0

@pytest.mark.asyncio
async def test_code_executor_syntax_error():
    """Test Python code with syntax error."""
    executor = CodeExecutor(timeout=5)
    
    result = await executor.execute("print('unclosed string")
    
    assert result.status == ExecutionStatus.ERROR
    assert result.error is not None

@pytest.mark.asyncio
async def test_code_executor_runtime_error():
    """Test Python code with runtime error."""
    executor = CodeExecutor(timeout=5)
    
    result = await executor.execute("raise ValueError('Test error')")
    
    assert result.status == ExecutionStatus.ERROR
    assert "ValueError" in result.error

@pytest.mark.asyncio
async def test_code_validation():
    """Test code validation."""
    executor = CodeExecutor()
    
    # Valid Python code
    assert executor.validate_code("print('valid')") == True
    
    # Invalid Python code
    assert executor.validate_code("print('unclosed string") == False

@pytest.mark.asyncio
async def test_code_executor_empty():
    """Test empty code execution."""
    executor = CodeExecutor(timeout=5)
    
    result = await executor.execute("")
    
    assert result.status == ExecutionStatus.SUCCESS

@pytest.mark.asyncio
async def test_code_executor_complex():
    """Test complex Python code execution."""
    executor = CodeExecutor(timeout=5)
    
    code = """
import math
result = math.sqrt(16)
print(f"Square root: {result}")
"""
    
    result = await executor.execute(code)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert "Square root: 4.0" in result.output

@pytest.mark.asyncio
async def test_executor_capabilities():
    """Test executor capabilities."""
    executor = CodeExecutor()
    
    capabilities = executor.get_capabilities()
    
    assert "python_execution" in capabilities
    assert "code_sandboxing" in capabilities

@pytest.mark.asyncio
async def test_safe_execute():
    """Test safe execution with timeout."""
    executor = CodeExecutor(timeout=2)
    
    result = await executor.safe_execute("print('Safe execution')")
    
    assert result.status == ExecutionStatus.SUCCESS
    assert "Safe execution" in result.output

@pytest.mark.asyncio
async def test_code_executor_with_metadata():
    """Test execution with metadata tracking."""
    executor = CodeExecutor(timeout=5)
    
    result = await executor.execute("print('test')")
    
    assert result.status == ExecutionStatus.SUCCESS
    assert "file_path" in result.metadata