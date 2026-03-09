# Agent API

> [首页](../README.md) → [API](.) → Agent

**文件：** `gptase/agents/base.py`

---

## 创建 Agent

### 从 Markdown 定义创建（推荐）

```python
from gptase.agents.base import Agent
from gptase.models.model import Model

model = Model()

# 通过 Agent 名称（查找 .claude/agents/{name}.md）
agent = Agent.from_markdown("enzyme-kinetics-extractor", model_manager=model)

# 通过直接文件路径
agent = Agent.from_markdown("/path/to/agent.md", model_manager=model)

# 自定义搜索目录
agent = Agent.from_markdown("my-agent", config_dir=Path("/custom/agents/"))
```

名称查找同时支持连字符和下划线：`my-agent` 和 `my_agent` 都能找到同一个文件。

### 直接构造

```python
agent = Agent(
    system_prompt="你是一个有用的助手。",
    tools=["Read", "Grep", "Bash"],
    model_config=model_config,       # ModelConfig 实例
    model_name="claude-sonnet-4-6",  # 仅用于路由判断（当没有 model_config 时）
    agent_id="my-agent",
    workspace_dir="/path/to/workspace",
)
```

---

## 执行

### `run()` — 主入口

```python
result = await agent.run(
    content: Union[str, List[Dict]],     # 文本字符串或预构建的内容列表
    image_paths: Optional[List[str]] = None,
) -> Dict[str, Any]
```

**返回值：**
```python
{"status": "success", "data": {"content": "..."}}              # 成功
{"status": "error",   "error": "..."}                          # 出错
{"status": "error",   "error": "...", "agent_id": "..."}       # process_task 出错
```

**路由逻辑：** `model_name.startswith("claude-")` → Claude SDK；否则 → LLM 循环。

### `process_task()` — 结构化输入

```python
result = await agent.process_task(task: AgentTask) -> Dict[str, Any]
```

从 task 中提取图片路径，将 task 字段序列化为 JSON 注入 prompt，然后调用 `run()`。

### `is_claude_model()`

```python
agent.is_claude_model() -> bool
```

检查 `model_name.startswith("claude-")`，内部用于路由判断。

---

## AgentTask

**文件：** `gptase/agents/types.py`

Pydantic 模型，设置 `extra="allow"` — 任何额外字段都被接受并以 JSON 形式注入 prompt。

```python
from gptase.agents.types import AgentTask

task = AgentTask(
    description="提取酶动力学参数",              # 可选，默认："Process the following data"
    workspace_dir="/path/to/workspace",          # 可选
    image_path="single.png",                     # 可选，单张图片
    image_paths=["img1.png", "img2.png"],        # 可选，图片列表
    images=["img3.png"],                         # 可选，备选图片字段
    # 任意额外字段：
    document_text="...",
    source="Nature 2024",
)

task.to_dict()           # 排除 None 值
task.get_extra_fields()  # 只返回未声明的额外字段
AgentTask.from_dict(data_dict)
```

图片去重：三个图片字段（`image_path`、`image_paths`、`images`）合并去重，保留顺序。

---

## 图片加载 {#图片加载}

`Agent._load_image_as_content(image_path)` 对每张图片执行：

1. 以二进制模式读取文件
2. Base64 编码内容
3. 根据文件扩展名检测 MIME 类型

| 扩展名 | MIME 类型 |
|---|---|
| `.jpg`, `.jpeg` | `image/jpeg` |
| `.png` | `image/png` |
| `.gif` | `image/gif` |
| `.webp` | `image/webp` |
| 其他 | `image/jpeg`（回退） |

返回：
```python
{
    "type": "image_url",
    "image_url": {"url": "data:image/png;base64,<编码内容>"}
}
```

图片列表前置于消息内容，文本跟在最后。文件不存在或加载失败时记录警告，跳过（非致命错误）。

---

## Markdown 格式 {#markdown-格式}

`.claude/agents/` 中的 Agent 文件必须包含 YAML 头部：

```markdown
---
name: my-agent
description: 一句话描述这个 Agent 的用途
tools: Read, Grep, Glob, Bash
model: claude-sonnet-4-6
color: blue
---

系统 prompt 正文从这里开始。--- 之后的所有内容都是 system_prompt。

## 工作流程
...

## 输出格式
...
```

| 头部字段 | 是否必填 | 说明 |
|---|---|---|
| `name` | 是 | Agent ID — 必须与文件名（不含扩展名）匹配 |
| `description` | 是 | 显示在 `gptase list` 输出中 |
| `tools` | 否 | 逗号分隔的工具名称列表 |
| `model` | 否 | 该 Agent 的模型覆盖配置 |
| `color` | 否 | 在 Claude Code 界面中的显示颜色 |

---

## AgentDefinition 与 AgentState

```python
@dataclass
class AgentDefinition:
    name: str
    description: str = ""
    tools: List[str] = field(default_factory=list)
    system_prompt: str = ""

    @property
    def agent_id(self) -> str: ...  # name 的别名

class AgentState(BaseModel):
    agent_id: str
    status: str = "idle"
    current_task: Optional[str] = None
```

---

*相关：[SOP API →](./sop.md) | [Model API →](./model.md)*
