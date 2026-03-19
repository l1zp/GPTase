# Model API

> [首页](../README.md) → [API](.) → Model

**文件：** `gptase/models/model.py`、`gptase/models/types.py`、`gptase/models/providers.py`

---

## Model

LLM 核心接口。所有模型调用统一通过 OpenAI 兼容 API（如 aiping.cn）。

```python
from gptase.models.model import Model

model = Model(
    default_config: Optional[ModelConfig] = None,   # 为 None 时自动加载 FrameworkConfig
    enable_tracking: bool = False,
    tracking_db_path: str = "data/conversations.db",
)
```

Provider 实例按 `(base_url, api_key)` 缓存，跨调用复用 HTTP 连接。

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
model.create_provider(config: ModelConfig) -> OpenAIProvider | LocalProvider

await model.initialize_tracking()       # 启用追踪时，在 generate() 前调用
await model.health_check(config=None) -> Dict
await model.shutdown()                  # 启用追踪时，程序退出前调用
model.get_usage_stats() -> Dict
```

---

## ModelConfig

```python
from gptase.models.types import ModelConfig

config = ModelConfig(
    model_name: str = "gpt-4",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,      # 如 "https://aiping.cn/api/v1"
    temperature: float = 0.1,
    max_tokens: int = 2000,
    timeout: int = 30,
    max_retries: int = 3,
    stream: bool = True,                 # 启用流式输出
    enable_thinking: bool = False,       # 启用推理模式
    use_mock: bool = False,              # 使用 LocalProvider 进行测试
    persist_response: bool = False,
    system_prompt: Optional[str] = None,
)
```

---

## ModelResponse

```python
class ModelResponse(BaseModel):
    content: str
    reasoning_content: Optional[str]   # thinking / 推理输出
    usage: Dict[str, int]              # {"prompt_tokens": N, "completion_tokens": N}
    model: str
    provider: str                      # 实际服务商名称（如 aiping.cn 返回的）
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

所有生产环境调用统一通过 `OpenAIProvider`，它封装了 OpenAI SDK 来调用任何 OpenAI 兼容端点。`LocalProvider` 仅用于测试（通过 `ModelConfig(use_mock=True)` 激活）。

---

*相关：[Config API →](./config.md) | [Memory API →](./memory.md)*
