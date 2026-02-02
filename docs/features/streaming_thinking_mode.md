# Streaming Support with Thinking Mode

Detailed documentation for real-time streaming of LLM responses with optional thinking/reasoning mode.

## Overview

The framework supports real-time streaming of LLM responses with optional thinking/reasoning mode, allowing you to:
- See responses as they're generated (reduced latency perception)
- Access the model's reasoning process (when supported)
- Handle different types of content chunks separately

## Basic Usage

### Simple Streaming

```python
from src.models.types import ModelRole
from src.utils import default_manager

manager = default_manager()

async def stream_example():
    messages = [
        {"role": "user", "content": "Explain enzyme kinetics"}
    ]

    async for chunk in manager.generate_stream(
        messages,
        role=ModelRole.GENERAL
    ):
        if chunk.content:
            print(chunk.content, end="", flush=True)
        if chunk.is_complete:
            print("\n\nStreaming complete!")
```

### Streaming with Thinking Mode

```python
async def stream_with_thinking():
    config = manager.get_role_config(ModelRole.GENERAL)
    config_with_thinking = config.model_copy(update={"enable_thinking": True})

    messages = [
        {"role": "user", "content": "Analyze this experimental design..."}
    ]

    async for chunk in manager.generate_stream(
        messages,
        role=ModelRole.GENERAL,
        config=config_with_thinking
    ):
        if chunk.is_thinking and chunk.reasoning_content:
            print(f"[Thinking] {chunk.reasoning_content}")
        elif chunk.content:
            print(f"[Answer] {chunk.content}")
        if chunk.is_complete:
            print("\n\nComplete!")
```

## StreamChunk Type

The `StreamChunk` type provides the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `content` | str | Response text chunk |
| `reasoning_content` | str | Thinking/reasoning chunk (when thinking mode enabled) |
| `is_thinking` | bool | Whether current chunk is reasoning content |
| `is_complete` | bool | Whether streaming is complete |
| `metadata` | object | Usage info, errors, etc. |

### Chunk Processing Pattern

```python
async for chunk in manager.generate_stream(messages, role=ModelRole.GENERAL):
    # Handle reasoning/thinking content
    if chunk.is_thinking and chunk.reasoning_content:
        process_thinking(chunk.reasoning_content)

    # Handle response content
    if chunk.content:
        process_content(chunk.content)

    # Handle completion
    if chunk.is_complete:
        handle_complete(chunk.metadata)
```

## Enabling Thinking Mode

### Method 1: Configuration File

Enable thinking mode globally in `config/llm_config.template.json`:

```json
{
  "model_name": "claude-sonnet-4-20250514",
  "api_key": "your-api-key",
  "enable_thinking": true,
  "provider_config": {
    "stream": true,
    "extra_body": {
      "enable_thinking": true
    }
  }
}
```

This will enable thinking mode for all LLM calls automatically. The `FrameworkConfig` class properly loads these settings and passes them to `ModelConfig`, which then uses them when constructing API requests.

### Method 2: Runtime Configuration

Enable thinking mode programmatically:

```python
from src.models.config import ModelConfig

config = ModelConfig(
    model_name="claude-sonnet-4-20250514",
    api_key="your-api-key",
    enable_thinking=True,
    provider_config={
        "stream": True,
        "extra_body": {"enable_thinking": True}
    }
)

manager = ModelManager(config)
```

### Method 3: Per-Call Configuration

Enable thinking mode for specific calls:

```python
base_config = manager.get_role_config(ModelRole.GENERAL)
thinking_config = base_config.model_copy(update={"enable_thinking": True})

async for chunk in manager.generate_stream(
    messages,
    role=ModelRole.GENERAL,
    config=thinking_config
):
    # Process chunks with thinking enabled
    ...
```

## Model Support

### Models with Thinking Mode Support

- **Claude 3.5 Sonnet** (extended thinking)
- **Claude 3 Opus** (extended thinking)
- **Custom models** that support reasoning content

### Models without Thinking Mode

For models that don't support thinking mode:
- `is_thinking` will always be `False`
- `reasoning_content` will always be `None`
- Streaming works normally for response content

## Advanced Usage

### Custom Content Handlers

```python
class StreamingProcessor:
    def __init__(self):
        self.thinking_buffer = []
        self.content_buffer = []

    async def process_stream(self, manager, messages, config):
        async for chunk in manager.generate_stream(
            messages,
            role=ModelRole.GENERAL,
            config=config
        ):
            if chunk.is_thinking and chunk.reasoning_content:
                await self.handle_thinking(chunk.reasoning_content)
            elif chunk.content:
                await self.handle_content(chunk.content)

            if chunk.is_complete:
                await self.handle_complete(chunk.metadata)

    async def handle_thinking(self, content):
        self.thinking_buffer.append(content)
        print(f"[Thinking] {content}")

    async def handle_content(self, content):
        self.content_buffer.append(content)
        print(f"[Content] {content}")

    async def handle_complete(self, metadata):
        print(f"\n[Complete] Tokens: {metadata.get('usage', {})}")
```

### Streaming to UI

```python
import streamlit as st

async def stream_to_ui(manager, messages, config):
    thinking_placeholder = st.empty()
    content_placeholder = st.empty()

    thinking_text = ""
    content_text = ""

    async for chunk in manager.generate_stream(
        messages,
        role=ModelRole.GENERAL,
        config=config
    ):
        if chunk.is_thinking and chunk.reasoning_content:
            thinking_text += chunk.reasoning_content
            with thinking_placeholder.container():
                st.markdown(f"**Thinking:**\n{thinking_text}")

        elif chunk.content:
            content_text += chunk.content
            with content_placeholder.container():
                st.markdown(content_text)

        if chunk.is_complete:
            thinking_placeholder.success("Thinking complete!")
            content_placeholder.success("Response complete!")
```

### Error Handling

```python
async def safe_stream(manager, messages, config):
    try:
        async for chunk in manager.generate_stream(
            messages,
            role=ModelRole.GENERAL,
            config=config
        ):
            if chunk.metadata and chunk.metadata.get("error"):
                handle_error(chunk.metadata["error"])
                break

            # Process chunk normally
            if chunk.content:
                print(chunk.content, end="")

    except Exception as e:
        print(f"Streaming error: {e}")
        # Handle cleanup, retry, etc.
```

## Performance Considerations

### Token Usage

Thinking mode may increase token usage:
- **Reasoning tokens**: Not typically charged for some providers
- **Response tokens**: Standard billing applies
- **Total tokens**: May be higher due to extended reasoning

Check `chunk.metadata.get("usage")` for actual token counts.

### Latency

**With thinking mode:**
- Initial response may be slower (model reasoning first)
- Content streaming may be faster (reasoning already done)

**Without thinking mode:**
- Immediate response start
- Steady streaming throughout

### Memory Management

For long-running streams:
```python
async def memory_efficient_stream(manager, messages):
    buffer = ""
    buffer_size = 0
    max_buffer_size = 10000  # Adjust as needed

    async for chunk in manager.generate_stream(messages):
        if chunk.content:
            buffer += chunk.content
            buffer_size += len(chunk.content)

            # Process and clear buffer periodically
            if buffer_size >= max_buffer_size:
                await process_chunk(buffer)
                buffer = ""
                buffer_size = 0

    # Process remaining content
    if buffer:
        await process_chunk(buffer)
```

## Use Cases

### 1. Real-Time Chat Interface

```python
async def chat_interface(user_message):
    messages = build_conversation_history(user_message)

    async for chunk in manager.generate_stream(
        messages,
        role=ModelRole.GENERAL
    ):
        if chunk.content:
            update_ui_in_real_time(chunk.content)
```

### 2. Document Analysis with Reasoning

```python
async def analyze_document(document_text):
    messages = [
        {
            "role": "user",
            "content": f"Analyze this document:\n\n{document_text}"
        }
    ]

    config = manager.get_role_config(ModelRole.GENERAL)
    config_with_thinking = config.model_copy(update={"enable_thinking": True})

    async for chunk in manager.generate_stream(
        messages,
        role=ModelRole.GENERAL,
        config=config_with_thinking
    ):
        if chunk.is_thinking:
            display_reasoning(chunk.reasoning_content)
        elif chunk.content:
            display_analysis(chunk.content)
```

### 3. Code Generation with Explanation

```python
async def generate_code_with_explanation(requirements):
    messages = [
        {
            "role": "user",
            "content": f"Generate code for: {requirements}"
        }
    ]

    config = manager.get_role_config(ModelRole.CODE_EXECUTION)
    config_with_thinking = config.model_copy(update={"enable_thinking": True})

    thinking = []
    code = []

    async for chunk in manager.generate_stream(
        messages,
        role=ModelRole.CODE_EXECUTION,
        config=config_with_thinking
    ):
        if chunk.is_thinking:
            thinking.append(chunk.reasoning_content)
        elif chunk.content:
            code.append(chunk.content)

    return {
        "reasoning": "".join(thinking),
        "code": "".join(code)
    }
```

## Troubleshooting

### Issue: No thinking content appears

**Possible causes:**
1. Model doesn't support thinking mode
2. `enable_thinking` not set correctly
3. Provider config missing `extra_body`

**Solution:**
```python
# Verify configuration
config = manager.get_role_config(ModelRole.GENERAL)
print(f"Thinking enabled: {config.enable_thinking}")
print(f"Provider config: {config.provider_config}")
```

### Issue: Streaming stops unexpectedly

**Possible causes:**
1. Network interruption
2. API error
3. Token limit reached

**Solution:**
```python
async for chunk in manager.generate_stream(messages):
    if chunk.metadata and chunk.metadata.get("error"):
        print(f"Error: {chunk.metadata['error']}")
        # Handle error (retry, notify user, etc.)
```

### Issue: High latency with thinking mode

**Possible causes:**
1. Model is doing extensive reasoning
2. Network latency
3. Provider-side processing

**Solution:**
- Use thinking mode selectively (for complex tasks only)
- Consider disabling for simple queries
- Monitor token usage and timing

## Best Practices

1. **Use thinking mode selectively** - Enable for complex tasks, disable for simple queries
2. **Handle errors gracefully** - Always check `chunk.metadata` for errors
3. **Provide user feedback** - Show thinking progress for long-running tasks
4. **Monitor token usage** - Check `metadata.usage` to track consumption
5. **Test without thinking first** - Verify basic functionality before enabling thinking mode

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - Main project documentation
- [src/models/types.py](../../src/models/types.py) - StreamChunk type definition
- [config/llm_config.template.json](../../config/llm_config.template.json) - Configuration examples
