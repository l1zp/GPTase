# Model API

> [Home](../README.md) → [API](.) → Model

**File:** `gptase/models/model.py`, `gptase/models/types.py`, `gptase/models/providers.py`

---

## Model

Central LLM interface. Manages providers, per-agent config, and optional tracking.

```python
from gptase.models.model import Model

model = Model(
    default_config: Optional[ModelConfig] = None,   # auto-loads FrameworkConfig if None
    enable_tracking: bool = False,
    tracking_db_path: str = "data/conversations.db",
)
```

Provider instances are cached by `(provider_key, base_url, api_key)` — HTTP connections are reused across calls.

### `generate()`

```python
response = await model.generate(
    messages: List[Dict[str, str]],
    config: Optional[ModelConfig] = None,
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,    # triggers per-agent config lookup
    session_id: Optional[str] = None,
    step_id: Optional[str] = None,
    tools: Optional[List[Dict]] = None,  # OpenAI function calling schemas
) -> ModelResponse
```

When `agent_name` is provided (and `config` is not), `get_config_for_agent()` resolves the model config from `FrameworkConfig.agent_models`.

### `generate_with_retry()`

```python
response = await model.generate_with_retry(
    messages: List[Dict[str, str]],
    config: Optional[ModelConfig] = None,
    max_retries: int = 3,
    agent_name: Optional[str] = None,
) -> ModelResponse
```

Uses exponential backoff: waits `2^attempt` seconds between retries.

### Streaming {#streaming}

```python
async for chunk in model.generate_stream(
    messages: List[Dict[str, str]],
    config: Optional[ModelConfig] = None,
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    session_id: Optional[str] = None,
    step_id: Optional[str] = None,
):
    print(chunk.content, end="")
    if chunk.reasoning_content:
        print(f"[thinking] {chunk.reasoning_content}")
    if chunk.is_complete:
        break
```

### Other methods

```python
model.get_config_for_agent(agent_name: str, default_config=None) -> ModelConfig
model.create_provider(config: ModelConfig) -> BaseProvider
model.register_provider(name: str, provider_class: type[BaseProvider])

await model.initialize_tracking()       # call before generate() if enable_tracking=True
await model.health_check(provider=None) -> Dict
await model.shutdown()                  # call at program exit if tracking enabled
model.get_usage_stats() -> Dict
```

---

## ModelConfig

```python
from gptase.models.types import ModelConfig, ThinkingConfig

config = ModelConfig(
    provider: str = "openai",            # "openai" | "local"
    model_name: str = "gpt-4",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,      # custom endpoint (DeepSeek, Ollama, etc.)
    temperature: float = 0.1,
    max_tokens: int = 2000,
    timeout: int = 30,
    max_retries: int = 3,
    thinking: Optional[ThinkingConfig] = None,
    enable_thinking: bool = False,       # legacy format
    provider_config: Dict[str, Any] = {},
    persist_response: bool = False,
    system_prompt: Optional[str] = None,
)

config.is_thinking_enabled() -> bool
```

`is_thinking_enabled()` checks in order:
1. `thinking.type == "enabled"`
2. `enable_thinking == True`
3. `provider_config["extra_body"]["enable_thinking"] == True`

### ThinkingConfig

```python
ThinkingConfig(type: str = "disabled")  # "enabled" | "disabled"
```

---

## ModelResponse

```python
class ModelResponse(BaseModel):
    content: str
    reasoning_content: Optional[str]   # thinking / chain-of-thought output
    usage: Dict[str, int]              # {"prompt_tokens": N, "completion_tokens": N}
    model: str
    provider: str
    tool_calls: Optional[List[ToolCall]]
    finish_reason: Optional[str]       # "stop" | "tool_calls"
    metadata: Dict[str, Any]
```

---

## StreamChunk

```python
class StreamChunk(BaseModel):
    content: str = ""
    reasoning_content: str = ""
    is_thinking: bool = False
    is_complete: bool = False
    chunk_index: int = 0
    metadata: Dict[str, Any]

    def save_json(file_path) -> str    # saves chunk to JSON file
```

---

## Multimodal Content Types

```python
from gptase.models.types import TextContent, ImageUrlContent

TextContent(type="text", text="...")
ImageUrlContent(
    type="image_url",
    image_url={"url": "data:image/png;base64,..."}
)

MultimodalContent = Union[TextContent, ImageUrlContent, Dict[str, Any]]
```

These types are used internally when building multimodal message lists.

---

## Providers

### Adding a custom provider

```python
from gptase.models.providers import BaseProvider
from gptase.models.types import ModelConfig, ModelResponse

class MyProvider(BaseProvider):
    def __init__(self, config: ModelConfig): ...

    async def generate(
        self, messages: List[Dict], tools=None
    ) -> ModelResponse: ...

    async def validate_config(self) -> None: ...

    async def health_check(self) -> Dict[str, Any]: ...

    # optional: for streaming support
    async def generate_stream(
        self, messages: List[Dict]
    ) -> AsyncGenerator[StreamChunk, None]: ...

# Register
model.register_provider("myprovider", MyProvider)
```

Also add `"myprovider"` to the `ModelProvider` enum in `gptase/models/types.py`.

---

*Related: [Config API →](./config.md) | [Memory API →](./memory.md)*
