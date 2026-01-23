# TrackingMixin Usage Guide

## Overview

`TrackingMixin` is a reusable mixin class for tools that need to track their LLM calls with `agent_id`, `session_id`, and `step_id` parameters. It eliminates code duplication and provides a consistent interface for conversation tracking.

## Benefits

1. **Code Reuse**: Don't repeat tracking parameter initialization in every tool
2. **Consistency**: All tracking-aware tools use the same interface
3. **Maintainability**: Add new tracking parameters in one place
4. **Cleaner Code**: Use `**self.get_tracking_params()` instead of listing all parameters

## How to Use

### Basic Implementation

```python
from src.tools.base import BaseTool
from src.tools.tracking_mixin import TrackingMixin
from src.tools.base import ToolResult

class MyCustomTool(BaseTool, TrackingMixin):
    """A tool that uses LLM calls with tracking."""

    def __init__(
        self,
        model_manager,
        agent_id=None,
        session_id=None,
        step_id=None,
        # ... other tool-specific parameters
    ):
        # Initialize BaseTool
        BaseTool.__init__(
            self,
            name="my_custom_tool",
            description="Description of what this tool does",
            timeout=30,
        )

        # Initialize TrackingMixin
        TrackingMixin.__init__(self, agent_id, session_id, step_id)

        # Tool-specific initialization
        self.model_manager = model_manager

    async def execute(self, **kwargs):
        """Execute the tool with tracking enabled."""

        # Method 1: Explicit parameters (old way, still works)
        response = await self.model_manager.generate(
            messages,
            agent_id=self.agent_id,
            session_id=self.session_id,
            step_id=self.step_id,
        )

        # Method 2: Using get_tracking_params() (recommended, cleaner)
        response = await self.model_manager.generate(
            messages,
            **self.get_tracking_params(),  # Automatically expands to the three parameters above
        )

        return ToolResult.success(response)
```

### Example: Enzyme Design Parser

If you were to create an enzyme design parser tool with tracking:

```python
from src.tools.base import BaseTool, ToolResult
from src.tools.tracking_mixin import TrackingMixin

class EnzymeDesignParser(BaseTool, TrackingMixin):
    """Parse enzyme design workflows from literature."""

    def __init__(
        self,
        model_manager,
        agent_id=None,
        session_id=None,
        step_id=None,
    ):
        BaseTool.__init__(
            self,
            name="enzyme_design_parser",
            description="Extract enzyme design workflow information",
            timeout=60,
        )
        TrackingMixin.__init__(self, agent_id, session_id, step_id)
        self.model_manager = model_manager

    async def execute(self, document_text: str) -> ToolResult:
        """Parse design workflow with tracking."""

        messages = [
            {"role": "system", "content": "You are an expert in protein engineering."},
            {"role": "user", "content": f"Extract design workflow from:\n{document_text}"}
        ]

        # Clean LLM call with automatic tracking
        response = await self.model_manager.generate(
            messages,
            **self.get_tracking_params(),
        )

        return ToolResult.success({"workflow": response.content})
```

## Advanced Usage

### Dynamic Tracking Updates

You can update tracking parameters during execution:

```python
class MultiStepProcessor(BaseTool, TrackingMixin):
    """Processes multiple steps, each with its own step_id."""

    async def execute(self, tasks: list) -> ToolResult:
        results = []

        for i, task in enumerate(tasks):
            # Update step_id for each iteration
            step_id = f"step_{i+1}"
            self.update_tracking(step_id=step_id)

            # This LLM call will use the new step_id
            response = await self.model_manager.generate(
                messages,
                **self.get_tracking_params(),
            )

            results.append(response)

        return ToolResult.success(results)
```

### Conditional Tracking

Only include non-None tracking parameters:

```python
# Only includes parameters that are not None
params = self.get_tracking_params()
# If agent_id=None, session_id="abc", step_id="123"
# Returns: {'session_id': 'abc', 'step_id': '123'}
# Does NOT include agent_id since it's None
```

## Existing Tools Using TrackingMixin

- ✅ `DocumentStructureAnalyzer` - Analyzes document structure and extracts tables
- 🔄 Add your tool here!

## Migration Guide

### Before (Repetitive Code)

```python
class MyTool(BaseTool):
    def __init__(self, model_manager, agent_id=None, session_id=None, step_id=None):
        super().__init__(name="my_tool", description="...")
        self.model_manager = model_manager
        self.agent_id = agent_id        # Repetitive
        self.session_id = session_id    # Repetitive
        self.step_id = step_id          # Repetitive

    async def execute(self, **kwargs):
        # Repetitive parameter passing
        await self.model_manager.generate(
            messages,
            agent_id=self.agent_id,
            session_id=self.session_id,
            step_id=self.step_id,
        )
```

### After (Clean with TrackingMixin)

```python
class MyTool(BaseTool, TrackingMixin):
    def __init__(self, model_manager, agent_id=None, session_id=None, step_id=None):
        BaseTool.__init__(self, name="my_tool", description="...")
        TrackingMixin.__init__(self, agent_id, session_id, step_id)  # One line!
        self.model_manager = model_manager

    async def execute(self, **kwargs):
        # Clean parameter passing
        await self.model_manager.generate(
            messages,
            **self.get_tracking_params(),  # One line!
        )
```

## API Reference

### `TrackingMixin.__init__(agent_id=None, session_id=None, step_id=None)`

Initialize tracking parameters.

**Parameters:**
- `agent_id` (str, optional): Agent identifier
- `session_id` (str, optional): Session identifier
- `step_id` (str, optional): Step identifier

### `get_tracking_params() -> dict`

Get tracking parameters as a dictionary. Only includes non-None values.

**Returns:**
 Dictionary with tracking parameters suitable for `**kwargs` expansion.

### `update_tracking(agent_id=None, session_id=None, step_id=None)`

Update tracking parameters. Only updates parameters that are not None.

**Parameters:**
- `agent_id` (str, optional): New agent ID
- `session_id` (str, optional): New session ID
- `step_id` (str, optional): New step ID
