# GPTase 参考手册

> 多智能体 AI 任务自动化框架。

## 快速开始

```bash
conda activate llm && pip install -e .

gptase list                                          # 查看所有可用 Agent
gptase run -d "从论文中提取酶动力学参数"               # 运行单个任务
gptase sop -p enzyme_extraction_pipeline -i paper.md # 运行工作流
```

**三件事：**
- Agent 定义在 `.claude/agents/*.md` — 新增无需写代码
- Skill 定义在 `.claude/skills/*/SKILL.md` — 可复用的 prompt 片段
- SOP 定义在 `config/sops/*.yaml` — 新增工作流无需写代码
- 配置在 `config/llm_config.template.json` — 在这里设置 API Key

## 架构

```
输入
  └─> Agent                    单个 AI 工作单元，执行一项任务
        └─> SOP 编排器          协调多个 Agent
              ├─> 步骤 1
              ├─> 步骤 2a ─┐   并行执行
              ├─> 步骤 2b ─┘
              └─> 步骤 3
```

Agent 自动路由：`claude-*` 模型 → Claude SDK；其他模型 → OpenAI 兼容 LLM 循环。

## CLI 命令

| 命令 | 说明 |
|---|---|
| `gptase list` | 列出所有 Agent |
| `gptase run -d "..."` | 运行任务 |
| `gptase run -d "..." -a agent-name` | 指定 Agent 运行 |
| `gptase sop --list` | 列出所有 SOP |
| `gptase sop -p PLAN -i file.md` | 执行 SOP |
| `gptase sop -p PLAN -i file.md -o out/` | 指定输出目录 |
| `gptase sop --resume SESSION_ID` | 恢复失败的 Session |
| `gptase sop --list-sessions` | 列出所有 Session |
| `gptase sop --session-status ID` | 查看 Session 进度 |
| `gptase sop --no-checkpoint` | 禁用断点保存 |
| 任何命令 + `--debug` | 启用 DEBUG 日志 |

## 文档导航

| 文件 | 层次 | 内容 |
|---|---|---|
| **当前文件** | L1 | 快速开始、CLI、导航索引 |
| [core-concepts.md](./core-concepts.md) | L2 | 思维模型、5个核心概念、路由逻辑 |
| [common-tasks.md](./common-tasks.md) | L3 | 日常开发代码示例 |
| [api/agent.md](./api/agent.md) | L4 | Agent、AgentTask、Skills、图片加载 |
| [api/sop.md](./api/sop.md) | L4 | SOPOrchestratorAgent、SOPDefinition、模板变量 |
| [api/model.md](./api/model.md) | L4 | Model、ModelConfig、流式输出 |
| [api/config.md](./api/config.md) | L4 | FrameworkConfig、环境变量、JSON Schema |
| [api/memory.md](./api/memory.md) | L4 | MemoryManager、SQLite 表结构 |
| [internals/execution-flow.md](./internals/execution-flow.md) | L5 | 详细执行流程 |
| [internals/dispatcher.md](./internals/dispatcher.md) | L5 | TaskDispatcher 内部实现 |
| [internals/types.md](./internals/types.md) | L5 | 所有类型、异常层次 |

## 提交前检查清单

```bash
pytest tests/test_agents/ -v
isort gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/
mypy gptase/ --ignore-missing-imports   # 可选
```
