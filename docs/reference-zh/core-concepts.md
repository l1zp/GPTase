# 核心概念

> [首页](./README.md) → 核心概念

五分钟建立 GPTase 的完整心智模型。

---

## 思维模型

```
 你的输入（文本、文档路径、图片）
            │
            ▼
   [ AgentOrchestrator.dispatch ]   框架层只有两种模式
            │
   ┌────────┴────────┐
   ▼                 ▼
[Agent]         [Coordinator]
单 agent         LLM 驱动的编排循环，
直接执行         通过 DelegateTask 委派给
工具循环          worker agent，聚合结果
                    ▲
                    │（可选）
                    │
              `gptase chat -p <plan_id>`
              把 config/plans/<id>.md 渲染
              成结构化 to-do prompt，
              交给 Coordinator 顺序执行

 ──────────────────────────────────────────────
 外挂路径：per-pipeline Python driver
 例如 scripts/run_kinetics_extraction.py
 直接 spawn Agent.run() 子进程，
 完全绕过 Coordinator。当工作流
 per-item 颗粒太细，LLM 编排开销不
 划算时使用。
```

**Plan 不是第三种 dispatch 模式** —— 它只是 Coordinator 遵循的一种
prompt 模板。**Driver script** 是第四种调用方式，根本不走框架的
dispatch 入口。

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

### 2. Coordinator Mode

**是什么：** 默认执行模式（`gptase chat`）。Orchestrator agent 在循环中运行，
可以直接回答、通过 DelegateTask 委派 worker agent、或 handoff 给 Plan 执行。

**如何工作：**
- Orchestrator agent 在 turn loop 里完成 tool calling 和 trace 收集
- 如果 runtime 返回 `final_answer` → 直接返回结果（即使本 turn 有委派）
- 如果有委派但未 final_answer → 构建 followup prompt，继续循环（最多 `_MAX_COORDINATOR_TURNS` 轮）
- 没有任何 coordinator 活动 → 错误返回

**两种退出路径：**
- 直接回答：一轮即返回结果
- 协调循环：多轮委派后由 LLM 自己组装最终答案返回

**关键文件：** `gptase/core/orchestrator.py` — `AgentOrchestrator`
**深入阅读：** [internals/execution-flow.md](./internals/execution-flow.md)

---

### 3. Plan Templates

**是什么：** Plan 模板是 `config/plans/<plan_id>.md` 下的 Markdown 文件，
描述"按这个顺序、用这些 worker、做这件事"。它们 **不是** 执行计划 —
而是 Coordinator session 的 prompt 种子。

**如何工作：**
- 用户运行 `gptase chat -p <plan_id> -i <doc>` 启动 session
- `expand_plan_to_prompt` 把 YAML 渲染成结构化 to-do prompt
- Coordinator 按 prompt 描述的顺序自主调度 DelegateTask
- `replicas` / `parallel_with` 在同一条 assistant message 中并发
- 带有 sibling `hooks.py` 且 `pre_run` 返回结果 dict 的 worker 绕过 LLM 直接出结果

**关键文件：** `gptase/agents/plan_prompt.py` — `expand_plan_to_prompt`
**深入阅读：** [../../CLAUDE.md#adding-a-new-plan](../../CLAUDE.md)

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
config/plans/             Plan 工作流（<plan_id>.md）← 在这里新增工作流
config/llm_config.*.json LLM 配置               ← 在这里设置 API Key

gptase/agents/           Agent 执行逻辑
gptase/core/             Coordinator + Plan 执行 runtime
gptase/models/           LLM Provider
gptase/memory/           SQLite 持久化
gptase/tools/            工具系统（用于 LLM 循环）
gptase/utils/            配置、常量、异常
gptase/main.py           CLI 入口
```

---

## 运行一个任务时发生了什么

```bash
gptase agent -n enzyme-kinetics-table-extractor -d "从论文中提取动力学参数"
```

1. `FrameworkConfig` 从 `config/llm_config.template.json` 加载
2. `AgentOrchestrator` 扫描 `.claude/agents/` 发现所有 Agent
3. 从匹配的 `.md` 文件创建 `Agent` 实例
4. `Agent.run()` 路由到 Claude SDK 或 interactive runtime
5. 结果输出到 stdout

```bash
gptase chat -p my_pipeline -i paper.md
```

1. CLI 加载 `config/plans/my_pipeline.md`
2. `expand_plan_to_prompt` 把 YAML 渲染成结构化 to-do prompt
3. `AgentOrchestrator.dispatch` 进入 Coordinator 模式
4. Coordinator 按 prompt 顺序发出 `DelegateTask` 调用
5. 每个 worker 输出写入 `<workspace>/worker_results/NNN_*.json`
6. 下游 step 通过 `output_path` 引用上游产物（artifact-based comms）
7. Coordinator 在最后一步生成最终答案返回

---

## 专用流水线：酶动力学提取

部分工作流的 per-item 粒度太细，用 Coordinator + Plan 编排成本过
高。酶动力学提取（Step 1–4）改为**纯 Python driver**驱动：

```bash
python scripts/run_kinetics_extraction.py --enable-figures --enable-text
```

driver 复用现有 Agent 基础设施（每个 item 一次 `Agent.run()` 子进程
调用），但跳过 Coordinator 的 LLM 协调成本。完整管道一次跑 ~22 分钟，
244 次 LLM 调用产出 607 个规范化变体 + 61 条蛋白序列。

详细架构与产物 schema：[features/enzyme_extraction.md](../features/enzyme_extraction.md)

---

*下一步：[常见任务 →](./common-tasks.md)*
