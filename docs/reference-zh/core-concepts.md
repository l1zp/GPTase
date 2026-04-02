# 核心概念

> [首页](./README.md) → 核心概念

五分钟建立 GPTase 的完整心智模型。

---

## 思维模型

```
你的输入（文本、文档路径、图片）
          |
          v
 [ Interactive Runtime ]
 单个 agent 的 direct LLM/tool 循环
 可直接回答，也可请求结构化后续执行
          |
          v
 [ Auto Orchestrator ]
 可能直接回答，也可能进入 coordinator loop 或执行 Plan
     |                    |
     v                    v
 [Coordinator Loop]   [Plan Execution]
 DelegateTask worker  Draft plan、执行、目标评估、replan
 回合 + 汇总
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

### 2. Interactive Runtime + Auto Orchestrator

**是什么：** 现在每个 non-Claude agent 都先经过 interactive runtime。Auto
orchestrator 也是先走 runtime，再决定直接结束、进入 coordinator loop，还是 handoff
到 plan 模式。

**如何工作：**
- 单个 agent 在 turn loop 里完成 tool calling 和 trace 收集
- `agent_id="auto"` 会先从 direct runtime 开始
- 如果发生 delegation，orchestrator 可以继续进入 coordinator loop
- 如果 runtime 返回 `needs_plan`，orchestrator 会创建 draft plan

**直接回答 vs. Plan 执行：**
- direct runtime 回答：直接返回结果
- coordinator loop 回答：直接返回结果
- plan handoff：创建 draft plan，可审核后执行或直接执行

**关键文件：** `gptase/core/orchestrator.py` — `AgentOrchestrator`
**深入阅读：** [api/plan.md](./api/plan.md)

---

### 3. Plan Execution

**是什么：** Plan Execution 是结构化执行层，用在显式 plan 请求或 runtime handoff 之后。
Plan 直接内联执行（不做 session 持久化），结果直接返回。

**如何工作：**
- Plan 可以来自 `plan_id`、`plan_path`、inline plan 数据，或 LLM 自动生成
- Plan 中的步骤按顺序或并行组执行
- 使用 `{{step1}}`、`{{step2a.field}}` 模板变量在步骤间传递数据
- 目标评估判断结果是否达标，支持自动 replan

**关键文件：** `gptase/core/orchestrator.py` — `AgentOrchestrator`
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
gptase/core/             Auto orchestrator + plan execution runtime
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
2. `AgentOrchestrator` 扫描 `.claude/agents/` 发现所有 Agent
3. 从匹配的 `.md` 文件创建 `Agent` 实例
4. `Agent.run()` 路由到 Claude SDK 或 interactive runtime
5. 结果输出到 stdout

```bash
gptase plan -p enzyme_extraction_pipeline -i paper.md
```

1. `PlanRegistry` 加载 `config/plans/enzyme_extraction_pipeline.yaml`
2. `AgentOrchestrator._execute_plan()` 解析或生成 Plan
3. 每个工作流步骤通过 `TaskDispatcher` 调度到对应 `Agent`
4. 模板变量（`{{step1}}`）从已完成步骤的结果中解析
5. 目标评估判断结果是否达标
6. 如果 `auto_replan=True` 且目标未达成，自动生成后续 Plan
7. 结果直接返回（不做 session 持久化）

---

*下一步：[常见任务 →](./common-tasks.md)*
