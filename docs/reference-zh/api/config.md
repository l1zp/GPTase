# Config API

> [首页](../README.md) → [API](.) → Config

**文件：** `gptase/utils/config.py`

---

## FrameworkConfig

所有框架配置的单一来源，从 JSON 模板文件加载一次后全局使用。

```python
from gptase.utils.config import FrameworkConfig

config = FrameworkConfig()                            # 从模板加载
config = FrameworkConfig(llm_model="gpt-4o")         # 覆盖特定字段
config = FrameworkConfig(**json.load(open("f.json"))) # 从字典加载
```

### 字段

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `llm_model` | `str` | `"gpt-4"` | 默认模型名称 |
| `llm_api_key` | `Optional[str]` | 环境变量 `OPENAI_API_KEY` | API Key |
| `llm_base_url` | `Optional[str]` | `"https://aiping.cn/api/v1"` | API 端点 URL |
| `llm_temperature` | `float` | `0.1` | 采样温度 |
| `llm_max_tokens` | `int` | `131072` | 最大输出 token 数 |
| `llm_timeout` | `Optional[int]` | `None` → `600` | 请求超时（秒） |
| `llm_stream` | `bool` | `True` | 启用流式输出 |
| `llm_enable_thinking` | `bool` | `False` | 启用推理/思考模式 |
| `llm_provider` | `Optional[Dict[str, Any]]` | `None` | 通过 `extra_body.provider` 透传给上游的 provider 路由/选项 |
| `agent_models` | `Dict[str, Dict]` | `{}` | 按 Agent 的模型覆盖 |
| `memory` | `MemoryConfig` | — | 内存子系统配置 |
| `log_level` | `str` | `"INFO"` | 日志级别 |

### 方法

```python
config.to_model_config() -> ModelConfig
# 使用默认 llm_* 字段转换为 ModelConfig。

config.get_config_for_agent(agent_name: str) -> Optional[ModelConfig]
# 查找 agent_models[agent_name]，与默认值合并，返回 ModelConfig。
# 自动处理连字符/下划线："my-agent" 和 "my_agent" 都能匹配。

config.to_dict() -> Dict[str, Any]
```

---

## 配置文件格式

### llm_config.template.json（完整示例）

> API Key 推荐通过 `.env` 文件管理，不在 JSON 中存储。

```json
{
  "model_name": "GLM-5",
  "base_url": "https://aiping.cn/api/v1",
  "temperature": 1,
  "max_tokens": 131072,
  "timeout": 300,
  "stream": true,
  "enable_thinking": false,
  "provider": {
    "sort": "input_length"
  },
  "agent_models": {
    "vision-image-analyzer": {
      "model_name": "Qwen3-VL-30B-A3B-Thinking",
      "max_tokens": 131072,
      "enable_thinking": true
    },
    "enzyme-kinetics-extractor": {
      "model_name": "GLM-5",
      "temperature": 0.1
    },
    "deep-research-eval-agent": {
      "provider": {
        "sort": "input_length"
      }
    }
  }
}
```

### JSON 键 → FrameworkConfig 字段映射

从 JSON 文件加载时，以下键名会被重新映射：

| JSON 键 | FrameworkConfig 字段 |
|---|---|
| `model_name` | `llm_model` |
| `api_key` | `llm_api_key` |
| `base_url` | `llm_base_url` |
| `temperature` | `llm_temperature` |
| `max_tokens` | `llm_max_tokens` |
| `timeout` | `llm_timeout` |
| `stream` | `llm_stream` |
| `enable_thinking` | `llm_enable_thinking` |
| `provider` | 当 JSON 值是对象时映射到 `llm_provider` |

不在此映射中的字段（如 `agent_models`、`memory`、`log_level`）直接透传。

> 为了兼容旧配置，标量型 `provider` 仍会被忽略；对象型 `provider` 现在保留给 provider 路由/选项透传。

---

## 环境变量

### .env 文件配置（推荐）

项目使用 `.env` 文件统一管理所有 API Key。框架启动时自动加载：

```bash
# 复制模板创建配置
cp .env.example .env

# 编辑填入真实 Key
vim .env
```

`.env` 文件格式：

```bash
# API Key（用于 aiping.cn 及其他 OpenAI 兼容端点）
OPENAI_API_KEY=your-api-key

# MCP Server Keys
BRAVE_API_KEY=your-brave-key
TAVILY_API_KEY=your-tavily-key
```

**优先级：** 配置文件中的 `api_key` > 环境变量 `OPENAI_API_KEY`

> 推荐做法：JSON 配置文件中不设置 `api_key`，统一通过 `.env` 管理。

### 支持的环境变量

| 变量 | 说明 |
|---|---|
| `OPENAI_API_KEY` | OpenAI 兼容端点的 API Key |
| `BRAVE_API_KEY` | MCP Brave Search 服务 Key |
| `TAVILY_API_KEY` | MCP Tavily Search 服务 Key |
| `GPTASE_LLM_CONFIG` | 自定义配置文件路径 |

### GPTASE_LLM_CONFIG

支持绝对路径和相对路径（相对路径从项目根目录解析）：

```bash
# 绝对路径
export GPTASE_LLM_CONFIG=/home/user/my_config.json

# 相对于项目根目录
export GPTASE_LLM_CONFIG=config/llm_config.glm5.json

# 单次命令覆盖
GPTASE_LLM_CONFIG=config/llm_config.glm5.json gptase plan -p my_pipeline -i paper.md
```

**加载优先级：**
1. `GPTASE_LLM_CONFIG` 环境变量
2. `config/llm_config.template.json`（默认）
3. 硬编码默认值（模板文件缺失时）

---

## MemoryConfig

```python
class MemoryConfig(BaseModel):
    type: str = "local"          # 存储类型
    max_history: int = 1000      # 最大历史条目数
```

---

## load_template_config()

`FrameworkConfig.__init__()` 内部使用的底层函数：

```python
from gptase.utils.config import load_template_config

raw_dict = load_template_config()   # 返回解析后的 JSON 字典
# 文件缺失或 JSON 格式错误时抛出 ConfigurationError
```

---

*相关：[Model API →](./model.md) | [Memory API →](./memory.md)*
