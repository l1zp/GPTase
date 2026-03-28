# 核心概念

> [首页](./README.md) → 核心概念

五分钟建立 GPTase 的完整心智模型。

---

## 思维模型

```
你的输入（文本、文档路径、图片）
          |
          v
 [ Orchestrator Runtime ]
 面向目标的 harness 入口。
 持有 session、加载或生成 draft plan、
 调度 worker，并跟踪目标是否完成。
          |
    ┌─────┴──────┐
    v            v
[ Worker 2a ] [ Worker 2b ] ← 并行调度
    └─────┬──────┘
          v
      [ Worker 3 ]          ← 顺序调度
          |
          v
        最终结果
```

---

## 五个核心概念

### 1. Agent

**是什么：** 单个 AI 工作单元。以 Markdown 文件形式存放在 `.claude/agents/your-agent/your-agent.md`，包含 YAML 头部。

**边界：** Agent 只表示 worker，不表示 orchestrator。orchestrator 是 `gptase/core/` 里的 runtime 层。

**如何运行：** 根据模型名称自动路由：

```
model_name.startswith("claude-")
    是 → claude_agent_sdk.query()         内置工具、MCP server、SDK 管理循环
    否 → Model.generate() + ToolExecutor  OpenAI 兼容工具调用 + MCP 工具
```

**输入 → 输出：**
```python
result = await agent.run("你的任务描述")
# {"status": "success", "data": {"content": "..."}}
```

**关键文件：** `gptase/agents/base.py` — `Agent` 类
**深入阅读：** [api/agent.md](./api/agent.md)

---

### 2. Orchestrator Harness

**是什么：** `AgentOrchestrator` 是多步任务的主入口。它不是 Markdown 定义的 Agent，
而是一个 Python runtime：接收任务提交、持有 goal session、加载或生成 draft plan、
调度 worker，并决定目标是否完成、等待审批，还是继续补充 draft。

**如何工作：**
- 每次编排运行都会生成一个 session ID
- session 可以从 `config/plans/*.yaml` 中的预定义 draft plan 启动，也可以由系统生成 draft
- worker 步骤按顺序或并行组执行
- 使用 `{{step1}}`、`{{step2a.field}}` 模板变量在 worker 步骤间传递数据
- 目标评估决定是结束、等待审批、等待用户输入，还是继续补充 plan

**关键文件：** `gptase/core/orchestrator.py` — `AgentOrchestrator`
**深入阅读：** [api/plan.md](./api/plan.md)

---

### 3. PlanManager + TaskDispatcher

**是什么：** harness runtime 背后的内部执行引擎。

**边界：** 它们不是用户侧主入口。`PlanManager` 负责生成和执行单个 draft plan，`TaskDispatcher` 负责把 ready task 分发给具体 worker agent。

**如何工作：**
- `PlanManager.create_plan()` 根据自然语言目标生成 draft plan
- `PlanManager.execute_plan()` 执行 plan DAG
- `TaskDispatcher` 将每个 ready task 分发给指定 worker
- orchestrator runtime 再在这之上叠加 session、审批、replan 和目标评估

**关键文件：** `gptase/agents/planner.py`, `gptase/agents/plan_dispatcher.py`
**深入阅读：** [api/plan.md](./api/plan.md)

---

### 4. Model

**是什么：** LLM 抽象层，封装任何 OpenAI 兼容的 Provider。

**负责处理：**
- 按 Agent 的模型配置（不同 Agent 可使用不同模型）
- Provider 实例缓存（复用 HTTP 连接）
- 可选的对话追踪（存入 SQLite）
- 流式响应

**关键文件：** `gptase/models/model.py` — `Model` 类
**深入阅读：** [api/model.md](./api/model.md)

---

### 5. FrameworkConfig

**是什么：** 所有配置的单一来源，加载一次，全局使用。

**现在还负责承载：**
- `agent_models`：按 Agent 覆盖模型配置
- `provider`：上游 provider 路由/选项
- `mcp_servers`：MCP 工具服务器定义

**加载优先级：**
1. `GPTASE_LLM_CONFIG` 环境变量
2. `config/llm_config.template.json`（默认）

**关键文件：** `gptase/utils/config.py` — `FrameworkConfig`
**深入阅读：** [api/config.md](./api/config.md)

---

### 6. Skill

**是什么：** 可复用的 prompt 片段，定义在 `.claude/skills/{name}/SKILL.md`。

**如何工作：**
- Agent 在 YAML 头部声明 `skills: skill1, skill2`
- 加载时 skill 内容自动追加到 system_prompt 末尾
- 用于封装常见工作流、领域知识或操作指南

**示例：**
```markdown
---
name: my-agent
skills: pdf-extractor, code_analysis
---
```

**关键文件：** `gptase/agents/base.py` — `Agent._load_skill_content()`
**深入阅读：** [api/agent.md#skills](./api/agent.md#skills)

---

## 目录地图

```
.claude/agents/          Agent 定义（目录布局）
  {name}/{name}.md       Agent 定义文件           ← 在这里新增 Agent
.claude/skills/          Skill 定义（*/SKILL.md）← 在这里新增 Skill
config/plans/             Plan 工作流（*.yaml）    ← 在这里新增工作流
config/llm_config.*.json LLM 配置               ← 在这里设置 API Key

gptase/agents/           Agent 执行逻辑
gptase/core/             Orchestrator harness runtime
gptase/models/           LLM Provider
gptase/memory/           SQLite 持久化
gptase/tools/            工具系统（用于 LLM 循环）
gptase/utils/            配置、常量、异常
gptase/main.py           CLI 入口
```

---

## 运行一个任务时发生了什么

```bash
gptase agent -n enzyme-kinetics-extractor -d "从论文中提取动力学参数"
```

1. `FrameworkConfig` 从 `config/llm_config.template.json` 加载
2. 从匹配的 `.md` 文件创建 `Agent` 实例
3. `Agent.run()` 路由到 Claude SDK 或 LLM 循环
4. 结果输出到 stdout

```bash
gptase plan -p enzyme_extraction_pipeline -i paper.md
```

1. `PlanRegistry` 加载 `config/plans/enzyme_extraction_pipeline.yaml`
2. `AgentOrchestrator` 创建 goal session，并挂载 draft plan
3. `PlanManager` 在 harness runtime 内执行 draft plan
4. 每个工作流步骤通过 `TaskDispatcher` 调度到对应 worker `Agent`
5. 模板变量（`{{step1}}`）从已完成步骤的结果中解析
6. orchestrator 判断目标是否已达成，必要时继续补充 plan
7. session 状态持久化到 SQLite

```python
from gptase.core.orchestrator import AgentOrchestrator
from gptase.utils.config import FrameworkConfig

orchestrator = AgentOrchestrator(FrameworkConfig())
result = await orchestrator.execute_task({
    "description": "分析这篇论文并比较变体表现",
    "auto_execute": False,
})
```

当没有预先提供 plan 时：

```python
from gptase.core.orchestrator import AgentOrchestrator
from gptase.utils.config import FrameworkConfig

orchestrator = AgentOrchestrator(FrameworkConfig())

draft = await orchestrator.execute_task({
    "description": "分析这篇论文并比较变体表现",
    "auto_execute": False,
})

approved = await orchestrator.approve_plan(draft["session_id"])
```

1. `AgentOrchestrator` 接收自然语言目标并创建 goal session
2. `PlanManager.create_plan()` 根据目标动态生成一个 draft plan
3. draft plan 返回给用户审批，或在 `auto_execute=True` 时直接进入执行
4. `PlanManager.execute_plan()` 执行 draft plan
5. 每个 ready task 通过 `TaskDispatcher` 分发给对应 worker `Agent`
6. 模板变量（`{{step1}}`）从已完成步骤的结果中解析
7. orchestrator 判断目标是否已达成，必要时继续补充 draft
8. session 状态持久化到 SQLite

---

*下一步：[常见任务 →](./common-tasks.md)*
