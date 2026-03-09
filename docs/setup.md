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

### 配置文件

`config/` 目录下提供了多个模型的配置模板：

| 文件 | 说明 |
|---|---|
| `llm_config.template.json` | 默认模板 |
| `llm_config.deepseek.json` | DeepSeek |
| `llm_config.glm5.json` | GLM-5 |
| `llm_config.minimax.json` | MiniMax |
| `llm_config.qwen.example.json` | Qwen |
| `llm_config.qwen_vl.example.json` | Qwen-VL（视觉）|

### 创建配置

```bash
cp config/llm_config.template.json config/llm_config.json
```

编辑 `config/llm_config.json`：

```json
{
  "model_name": "your-model",
  "api_key": "your-api-key",
  "base_url": "https://your-api-endpoint/v1/",
  "temperature": 0.1,
  "max_tokens": 4096,
  "timeout": 300,
  "provider": "openai"
}
```

使用环境变量也可以（`OPENAI_API_KEY` 或 `GPTASE_LLM_CONFIG`）。详见 [Config API →](./reference-zh/api/config.md)

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
  "thinking": { "type": "enabled" },
  "provider_config": {
    "extra_body": { "enable_thinking": true }
  }
}
```

## 验证安装

```bash
gptase --help
gptase list
gptase sop --list
pytest tests/ -v --tb=short
```

## 常见问题

**导入错误** → 确认已激活环境：`conda activate llm`

**API 连接失败** → 检查 `base_url` 格式、API Key 有效性，或增大 `timeout`

**模型找不到** → 核对 `model_name` 与 provider 的实际模型 ID 是否一致
