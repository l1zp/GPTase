# Thinking Mode (思考模式) 使用指南

## 概述

Thinking mode（思考模式）允许 LLM 在生成最终答案之前展示其推理过程。这个功能特别适用于：

- 复杂的问题分析和推理
- 需要展示思维链的任务
- 调试和理解模型的思考过程
- 教育和演示场景

## 支持的模型

目前支持 reasoning_content 的模型包括：

### OpenAI 系列
- **o1-preview**
- **o1-mini**
- 其他支持 reasoning 的模型

### 国产模型
- **Qwen/QwQ 系列**（如 Qwen3-235B-A22B）
- 其他支持 `enable_thinking` 参数的模型

> **注意**：不是所有模型都支持 thinking 模式。如果不支持，模型会直接返回答案，不会显示思考过程。

## 启用方式

### 方法 1: 在代码中启用

```python
from src.models.types import ModelConfig
from src.utils import default_manager

manager = default_manager()

# 创建启用 thinking 的配置
thinking_config = ModelConfig(enable_thinking=True)

# 使用该配置调用
messages = [
    {"role": "user", "content": "解释量子计算的原理"}
]

async for chunk in manager.generate_stream(
    messages,
    role=ModelRole.GENERAL,
    config=thinking_config
):
    if chunk.is_thinking:
        print(f"🧠 Thinking: {chunk.reasoning_content}")
    elif chunk.content:
        print(f"💡 Answer: {chunk.content}")
```

### 方法 2: 在配置文件中启用

编辑 `config/llm_config.template.json`:

```json
{
  "model_name": "Qwen3-235B-A22B",
  "api_key": "your-api-key",
  "temperature": 0.7,
  "max_tokens": 2000,
  "timeout": 120,
  "base_url": "https://your-api-endpoint.com",
  "enable_thinking": true,
  "provider_config": {
    "stream": true
  }
}
```

### 方法 3: 使用命令行工具

```bash
# 流式模式（默认启用 thinking）
python examples/chat_demo.py

# 禁用 thinking 模式
python examples/chat_demo.py --no-thinking

# 简单模式（非流式）
python examples/chat_demo.py --simple
```

## 输出格式

### 启用 Thinking 模式

```
============================================================
🤖 GPTase Streaming Chat Demo
============================================================

📝 Question: Explain quantum computing

⚙️  Thinking mode: enabled ✅

============================================================
💭 Streaming Response
============================================================

🧠 Thinking:
Let me think about quantum computing step by step...
Quantum computing uses quantum bits (qubits)...
Unlike classical bits, qubits can exist in superposition...
This allows quantum computers to process multiple possibilities...

💡 Answer:
Quantum computing is a revolutionary computing paradigm...
[Final answer here]

📊 Tokens: 1250 (prompt: 50, completion: 1200)

============================================================
✨ Demo Complete
============================================================
```

### 未启用或不支持 Thinking 模式

```
============================================================
💭 Streaming Response
============================================================

[直接显示答案，无思考过程]

📊 Tokens: 500 (prompt: 50, completion: 450)
```

## 技术细节

### API 调用

启用 thinking 模式时，API 调用会添加 `extra_body` 参数：

```python
completion = client.chat.completions.create(
    model="Qwen3-235B-A22B",
    messages=messages,
    stream=True,
    extra_body={"enable_thinking": True}  # 关键参数
)
```

### 响应结构

流式响应包含两种类型的内容：

1. **reasoning_content**: 推理/思考过程（黄色显示）
2. **content**: 最终答案（白色显示）

状态转换：
```
[开始] → [Thinking 阶段] → [Answer 阶段] → [完成]
         (reasoning_     (content
          content)       字段)
```

## 配置选项

### ModelConfig 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enable_thinking` | bool | False | 是否启用思考模式 |
| `stream` | bool | False | 是否使用流式输出（在 provider_config 中） |

### 注意事项

1. **兼容性**: 只有支持 `reasoning_content` 字段的模型才会返回思考过程
2. **性能**: Thinking 模式可能会增加响应时间和 token 消耗
3. **调试**: 使用 `--no-thinking` 可以快速禁用 thinking 进行对比测试

## 示例代码

### 完整示例

```python
import asyncio
from src.utils import default_manager
from src.models.types import ModelRole, ModelConfig

async def main():
    manager = default_manager()

    # 启用 thinking 模式
    config = ModelConfig(enable_thinking=True)

    messages = [{
        "role": "user",
        "content": "为什么天空是蓝色的？请逐步思考。"
    }]

    thinking_buffer = []
    answer_buffer = []
    is_thinking = False

    print("🧠 Thinking: ", end="", flush=True)

    async for chunk in manager.generate_stream(
        messages,
        role=ModelRole.GENERAL,
        config=config
    ):
        if chunk.is_thinking and chunk.reasoning_content:
            if not is_thinking:
                print("\n🧠 Thinking: ", end="", flush=True)
                is_thinking = True
            print(chunk.reasoning_content, end="", flush=True)
            thinking_buffer.append(chunk.reasoning_content)

        elif chunk.content:
            if is_thinking:
                print("\n\n💡 Answer: ", end="", flush=True)
                is_thinking = False
            print(chunk.content, end="", flush=True)
            answer_buffer.append(chunk.content)

        elif chunk.is_complete and "usage" in chunk.metadata:
            print(f"\n\n📊 {chunk.metadata['usage']}")

    print("\n\n✨ Done!")
    print(f"Thinking: {len(''.join(thinking_buffer))} chars")
    print(f"Answer: {len(''.join(answer_buffer))} chars")

if __name__ == "__main__":
    asyncio.run(main())
```

## 故障排除

### 问题: 没有看到思考过程

**可能原因**:
1. 模型不支持 `reasoning_content`
2. API 端点不支持 `extra_body` 参数
3. `enable_thinking` 未设置为 `True`

**解决方案**:
```python
# 检查模型是否支持
config = ModelConfig(enable_thinking=True)
# 或在配置文件中设置: "enable_thinking": true
```

### 问题: 报错 "extra_body not supported"

**解决方案**: 某些 API 提供商不支持 `extra_body`，可以尝试：
1. 更新 API 库版本
2. 使用提供商特定的 SDK
3. 联系 API 提供商确认支持

## 相关链接

- [OpenAI o1 系列文档](https://platform.openai.com/docs/guides/reasoning)
- [Qwen API 文档](https://help.aliyun.com/zh/dashscope/developer-reference/qwen-api)
- [流式输出文档](./STREAMING.md)

## 更新日志

- **2025-01-19**: 初始版本，支持 Qwen 和 OpenAI o1 系列的 thinking 模式
