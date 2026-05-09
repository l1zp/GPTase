# GPTase 参考手册

> 多智能体 AI 任务自动化框架。

## 快速开始

```bash
conda activate llm && pip install -e .

gptase list                                          # 查看所有可用 Agent
gptase chat                                          # Coordinator 模式
gptase agent -n <name> -d "从论文中提取酶动力学参数"               # 运行单个任务
gptase chat -p enzyme_extraction_pipeline -i paper.md # 运行工作流（Coordinator 驱动）
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
  └─> dispatch 路由       两条路径：Agent / Coordinator
        ├─> Agent            单 agent 直接执行
        └─> Coordinator      Orchestrator 循环 + DelegateTask 委派 worker
                             （artifact-based 通信 + deterministic agent shortcut）
```

Agent 自动路由：`claude-*` 模型 → Claude SDK；其他模型 → OpenAI 兼容 LLM 循环。

**关键边界：**
- `.claude/agents/*` 里只定义 worker agents
- `AgentOrchestrator` 是 `gptase/core/orchestrator.py` 里的 orchestrator runtime，不是 markdown agent
- 多步编排统一从 orchestrator runtime 进入，而不是从 worker prompt 进入

## CLI 命令

| 命令 | 说明 |
|---|---|
| `gptase list` | 列出所有 Agent |
| `gptase chat` | Coordinator 模式（free-form）|
| `gptase chat -p <plan> -i <doc>` | 用 plan 模板初始化的 Coordinator 会话 |
| `gptase agent -n <name> -d "..."` | 运行单个 Agent |
| `gptase memory --agent NAME` | 查看 Agent 的工作记忆 (working memory) |
| `gptase eval -a <agent>` | 评估 Agent（使用缓存） |
| `gptase eval -a <agent> --live` | 实时运行并评估 |
| `gptase web` | 启动 Web UI |
| `gptase web --port 8080 --host 0.0.0.0` | 自定义端口和主机 |
| 任何命令 + `--debug` | 启用 DEBUG 日志 |

## Coordinator 模式

`gptase chat` 默认进入 Coordinator 模式。Orchestrator agent 在循环中运行，可以：

- 直接回答
- 通过 DelegateTask 委派 specialized worker，汇总结果后继续
- 配 `-p <plan_id>`：从 YAML plan 模板生成结构化 to-do 提示作为 session 起点

Plan 模板放在 `config/plans/*.yaml`（见 [api/agent.md](./api/agent.md)
关于 plan_prompt 的章节）。Coordinator 按 plan 列出的步骤顺序发出
DelegateTask；replicas/parallel_with 在同一条 assistant message 中并发。

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
| [api/agent.md](./api/agent.md) | L4 | Agent、Task、Skills、图片加载 |
| [api/model.md](./api/model.md) | L4 | Model、ModelConfig、流式输出 |
| [api/config.md](./api/config.md) | L4 | FrameworkConfig、环境变量、JSON Schema |
| [api/memory.md](./api/memory.md) | L4 | MemoryManager、SQLite 表结构 |
| [api/web.md](./api/web.md) | L4 | Web UI API 端点、WebSocket |
| [api/eval.md](./api/eval.md) | L4 | Eval 框架、EvalRunner、golden.yaml、字段路径 DSL |
| [internals/execution-flow.md](./internals/execution-flow.md) | L5 | 详细执行流程 |
| [internals/types.md](./internals/types.md) | L5 | 所有类型、异常层次 |

## 自动化测试与质量

GPTase 强调通过自动化测试保证代码质量。

- **目录布局**：`tests/` 镜像 `gptase/` 包结构——每个 `gptase/<pkg>/<module>.py` 对应 `tests/<pkg>/test_<module>.py`；跨模块 wiring 集中在 `tests/integration/`。
- **agent-co-located**：领域纯函数若位于 `.claude/agents/<agent>/`（如 `enzyme-variant-normalizer/normalizer.py`），其测试紧邻源码放在 `.claude/agents/<agent>/tests/`。`pyproject.toml::testpaths` 同时收集两个根目录。
- **异步测试**：已配置 `asyncio_mode = "auto"`，**禁止**在测试方法上使用 `@pytest.mark.asyncio`。
- **结构化测试**：测试必须封装在 `class Test...` 中。

```bash
# 运行完整测试套件（无参 pytest 走 pyproject testpaths）
pytest -v

# 检查特定模块覆盖率
pytest tests/models/test_model.py --cov=gptase.models --cov-report=term-missing

# 单层 / 单文件
pytest tests/core/ -v
pytest tests/evals/test_assertions.py -v
```

## 提交前检查清单

```bash
pytest -v                                                                      # 全量
isort gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/
mypy gptase/ --ignore-missing-imports   # 可选
```
