# Technical Features

This guide covers advanced technical features in the GPTase framework.

## Table of Contents

1. [Thinking Mode](#thinking-mode)
2. [TrackingMixin for LLM Call Tracking](#trackingmixin-for-llm-call-tracking)

---

## Thinking Mode

### Overview

Thinking mode allows LLMs to show their reasoning process before generating the final answer. This is useful for:

- Complex problem analysis and reasoning
- Tasks requiring chain-of-thought
- Debugging and understanding model thought process
- Educational and demonstration scenarios

### Supported Models

**OpenAI Series:**
- o1-preview
- o1-mini
- Other models supporting reasoning

**Domestic Models:**
- Qwen/QwQ series (e.g., Qwen3-235B-A22B)
- Other models supporting `enable_thinking` parameter

> **Note**: Not all models support thinking mode. Unsupported models will return answers directly without showing reasoning.

### Enabling Thinking Mode

#### Method 1: In Code

```python
from src.models.types import ModelConfig
from src.utils import default_manager
from src.models.types import ModelRole

manager = default_manager()
config = ModelConfig(enable_thinking=True)

messages = [{"role": "user", "content": "Explain quantum computing"}]

async for chunk in manager.generate_stream(
    messages,
    role=ModelRole.GENERAL,
    config=config
):
    if chunk.is_thinking:
        print(f"Thinking: {chunk.reasoning_content}")
    elif chunk.content:
        print(f"Answer: {chunk.content}")
```

#### Method 2: Configuration File

Edit `config/llm_config.template.json`:

```json
{
  "model_name": "Qwen3-235B-A22B",
  "api_key": "your-api-key",
  "enable_thinking": true,
  "provider_config": {
    "stream": true
  }
}
```

#### Method 3: Command Line

```bash
# Stream with thinking (default)
python examples/chat_demo.py

# Disable thinking
python examples/chat_demo.py --no-thinking

# Simple mode (non-streaming)
python examples/chat_demo.py --simple
```

### StreamChunk Structure

| Field | Type | Description |
|-------|------|-------------|
| `content` | str | Response text chunk |
| `reasoning_content` | str | Thinking/reasoning chunk |
| `is_thinking` | bool | Whether current chunk is reasoning |
| `is_complete` | bool | Whether streaming is complete |
| `metadata` | dict | Usage info, errors |

### Technical Details

**API Call:**
```python
completion = client.chat.completions.create(
    model="Qwen3-235B-A22B",
    messages=messages,
    stream=True,
    extra_body={"enable_thinking": True}  # Key parameter
)
```

**Response Flow:**
```
[Start] → [Thinking Phase] → [Answer Phase] → [Complete]
           (reasoning_       (content
            content)         field)
```

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_thinking` | bool | False | Enable thinking mode |
| `stream` | bool | False | Use streaming output |

### Troubleshooting

**Problem: No thinking process visible**

1. Check if model supports `reasoning_content`
2. Verify API endpoint supports `extra_body`
3. Confirm `enable_thinking` is set to `True`

**Problem: Error "extra_body not supported"**

- Update API library version
- Use provider-specific SDK
- Contact API provider for support

---

## TrackingMixin for LLM Call Tracking

### Overview

`TrackingMixin` is a reusable mixin class for tools that need to track LLM calls with `agent_id`, `session_id`, and `step_id` parameters.

### Benefits

1. **Code Reuse**: Eliminate repetitive tracking parameter initialization
2. **Consistency**: Uniform interface across tracking-aware tools
3. **Maintainability**: Add new tracking parameters in one place
4. **Cleaner Code**: Use `**self.get_tracking_params()` instead of listing all parameters

### Basic Implementation

```python
from src.tools.base import BaseTool, ToolResult
from src.tools.tracking_mixin import TrackingMixin

class MyCustomTool(BaseTool, TrackingMixin):
    """A tool that uses LLM calls with tracking."""

    def __init__(
        self,
        model_manager,
        agent_id=None,
        session_id=None,
        step_id=None,
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

        # Clean LLM call with automatic tracking
        response = await self.model_manager.generate(
            messages,
            **self.get_tracking_params(),  # Expands to the three parameters
        )

        return ToolResult.success(response)
```

### Migration Guide

#### Before (Repetitive Code)

```python
class MyTool(BaseTool):
    def __init__(self, model_manager, agent_id=None, session_id=None, step_id=None):
        super().__init__(name="my_tool", description="...")
        self.model_manager = model_manager
        self.agent_id = agent_id        # Repetitive
        self.session_id = session_id    # Repetitive
        self.step_id = step_id          # Repetitive

    async def execute(self, **kwargs):
        await self.model_manager.generate(
            messages,
            agent_id=self.agent_id,
            session_id=self.session_id,
            step_id=self.step_id,
        )
```

#### After (Clean with TrackingMixin)

```python
class MyTool(BaseTool, TrackingMixin):
    def __init__(self, model_manager, agent_id=None, session_id=None, step_id=None):
        BaseTool.__init__(self, name="my_tool", description="...")
        TrackingMixin.__init__(self, agent_id, session_id, step_id)
        self.model_manager = model_manager

    async def execute(self, **kwargs):
        await self.model_manager.generate(
            messages,
            **self.get_tracking_params(),  # One line!
        )
```

### Advanced Usage

#### Dynamic Tracking Updates

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

#### Conditional Tracking

```python
# Only includes parameters that are not None
params = self.get_tracking_params()
# If agent_id=None, session_id="abc", step_id="123"
# Returns: {'session_id': 'abc', 'step_id': '123'}
# Does NOT include agent_id since it's None
```

### API Reference

#### `TrackingMixin.__init__(agent_id=None, session_id=None, step_id=None)`

Initialize tracking parameters.

**Parameters:**
- `agent_id` (str, optional): Agent identifier
- `session_id` (str, optional): Session identifier
- `step_id` (str, optional): Step identifier

#### `get_tracking_params() -> dict`

Get tracking parameters as a dictionary. Only includes non-None values.

**Returns:**
Dictionary with tracking parameters suitable for `**kwargs` expansion.

#### `update_tracking(agent_id=None, session_id=None, step_id=None)`

Update tracking parameters. Only updates parameters that are not None.

**Parameters:**
- `agent_id` (str, optional): New agent ID
- `session_id` (str, optional): New session ID
- `step_id` (str, optional): New step ID

### Existing Tools Using TrackingMixin

- `DocumentStructureAnalyzer` - Analyzes document structure and extracts tables

---

## Related Links

- [OpenAI o1 Reasoning Guide](https://platform.openai.com/docs/guides/reasoning)
- [Qwen API Documentation](https://help.aliyun.com/zh/dashscope/developer-reference/qwen-api)
- [Main README](../README.md)
