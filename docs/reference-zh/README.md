# GPTase 参考手册

> 多智能体 AI 任务自动化框架。

## 快速开始

```bash
conda activate llm && pip install -e .

gptase list                                          # 查看所有可用 Agent
gptase agent -n <name> -d "从论文中提取酶动力学参数"               # 运行单个任务
gptase plan -p enzyme_extraction_pipeline -i paper.md # 运行工作流
gptase web                                           # 启动 Web UI
```

**三件事：**
- Agent 定义在 `.claude/agents/{name}/{name}.md` — 新增无需写代码
- Skill 定义在 `.claude/skills/*/SKILL.md` — 可复用的 prompt 片段
- Plan 定义在 `config/plans/*.yaml` — 新增工作流无需写代码
- 配置在 `config/llm_config.template.json` — 在这里设置 API Key

## 架构

```
输入
  └─> Orchestrator Runtime     harness 入口，持有 session 与 draft plan
        └─> Worker Agents       执行被分发任务的单个 AI 工作单元
              ├─> 任务 1
              ├─> 任务 2a ─┐   并行执行
              ├─> 任务 2b ─┘
              └─> 任务 3
```

Agent 自动路由：`claude-*` 模型 → Claude SDK；其他模型 → OpenAI 兼容 LLM 循环。

**关键边界：**
- `.claude/agents/*` 里只定义 worker agents
- `AgentOrchestrator` 是 `gptase/core/orchestrator.py` 里的 harness runtime，不是 markdown agent
- 多步编排统一从 runtime harness 进入，而不是从 worker prompt 进入

## CLI 命令

| 命令 | 说明 |
|---|---|
| `gptase list` | 列出所有 Agent |
| `gptase agent -n <name> -d "..."` | 运行单个 Agent |
| `gptase agent -n <name> -i file.md` | 使用输入文件运行 |
| `gptase agent -n <name> --images img.png` | 运行多模态 Agent |
| `gptase plan --list` | 列出所有 Plan |
| `gptase plan -p PLAN -i file.md` | 执行 Plan |
| `gptase plan -p PLAN -i file.md -o out/` | 指定输出目录 |
| `gptase plan --resume SESSION_ID` | 恢复失败的 Session |
| `gptase plan --list-sessions` | 列出所有 Session |
| `gptase plan --session-status ID` | 查看 Session 进度 |
| `gptase plan --no-checkpoint` | 禁用断点保存 |
| `gptase eval -a <agent>` | 评估 Agent（使用缓存） |
| `gptase eval -a <agent> --live` | 实时运行并评估 |
| `gptase web` | 启动 Web UI |
| `gptase web --port 8080 --host 0.0.0.0` | 自定义端口和主机 |
| 任何命令 + `--debug` | 启用 DEBUG 日志 |

## 执行模式 (Execution Modes)

Agent 支持两种执行模式：**直接执行模式**（默认）或 **规划模式**（Plan Mode）。

```python
from gptase.agents import AgentMode

# 直接执行（默认）
result = await agent.run("立刻分析这些数据")

# 规划模式（Agent 会先动态创建一个任务有向无环图 DAG，然后再执行）
manager_result = await agent.run(
    "分析这篇论文并将动力学常数提取到 CSV 中",
    mode=AgentMode.PLAN
)

# 你也可以手动访问 planner：
plan = await agent.planner.create_plan("复杂的任务目标")
print(f"创建了包含 {len(plan.tasks)} 个步骤的计划。")
result = await agent.planner.execute_plan(plan)
```

如果你要运行的是多步 harness 工作流，主入口不是单个 worker agent，而是 `AgentOrchestrator.execute_task()` 或 CLI 的 `gptase plan`。

## Web UI

GPTase 提供基于 Web 的可视化界面，支持 Agent 对话和 Plan 工作流管理。

```bash
cd ui && ./build.sh    # 首次构建
gptase web             # 启动服务（默认 http://127.0.0.1:8000）
```

→ 完整使用指南：[common-tasks.md#web-ui](./common-tasks.md#web-ui)
→ API 文档：[api/web.md](./api/web.md)

## 文档导航

| 文件 | 层次 | 内容 |
|---|---|---|
| **当前文件** | L1 | 快速开始、CLI、导航索引 |
| [core-concepts.md](./core-concepts.md) | L2 | 思维模型、5个核心概念、路由逻辑 |
| [common-tasks.md](./common-tasks.md) | L3 | 日常开发代码示例 |
| [api/agent.md](./api/agent.md) | L4 | Agent、AgentTask、Skills、图片加载 |
| [api/plan.md](./api/plan.md) | L4 | PlanManager、Plan、PlannedTask、模板变量 |
| [api/model.md](./api/model.md) | L4 | Model、ModelConfig、流式输出 |
| [api/config.md](./api/config.md) | L4 | FrameworkConfig、环境变量、JSON Schema |
| [api/memory.md](./api/memory.md) | L4 | MemoryManager、SQLite 表结构 |
| [api/web.md](./api/web.md) | L4 | Web UI API 端点、WebSocket |
| [api/eval.md](./api/eval.md) | L4 | Eval 框架、EvalRunner、golden.yaml、字段路径 DSL |
| [internals/execution-flow.md](./internals/execution-flow.md) | L5 | 详细执行流程 |
| [internals/dispatcher.md](./internals/dispatcher.md) | L5 | TaskDispatcher 内部实现 |
| [internals/types.md](./internals/types.md) | L5 | 所有类型、异常层次 |

## 自动化测试与质量

GPTase 强调通过自动化测试保证代码质量。

- **核心规范**：所有测试位于 `tests/` 目录。
- **异步测试**：已配置 `asyncio_mode = "auto"`，**禁止**在测试方法上使用 `@pytest.mark.asyncio`宣。
- **结构化测试**：测试必须封装在 `class Test...` 中。
- **智能编写**：内置 `pytest-writer` Skill，可自动根据源码生成符合项目规范的测试代码。

```bash
# 运行所有测试
pytest tests/ -v

# 检查特定模块覆盖率
pytest tests/test_models.py --cov=gptase.models --cov-report=term-missing
```

## 提交前检查清单

```bash
pytest tests/test_agents/ -v
isort gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/
mypy gptase/ --ignore-missing-imports   # 可选
```
