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
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
GEMINI_API_KEY=your-gemini-key

# Custom Provider
CUSTOM_API_KEY=your-custom-key
CUSTOM_BASE_URL=https://your-api-endpoint.com

# MCP Server Keys
BRAVE_API_KEY=your-brave-key
TAVILY_API_KEY=your-tavily-key
```

JSON 配置文件中无需填写 `api_key`，框架会自动从环境变量读取。

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
  "max_tokens": 4096,
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
      "max_tokens": 8192
    }
  }
}
```

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

## 验证安装

```bash
gptase --help
gptase list
gptase plan --list
pytest tests/ -v --tb=short
```

## 常见问题

**导入错误** → 确认已激活环境：`conda activate llm`

**API 连接失败** → 检查 `base_url` 格式、API Key 有效性，或增大 `timeout`

**模型找不到** → 核对 `model_name` 与 provider 的实际模型 ID 是否一致
