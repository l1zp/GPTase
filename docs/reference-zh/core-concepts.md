# 核心概念

> [首页](./README.md) → 核心概念

五分钟建立 GPTase 的完整心智模型。

---

## 思维模型

```
你的输入（文本、文档路径、图片）
          |
          v
      [ Agent ]
      单个 AI 工作单元，定义在 .claude/agents/*.md
      执行一项任务，返回 {"status", "data", "error"}
          |
          v
  [ Plan 编排器 ]
  从 config/plans/*.yaml 读取工作流定义
  通过 {{template}} 变量在步骤间传递数据
          |
    ┌─────┴──────┐
    v            v
[ 步骤 2a ]  [ 步骤 2b ]   ← 并行组
    └─────┬──────┘
          v
      [ 步骤 3 ]           ← 顺序步骤
          |
          v
      最终结果
```

---

## 五个核心概念

### 1. Agent

**是什么：** 单个 AI 工作单元。以 Markdown 文件形式存放在 `.claude/agents/your-agent.md`，包含 YAML 头部。

**如何运行：** 根据模型名称自动路由：

```
model_name.startswith("claude-")
    是 → claude_agent_sdk.query()         内置工具，SDK 管理循环
    否 → Model.generate() + ToolExecutor  OpenAI 兼容的工具调用
```

**输入 → 输出：**
```python
result = await agent.run("你的任务描述")
# {"status": "success", "data": {"content": "..."}}
```

**关键文件：** `gptase/agents/base.py` — `Agent` 类
**深入阅读：** [api/agent.md](./api/agent.md)

---

### 2. Plan（标准操作流程）

**是什么：** 将多个 Agent 串联起来的 YAML 工作流，存放在 `config/plans/*.yaml`。

**如何工作：**
- 步骤按顺序或并行组执行
- 使用 `{{step1}}`、`{{step2a.field}}` 模板变量在步骤间传递数据
- 失败步骤可重试、跳过或中止工作流
- 每次运行生成一个 session ID；中断的运行可以恢复

**关键文件：** `gptase/plan/orchestrator_agent.py` — `PlanOrchestratorAgent`
**深入阅读：** [api/plan.md](./api/plan.md)

---

### 3. Model

**是什么：** LLM 抽象层，封装任何 OpenAI 兼容的 Provider。

**负责处理：**
- 按 Agent 的模型配置（不同 Agent 可使用不同模型）
- Provider 实例缓存（复用 HTTP 连接）
- 可选的对话追踪（存入 SQLite）
- 流式响应

**关键文件：** `gptase/models/model.py` — `Model` 类
**深入阅读：** [api/model.md](./api/model.md)

---

### 4. FrameworkConfig

**是什么：** 所有配置的单一来源，加载一次，全局使用。

**加载优先级：**
1. `GPTASE_LLM_CONFIG` 环境变量
2. `config/llm_config.template.json`（默认）

**关键文件：** `gptase/utils/config.py` — `FrameworkConfig`
**深入阅读：** [api/config.md](./api/config.md)

---

### 5. Skill

**是什么：** 可复用的 prompt 片段，定义在 `.claude/skills/{name}/SKILL.md`。

**如何工作：**
- Agent 在 YAML 头部声明 `skills: skill1, skill2`
- 加载时 skill 内容自动追加到 system_prompt 末尾
- 用于封装常见工作流、领域知识或操作指南

**示例：**
```markdown
---
name: my-agent
skills: academic-pdf-reader, code_analysis
---
```

**关键文件：** `gptase/agents/base.py` — `Agent._load_skill_content()`
**深入阅读：** [api/agent.md#skills](./api/agent.md#skills)

---

## 目录地图

```
.claude/agents/          Agent 定义（*.md）      ← 在这里新增 Agent
.claude/skills/          Skill 定义（*/SKILL.md）← 在这里新增 Skill
config/plans/             Plan 工作流（*.yaml）    ← 在这里新增工作流
config/llm_config.*.json LLM 配置               ← 在这里设置 API Key

gptase/agents/           Agent 执行逻辑
gptase/plan/              Plan 系统
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
4. `Agent.run()` 路由到 Claude SDK 或 LLM 循环
5. 结果输出到 stdout

```bash
gptase plan -p enzyme_extraction_pipeline -i paper.md
```

1. `PlanRegistry` 加载 `config/plans/enzyme_extraction_pipeline.yaml`
2. `PlanOrchestratorAgent` 创建带 session ID 的 `ExecutionContext`
3. 每个工作流步骤通过 `TaskDispatcher` 调度到对应 `Agent`
4. 模板变量（`{{step1}}`）从已完成步骤的结果中解析
5. 每步完成后将 checkpoint 保存到 SQLite
6. 输出整理到 `analysis/`、`extraction/`、`vision/`、`summary/` 目录

---

*下一步：[常见任务 →](./common-tasks.md)*
