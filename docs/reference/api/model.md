# Model API

> [Home](../README.md) → [API](.) → Model

**File:** `gptase/models/model.py`, `gptase/models/types.py`, `gptase/models/providers.py`

---

## Model

Central LLM interface. All models go through OpenAI-compatible APIs (e.g. aiping.cn).

```python
from gptase.models.model import Model

model = Model(
    default_config: Optional[ModelConfig] = None,   # auto-loads FrameworkConfig if None
    enable_tracking: bool = False,
    tracking_db_path: str = "data/conversations.db",
)
```

Provider instances are cached by `(base_url, api_key)` — HTTP connections are reused across calls.

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
model.create_provider(config: ModelConfig) -> OpenAIProvider | LocalProvider

await model.initialize_tracking()       # call before generate() if enable_tracking=True
await model.health_check(config=None) -> Dict
await model.shutdown()                  # call at program exit if tracking enabled
model.get_usage_stats() -> Dict
```

---

## ModelConfig

```python
from gptase.models.types import ModelConfig

config = ModelConfig(
    model_name: str = "gpt-4",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,      # e.g. "https://aiping.cn/api/v1"
    temperature: float = 0.1,
    max_tokens: int = 131072,
    timeout: int = 30,
    max_retries: int = 3,
    stream: bool = True,                 # enable streaming
    enable_thinking: bool = False,       # enable reasoning mode
    provider: Optional[Dict[str, Any]] = None,  # provider routing/options via extra_body.provider
    use_mock: bool = False,              # use LocalProvider for testing
    persist_response: bool = False,
    system_prompt: Optional[str] = None,
)
```

---

## ModelResponse

```python
class ModelResponse(BaseModel):
    content: str
    reasoning_content: Optional[str]   # thinking / chain-of-thought output
    usage: Dict[str, int]              # {"prompt_tokens": N, "completion_tokens": N}
    model: str
    provider: str                      # actual provider name (e.g. from aiping.cn)
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

All production calls go through `OpenAIProvider`, which wraps the OpenAI SDK for any OpenAI-compatible endpoint. `LocalProvider` exists only for testing (activated via `ModelConfig(use_mock=True)`).

---

*Related: [Config API →](./config.md) | [Memory API →](./memory.md)*
