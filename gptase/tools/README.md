# GPTase Tools System

This document explains how to create and register custom tools for the GPTase tool execution system.

## Overview

The tools system provides a way for LLM agents to interact with external systems through function calling. It consists of:

- **BaseTool**: Abstract base class that all tools must inherit from
- **ToolRegistry**: Global registry for managing available tools
- **ToolExecutor**: Executes the multi-turn LLM loop with tool support

## Core Concepts

### BaseTool

All tools inherit from `BaseTool` and must implement:

1. `name`: Class attribute - the tool name (e.g., "Read", "Bash")
2. `description`: Class attribute - human-readable description
3. `get_schema()`: Returns JSON Schema for the tool parameters
4. `execute()`: Async method that performs the actual work

### Tool Schema

Tool schemas follow the OpenAI function calling format. Example:

```python
{
    "type": "object",
    "properties": {
        "param_name": {
            "type": "string",
            "description": "Parameter description",
        },
    },
    "required": ["param_name"],
}
```

## Creating a Custom Tool

### Step 1: Create the Tool Class

Create a new file in `gptase/tools/` or import `BaseTool` from your own module:

```python
# gptase/tools/handlers.py (add to existing file)
# or create a new file like gptase/tools/my_tools.py

from typing import Any, Dict, Optional
from gptase.tools.base import BaseTool


class WebFetchTool(BaseTool):
    """Tool for fetching web content."""

    name = "WebFetch"
    description = "Fetch content from a URL and return the text."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch content from",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 30)",
                },
            },
            "required": ["url"],
        }

    async def execute(self, url: str, timeout: int = 30) -> str:
        """Fetch content from a URL.

        Args:
            url: The URL to fetch.
            timeout: Request timeout in seconds.

        Returns:
            The fetched content or error message.
        """
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    if response.status != 200:
                        return f"[ERROR] HTTP {response.status}: {response.reason}"
                    content = await response.text()
                    return content[:10000]  # Limit output size
        except asyncio.TimeoutError:
            return f"[ERROR] Request timed out after {timeout} seconds"
        except Exception as e:
            return f"[ERROR] Failed to fetch URL: {e}"
```

### Step 2: Register the Tool

Register your tool with the global registry:

```python
from gptase.tools.base import get_tool_registry
from gptase.tools.handlers import register_default_tools

# Option 1: Add to register_default_tools() in handlers.py
def register_default_tools(registry: "ToolRegistry") -> None:
    registry.register(ReadTool())
    registry.register(GrepTool())
    registry.register(GlobTool())
    registry.register(BashTool())
    registry.register(WebFetchTool())  # Add your tool here

# Option 2: Register manually anywhere in your code
registry = get_tool_registry()
registry.register(WebFetchTool())

# Option 3: Register with permission restrictions
registry.register(
    WebFetchTool(),
    allowed_agents=["web-analyzer", "data-fetcher"],  # Only these agents can use it
)
```

### Step 3: Use the Tool with an Agent

```python
from gptase.models.model import Model
from gptase.tools import ToolExecutor, get_tool_registry

# Initialize model
model = Model()

# Create executor with available tools
executor = ToolExecutor(
    model=model,
    agent_id="my-agent",
    max_iterations=10,
)

# Run with tool access
messages = [
    {"role": "user", "content": "Fetch the content from https://example.com"}
]

result = await executor.execute(
    messages=messages,
    tools=["WebFetch"],  # Specify which tools the LLM can use
)

print(result["data"]["content"])
```

## Complete Example: Calculator Tool

```python
from typing import Any, Dict, List
from gptase.tools.base import BaseTool


class CalculatorTool(BaseTool):
    """Tool for basic arithmetic calculations."""

    name = "Calculator"
    description = "Perform basic arithmetic operations (add, subtract, multiply, divide)."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                    "description": "The arithmetic operation to perform",
                },
                "numbers": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "List of numbers to operate on",
                },
            },
            "required": ["operation", "numbers"],
        }

    async def execute(self, operation: str, numbers: List[float]) -> str:
        """Execute the calculation.

        Args:
            operation: The arithmetic operation.
            numbers: List of numbers.

        Returns:
            The calculation result or error message.
        """
        if not numbers:
            return "[ERROR] No numbers provided"

        try:
            if operation == "add":
                result = sum(numbers)
            elif operation == "subtract":
                result = numbers[0] - sum(numbers[1:])
            elif operation == "multiply":
                result = 1
                for n in numbers:
                    result *= n
            elif operation == "divide":
                if 0 in numbers[1:]:
                    return "[ERROR] Division by zero"
                result = numbers[0]
                for n in numbers[1:]:
                    result /= n
            else:
                return f"[ERROR] Unknown operation: {operation}"

            return str(result)
        except Exception as e:
            return f"[ERROR] Calculation failed: {e}"
```

## Best Practices

### 1. Return Strings

Always return strings from `execute()`. This is what the LLM expects:

```python
# Good
async def execute(self, path: str) -> str:
    return f"[OK] File read: {content}"

# Bad - will cause issues
async def execute(self, path: str) -> dict:
    return {"status": "ok", "content": "..."}
```

### 2. Use Error Prefixes

Use consistent error prefixes for better parsing:

- `[ERROR]` for errors
- `[OK]` for success
- `[INFO]` for informational messages
- `[WARNING]` for warnings

### 3. Validate Input

Validate inputs early and return clear error messages:

```python
async def execute(self, file_path: str) -> str:
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        return f"[ERROR] File not found: {file_path}"

    if not path.is_file():
        return f"[ERROR] Not a file: {file_path}"

    # ... rest of implementation
```

### 4. Limit Output Size

Large outputs can overwhelm the context window:

```python
async def execute(self, query: str) -> str:
    result = expensive_operation(query)
    return result[:5000]  # Limit to 5000 characters
```

### 5. Handle Timeouts

For long-running operations, implement timeout handling:

```python
async def execute(self, command: str, timeout: int = 30) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(command)
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
        # ...
    except asyncio.TimeoutError:
        return f"[ERROR] Operation timed out after {timeout} seconds"
```

### 6. Safety Checks

For tools that execute commands or modify files, add safety checks:

```python
class BashTool(BaseTool):
    BLOCKED_PATTERNS = [
        r"\brm\s+-rf",
        r"\bmkfs\b",
        # ...
    ]

    async def execute(self, command: str) -> str:
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return "[ERROR] Command blocked for safety"
        # ... rest of implementation
```

## Exporting New Tools

Add your tool to `gptase/tools/__init__.py`:

```python
from gptase.tools.handlers import WebFetchTool

__all__ = [
    # ... existing exports
    "WebFetchTool",
]
```

## Testing Tools

Create unit tests for your tools:

```python
import pytest
from gptase.tools.handlers import CalculatorTool


@pytest.mark.asyncio
async def test_calculator_add():
    tool = CalculatorTool()
    result = await tool.execute(operation="add", numbers=[1, 2, 3])
    assert result == "6.0"


@pytest.mark.asyncio
async def test_calculator_divide_by_zero():
    tool = CalculatorTool()
    result = await tool.execute(operation="divide", numbers=[10, 0])
    assert "[ERROR]" in result
```

## Architecture Summary

```
gptase/tools/
  base.py        # BaseTool, ToolRegistry, data models
  handlers.py    # Concrete tool implementations (Read, Grep, Glob, Bash)
  executor.py    # ToolExecutor for LLM tool-calling loop
  __init__.py    # Public API exports
```

### Data Flow

```
User Message -> LLM -> Tool Call -> ToolExecutor -> ToolRegistry -> Tool.execute()
                                                        |
User Response <- LLM <- Tool Result <- ToolExecutor <---+
```
