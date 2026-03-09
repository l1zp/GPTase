# Model API

> [首页](../README.md) → [API](.) → Model

**文件：** `gptase/models/model.py`、`gptase/models/types.py`、`gptase/models/providers.py`

---

## Model

LLM 核心接口。管理 Provider、按 Agent 的配置和可选的对话追踪。

```python
from gptase.models.model import Model

model = Model(
    default_config: Optional[ModelConfig] = None,   # 为 None 时自动加载 FrameworkConfig
    enable_tracking: bool = False,
    tracking_db_path: str = "data/conversations.db",
)
```

Provider 实例按 `(provider_key, base_url, api_key)` 缓存，跨调用复用 HTTP 连接。

### `generate()`

```python
response = await model.generate(
    messages: List[Dict[str, str]],
    config: Optional[ModelConfig] = None,
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,    # 触发按 Agent 的模型配置查找
    session_id: Optional[str] = None,
    step_id: Optional[str] = None,
    tools: Optional[List[Dict]] = None,  # OpenAI function calling schema
) -> ModelResponse
```

提供 `agent_name`（且不提供 `config`）时，`get_config_for_agent()` 从 `FrameworkConfig.agent_models` 解析模型配置。

### `generate_with_retry()`

```python
response = await model.generate_with_retry(
    messages: List[Dict[str, str]],
    config: Optional[ModelConfig] = None,
    max_retries: int = 3,
    agent_name: Optional[str] = None,
) -> ModelResponse
```

使用指数退避：每次重试等待 `2^attempt` 秒。

### 流式输出 {#流式输出}

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
        print(f"[思考] {chunk.reasoning_content}")
    if chunk.is_complete:
        break
```

### 其他方法

```python
model.get_config_for_agent(agent_name: str, default_config=None) -> ModelConfig
model.create_provider(config: ModelConfig) -> BaseProvider
model.register_provider(name: str, provider_class: type[BaseProvider])

await model.initialize_tracking()       # 启用追踪时，在 generate() 前调用
await model.health_check(provider=None) -> Dict
await model.shutdown()                  # 启用追踪时，程序退出前调用
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
    base_url: Optional[str] = None,      # 自定义端点（DeepSeek、Ollama 等）
    temperature: float = 0.1,
    max_tokens: int = 2000,
    timeout: int = 30,
    max_retries: int = 3,
    thinking: Optional[ThinkingConfig] = None,
    enable_thinking: bool = False,       # 旧版格式
    provider_config: Dict[str, Any] = {},
    persist_response: bool = False,
    system_prompt: Optional[str] = None,
)

config.is_thinking_enabled() -> bool
```

`is_thinking_enabled()` 依次检查：
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
    reasoning_content: Optional[str]   # thinking / 推理输出
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

    def save_json(file_path) -> str    # 将 chunk 保存到 JSON 文件
```

---

## 多模态内容类型

```python
from gptase.models.types import TextContent, ImageUrlContent

TextContent(type="text", text="...")
ImageUrlContent(
    type="image_url",
    image_url={"url": "data:image/png;base64,..."}
)

MultimodalContent = Union[TextContent, ImageUrlContent, Dict[str, Any]]
```

这些类型在内部构建多模态消息列表时使用。

---

## Provider

### 新增自定义 Provider

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

    # 可选：支持流式输出
    async def generate_stream(
        self, messages: List[Dict]
    ) -> AsyncGenerator[StreamChunk, None]: ...

# 注册
model.register_provider("myprovider", MyProvider)
```

同时需要在 `gptase/models/types.py` 的 `ModelProvider` 枚举中添加 `"myprovider"`。

---

*相关：[Config API →](./config.md) | [Memory API →](./memory.md)*
