# 环境搭建

## 安装

```bash
# 推荐：使用 Conda
conda create -n llm python=3.11 -y
conda activate llm
pip install -e .

# 或：使用 venv
python -m venv .venv && source .venv/bin/activate
pip install -e ".[models,dev]"
```

## LLM 配置

### 方式一：使用 .env 文件（推荐）

所有 API Key 统一通过 `.env` 文件管理：

```bash
# 复制模板
cp .env.example .env

# 编辑 .env，填入你的 API Key
vim .env
```

`.env` 文件内容：

```bash
# LLM Provider Keys
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
GEMINI_API_KEY=your-gemini-key

# Custom Provider
CUSTOM_API_KEY=your-custom-key
CUSTOM_BASE_URL=https://your-api-endpoint.com

# MCP Server Keys
BRAVE_API_KEY=your-brave-key
TAVILY_API_KEY=your-tavily-key

# MinerU Cloud API
MINERU_TOKEN=your-mineru-token
```

JSON 配置文件中无需填写 `api_key`，框架会自动从环境变量读取。

如果你会使用 `pdf-extractor` skill 处理 PDF，建议同时配置 `MINERU_TOKEN`：

- 配置了 `MINERU_TOKEN` 时，skill 会优先走 MinerU Cloud API，适合表格、公式、OCR、批量提取等高准确率场景
- 未配置时，skill 会退回到 `flash-extract` 或本地 CLI 流程

### 方式二：使用配置文件

`config/` 目录下提供了多个模型的配置模板：

| 文件 | 说明 |
|---|---|
| `llm_config.template.json` | 默认模板 |
| `llm_config.deepseek.json` | DeepSeek |
| `llm_config.glm5.json` | GLM-5 |
| `llm_config.minimax.json` | MiniMax |
| `llm_config.qwen.example.json` | Qwen |
| `llm_config.qwen_vl.example.json` | Qwen-VL（视觉）|

```bash
# 选择一个配置
export GPTASE_LLM_CONFIG=config/llm_config.glm5.json
```

配置文件示例（无需 api_key）：

```json
{
  "model_name": "GLM-5",
  "base_url": "https://aiping.cn/api/v1",
  "temperature": 0.1,
  "max_tokens": 131072,
  "timeout": 300,
  "stream": true
}
```

详见 [Config API →](./reference-zh/api/config.md)

### 按 Agent 指定模型

在配置文件中添加 `agent_models` 覆盖特定 Agent 的模型：

```json
{
  "agent_models": {
    "vision-image-analyzer": {
      "model_name": "Qwen3-VL-30B-A3B-Thinking",
      "base_url": "https://your-vision-endpoint/v1/",
      "max_tokens": 131072
    }
  }
}
```

> `agent_models` 才是 GPTase 当前生效的按 Agent 模型覆盖入口。`.claude/agents/*.md` frontmatter 中的 `model:` 目前不会被 `Agent.from_markdown()` 读取。

### 开启思维模式（Thinking Mode）

```json
{
  "enable_thinking": true
}
```

或在 `agent_models` 中按 Agent 单独配置：

```json
{
  "agent_models": {
    "vision-image-analyzer": {
      "enable_thinking": true
    }
  }
}
```

### Provider 路由选项

如果上游 OpenAI 兼容网关支持 provider 路由，可通过 `provider` 透传：

```json
{
  "provider": {
    "sort": "input_length"
  }
}
```

这会被发送为 `extra_body.provider`。常见用途是把长上下文请求路由到更适合的上游模型。

### MCP 工具服务器

可在配置文件中声明 MCP server，GPTase 会在 Claude SDK 路径和非 Claude `ToolExecutor` 路径中自动接入这些工具：

```json
{
  "mcp_servers": {
    "brave-search": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "YOUR_BRAVE_API_KEY"
      }
    },
    "tavily-search": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "tavily-mcp"],
      "env": {
        "TAVILY_API_KEY": "YOUR_TAVILY_API_KEY"
      }
    }
  }
}
```

支持的传输方式：
- `stdio`：通过本地命令启动 MCP server
- `sse`：通过远端 SSE URL 连接 MCP server

### 关于 `max_tokens` 与 413

- `max_tokens` 只控制输出 token 上限，不控制输入上下文总大小。
- 如果上游返回 `413 Request Entity Too Large`，优先检查输入消息、技能提示、工具返回内容是否过大。
- 对长上下文场景，可结合 `provider.sort = "input_length"` 使用更合适的上游路由。

## 验证安装

```bash
gptase --help
gptase list
pytest -v --tb=short              # full suite via pyproject testpaths
                                  # (tests/ + .claude/agents/*/tests/)
```

## 常见问题

**导入错误** → 确认已激活环境：`conda activate llm`

**API 连接失败** → 检查 `base_url` 格式、API Key 有效性，或增大 `timeout`

**模型找不到** → 核对 `model_name` 与 provider 的实际模型 ID 是否一致
