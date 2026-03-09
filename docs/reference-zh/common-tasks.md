# 常见任务

> [首页](./README.md) → 常见任务

日常开发代码示例。每个任务都链接到对应的 API 页面以获取完整详情。

---

## 运行 Agent

### 从代码运行单个 Agent

```python
import asyncio
from gptase.agents.base import Agent
from gptase.models.model import Model

async def main():
    model = Model()
    agent = Agent.from_markdown("enzyme-kinetics-extractor", model_manager=model)

    result = await agent.run("从以下文本中提取所有 Km 和 kcat 值：...")
    print(result["status"])           # "success" 或 "error"
    print(result["data"]["content"])  # Agent 输出内容

asyncio.run(main())
```

→ 完整 API：[api/agent.md](./api/agent.md)

### 运行多模态（视觉）任务

```python
result = await agent.run(
    content="从这些图表中提取数值数据",
    image_paths=["figure1.png", "figure2.png"],
)
```

图片会被 base64 编码后与文本一起发送。支持格式：`.png`、`.jpg`、`.gif`、`.webp`。

→ 图片加载详情：[api/agent.md#图片加载](./api/agent.md#图片加载)

### 以结构化数据传入任务

```python
from gptase.agents.types import AgentTask

task = AgentTask(
    description="提取酶动力学参数",
    image_paths=["table.png"],
    document_text="论文全文...",   # 任意额外字段都会注入 prompt
    source="Nature 2024",          # 任意额外字段都会注入 prompt
)
result = await agent.process_task(task)
```

→ AgentTask 详情：[api/agent.md#agenttask](./api/agent.md#agenttask)

---

## 运行 SOP 工作流

### 从代码执行 SOP

```python
import asyncio
from gptase.sop import SOPOrchestratorAgent

async def main():
    orchestrator = SOPOrchestratorAgent()
    try:
        result = await orchestrator.execute_sop(
            plan_id="enzyme_extraction_pipeline",
            input_data={"text": open("paper.md").read()},
            document_path="/path/to/paper_dir",
            workspace_dir="/path/to/workspace",
            auto_checkpoint=True,
        )
        print(result["step_results"]["1"])   # 步骤 1 输出
        print(result["step_results"]["2a"])  # 步骤 2a 输出
    finally:
        await orchestrator.close()  # 必须关闭，否则 SQLite 连接报错

asyncio.run(main())
```

→ 完整 API：[api/sop.md](./api/sop.md)

### 恢复中断的 Session

```bash
gptase sop --list-sessions
gptase sop --resume sop_20240301_120000_abc12345
```

```python
orchestrator = SOPOrchestratorAgent()
result = await orchestrator.resume_sop(session_id="sop_20240301_120000_abc12345")
await orchestrator.close()
```

→ Checkpoint 机制：[internals/execution-flow.md](./internals/execution-flow.md)

---

## 配置

### 为特定 Agent 指定不同的模型

在 `config/llm_config.template.json` 中：

```json
{
  "model_name": "gpt-4",
  "api_key": "sk-...",
  "agent_models": {
    "vision-image-analyzer": {
      "model_name": "gpt-4o",
      "max_tokens": 4000
    },
    "enzyme-kinetics-extractor": {
      "model_name": "gpt-4-turbo",
      "temperature": 0.0
    }
  }
}
```

不需要修改代码，`Model.get_config_for_agent()` 会自动解析。

→ 完整配置参考：[api/config.md](./api/config.md)

### 指定自定义配置文件

```bash
export GPTASE_LLM_CONFIG=/path/to/my_config.json
gptase sop -p enzyme_extraction_pipeline -i paper.md
```

### 启用 Thinking / 推理模式

在配置中：
```json
{ "thinking": { "type": "enabled" } }
```

或按 Agent 单独配置：
```json
{
  "agent_models": {
    "my-agent": { "thinking": { "type": "enabled" } }
  }
}
```

---

## 新增组件

### 新增 Agent（无需写代码）

创建 `.claude/agents/my-agent.md`：

```markdown
---
name: my-agent
description: 描述这个 Agent 的用途和适用场景
tools: Read, Grep, Glob
model: claude-sonnet-4-6
---

你是一个专门用于...的 Agent。

## 工作流程

1. 读取输入数据...
2. 提取...

## 输出格式

返回 JSON：
```json
{"field": "value"}
```
```

验证：
```bash
gptase list   # 应该出现 my-agent
```

→ 完整格式说明：[api/agent.md#markdown-格式](./api/agent.md#markdown-格式)

### 新增 SOP 工作流（无需写代码）

创建 `config/sops/my_pipeline.yaml`：

```yaml
plan_id: my_pipeline
name: "我的工作流"
version: "1.0"

workflow:
  - step_id: "1"
    agent: document-structure-analyzer
    inputs:
      text: "{{input_text}}"

  - parallel:
      - step_id: "2a"
        agent: my-extractor-a
        inputs:
          text: "{{input_text}}"
          structure: "{{step1}}"
      - step_id: "2b"
        agent: my-extractor-b
        inputs:
          images: "{{step1.images}}"

  - step_id: "3"
    agent: my-summarizer
    inputs:
      results_a: "{{step2a}}"
      results_b: "{{step2b}}"
```

验证：
```bash
gptase sop --list   # 应该出现 my_pipeline
```

→ 完整 YAML Schema：[api/sop.md#yaml-schema](./api/sop.md#yaml-schema)

---

## LLM 与流式输出

### 启用流式响应

```python
from gptase.models.model import Model

model = Model()
async for chunk in model.generate_stream(messages):
    print(chunk.content, end="", flush=True)
    if chunk.reasoning_content:
        print(f"[思考] {chunk.reasoning_content}")
```

→ 完整流式 API：[api/model.md#流式输出](./api/model.md#流式输出)

### 启用对话追踪

```python
model = Model(enable_tracking=True, tracking_db_path="data/conversations.db")
await model.initialize_tracking()
response = await model.generate(messages, agent_name="my-agent")
await model.shutdown()
```

→ 内存系统：[api/memory.md](./api/memory.md)

### 带重试的生成

```python
response = await model.generate_with_retry(messages, max_retries=3)
```

使用指数退避：每次重试等待 `2^attempt` 秒。

---

## 调试

### 启用 DEBUG 日志

```bash
gptase sop -p my_pipeline -i paper.md --debug
```

### 查看 Session 状态

```bash
gptase sop --session-status sop_20240301_120000_abc12345
```

### 禁用 Checkpoint（测试用）

```bash
gptase sop -p my_pipeline -i paper.md --no-checkpoint
```

### 健康检查

```python
model = Model()
status = await model.health_check()
print(status)
```

---

*下一层详情：[api/ →](./api/agent.md)*
