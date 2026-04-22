# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working with this repository.

## Project Overview

GPTase is a multi-agent framework for AI task automation with specialized capabilities for biochemical analysis. Supports multiple LLM providers, multimodal messages, and SQLite-based memory management.

## Documentation

| 文档 | 说明 |
|---|---|
| [docs/reference-zh/](docs/reference-zh/README.md) | **Chinese Reference Manual** (L1-L5 progressive disclosure, main docs) |
| [docs/reference/](docs/reference/README.md) | English Reference (mirror) |
| [docs/setup.md](docs/setup.md) | Environment setup and LLM configuration |
| [docs/features/enzyme_extraction.md](docs/features/enzyme_extraction.md) | Enzyme kinetics extraction pipeline |

## Quick Reference

| Command | Purpose |
|---------|---------|
| `conda activate llm` | Activate Python environment |
| `pip install -e .` | Install in development mode |
| `gptase list` | List available agents |
| `gptase chat` | Start Auto Orchestrator (Interactive mode) |
| `gptase agent -n <name> -d "task"` | Run a single agent |
| `gptase plan list` | List available Plans |
| `gptase plan run -p <id>` | Execute Plan workflow |
| `gptase plan sessions` | List all sessions |
| `gptase plan status ID` | View session progress |
| `gptase plan resume ID` | Resume a session |
| `gptase memory --agent <name>` | Inspect agent working memory |
| `gptase eval -a <agent>` | Evaluate agent |
| `gptase eval -a <agent> --live` | Evaluate with live LLM run |
| `gptase web` | Start Web UI |
| `gptase web --port 8080 --host 0.0.0.0` | Start Web UI with custom port/host |
| `pytest tests/ -v --cov=gptase` | Run tests with coverage |
| `isort gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/` | Format code |

## Environment

Conda environment: `llm`

Current repository default: use the `llm` environment directly. Do not switch to other conda environments unless the user explicitly asks.

```bash
conda activate llm
pip install -e .
```

## LLM Configuration

Copy and edit configuration file:

```bash
cp config/llm_config.template.json config/llm_config.json
```

Or use environment variable:

```bash
export GPTASE_LLM_CONFIG=/path/to/my_config.json
```

## Architecture

```
Input
  └─> dispatch             Routes to one of three modes
        ├─> Agent              Direct tool loop for a single agent
        ├─> Coordinator        Orchestrator loop with worker delegation + plan handoff
        └─> Plan Manager       Executes structured workflows (sequential or parallel)
```

Auto-routing: `claude-*` models -> Claude SDK; other models -> OpenAI-compatible LLM loop.

### Directory Structure

```
.claude/agents/          Agent definitions (directory layout)
  {name}/{name}.md       Agent definition file        <- Add agents here
config/plans/            Plan workflows (*.yaml)      <- Add workflows here
config/llm_config.*.json LLM configuration            <- Set API key here

gptase/
  agents/                Agent execution logic
                         - base.py: Agent class + from_markdown factory
                         - runtime.py: Interactive tool-calling runtime
                         - types.py: Task, AgentDefinition, AgentState
                         - runtime_types.py: SessionTrace, InteractiveMetadata
                         - execution_types.py: StepResult, PlanProgress
                         - planner.py: PlanManager (multi-agent coordination)
                         - plan_dispatcher.py: TaskDispatcher
                         - plan_failure_handler.py: AI-driven failure recovery
                         - plan_loader.py: PlanRegistry
  core/                  Core execution engine
                         - orchestrator.py: AgentOrchestrator (Main entry point)
  models/                LLM providers
                         - model.py: Model class (main entry)
                         - types.py: ModelConfig, ModelResponse, StreamChunk
                         - providers.py: BaseProvider
  memory/                SQLite persistence
                         - manager.py: MemoryManager
                         - storage.py: ConversationStorage
                         - models.py: AgentMessage
  tools/                 Tool system (for LLM loop)
                         - base.py: BaseTool
                         - executor.py: ToolExecutor (parallel execution)
                         - handlers.py: built-in tool handlers
  web/                   Web UI server
                         - server.py: FastAPI app, REST API endpoints
  utils/                 Config, constants, exceptions
  main.py                CLI entry point

ui/                      Web UI frontend (React + TypeScript)
  src/App.tsx            Main UI components
  build.sh               Build script
  dist/                  Production build output
```

## Code Style

- Import sorting: isort with Google profile
- Code formatting: yapf (88 char limit, 4 space indent)
- Type checking: mypy
- **NO EMOJI** in any files (use `[ERROR]`, `[OK]`, `[INFO]`, `[WARNING]` instead)

## After Adding New Features

After implementing any new feature or non-trivial change, always run these three skills in order:

1. `/simplify` — review changed code for reuse, quality, and efficiency; fix issues found
2. `/deadcode` — identify and remove any dead code introduced or exposed by the change
3. `/pytest-writer` — write or update tests covering the new functionality

## Skill Test Cases (After Real Invocation)

每次调用 `.claude/skills/` 下的 skill 并得到实际输出后，评估本次调用效果，
将值得固化的输入/输出对提炼成 test case，写入对应 skill 的 `golden.yaml`。

**触发时机**：skill 调用完成，且输出结果具有以下特征之一：
- 正确处理了一个边界情况（例如数据库无记录、非天然反应、设计酶等特殊情况）
- 纠正了一个容易误判的先验假设（例如 EC number 不存在、scaffold 身份出人意料）
- 首次覆盖某类新输入（新的 PDB ID、新的酶家族、新的反应类型）

**如何提炼**：
1. 用 `/agent-eval` 检查 skill 是否已有覆盖该输入类型的 golden case
2. 若无，将本次调用的输入描述和期望输出提炼成 `golden.yaml` 条目
3. 期望输出只描述**关键断言**（例如"无 EC number"、"结合位点包含 GLU17"），不照搬完整响应

**示例**（来自本次 `biochem_databases` 调用）：
```yaml
- id: pdb_no_ec_designed_enzyme
  input: "查询 7VUU 的 EC number"
  assertions:
    - no_ec_number: true
    - scaffold: calmodulin
    - reason_keyword: "非天然反应"
```

## Pre-Commit Requirements

1. Run tests: `pytest tests/ -v --cov=gptase` (or `pytest tests/test_agents/ -v` for quick check)
2. Format: `isort gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/`
3. Type check (optional): `mypy gptase/ --ignore-missing-imports`
4. **Check documentation**: If code changes affect user-facing behavior (CLI, API, config), update corresponding docs in `docs/`

Exception: Documentation-only changes can skip tests and the post-feature skills above.

## Commit Conventions

- **NEVER add co-author metadata** to commit messages (e.g., "Co-Authored-By: ...")
- Use simple, descriptive commit messages

## Adding a New Agent

Create `.claude/agents/my-agent/my-agent.md`:

```markdown
---
name: my-agent
description: One-line description of what this agent does
tools: Read, Grep, Glob, Bash
model: claude-sonnet-4-6
---

System prompt content starts here. Everything after --- is the system_prompt.

## Workflow
1. Read input data...
2. Extract...

## Output Format
Return JSON:
`{"field": "value"}`
```

| Header Field | Required | Description |
|---|---|---|
| `name` | Yes | Agent ID - must match directory and filename |
| `description` | Yes | Displayed in `gptase list` output |
| `tools` | No | Comma-separated tool names |
| `model` | No | Model override for this agent |
| `color` | No | Display color in Claude Code UI |

Verify: `gptase list` should show `my-agent`

## Adding a New Plan

Create `config/plans/my_pipeline.yaml`:

```yaml
plan_id: my_pipeline
name: "My Workflow"
version: "1.0"
default_retry_count: 0
max_parallel: 10

workflow:
  # Sequential step
  - step_id: "1"
    agent: document-structure-analyzer
    action: analyze
    inputs:
      text: "{{input_text}}"

  # Parallel group
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

  # Reference previous steps
  - step_id: "3"
    agent: my-summarizer
    inputs:
      result_a: "{{step2a}}"
      result_b: "{{step2b}}"
```

Template variables:
| Template | Resolves to |
|---|---|
| `{{input_text}}` | `input_data["text"]` |
| `{{document_path}}` | `context.document_path` |
| `{{stepN}}` | Full result data dict from step N |
| `{{stepN.field}}` | Nested field from step N result |

Verify: `gptase plan list` should show `my_pipeline`

## Key Entry Points

```python
# Initialize orchestrator
from gptase.core.orchestrator import AgentOrchestrator
from gptase.utils.config import FrameworkConfig

orchestrator = AgentOrchestrator(FrameworkConfig())

# Run Coordinator mode (Interactive mode)
result = await orchestrator.dispatch({
    "description": "Compare top 3 enzymes for nitrobenzisoxazole hydrolysis",
    "auto_execute": True,
})
print(result["data"]["content"])

# Run a specific Plan
result = await orchestrator.dispatch({
    "plan_id": "enzyme_extraction_pipeline",
    "workspace_dir": "data/output/paper1",
    "auto_execute": True,
})

# Run single agent directly
from gptase.agents.base import Agent
from gptase.models.model import Model

model = Model()
agent = Agent.from_markdown("enzyme-kinetics-extractor", model_manager=model)
result = await agent.run("Extract Km from paper text...")
```

## Specialized Features

| Feature | Location |
|---------|----------|
| Auto Orchestration | `gptase chat` / `AgentOrchestrator._execute_coordinator` |
| Deep Research | `deep-research` agent (multi-round citation-backed reports) |
| Enzyme Extraction | `enzyme_extraction_pipeline` Plan, `enzyme-kinetics-extractor` agent |
| Enzyme Summary | `enzyme-extraction-summary` agent |
| Enzyme Design | `enzyme_design_pipeline` Plan (Literature -> Planning -> Prediction -> Design) |
| Document Analysis | `document-structure-analyzer` agent |
| Vision Analysis | `vision-image-analyzer` agent (multimodal) |
| Pytest Generation | `.claude/skills/pytest-writer/SKILL.md` (Expert test writer) |
| Agent Eval Framework | `gptase/evals/`, golden data in `data/evals/` |
| PDF Extraction | `pdf-extractor` skill，后端 MinerU Cloud API；Token 见 `.env`（`MINERU_TOKEN`），获取地址：`https://mineru.net/apiManage/token`；加载方式见 `.claude/skills/pdf-extractor/references/cloud_api.md` |

### Pytest Writer Skill

Use the `pytest-writer` skill to generate high-quality, idiomatic tests.
- **Organization**: Tests follow `tests/test_<module>.py` structure.
- **Async**: `asyncio_mode = "auto"`. **DO NOT** use `@pytest.mark.asyncio`.
- **Structure**: All tests must be inside a `class Test...`.
- **Fixtures**: Use fixtures from `tests/conftest.py` (e.g., `framework_config`, `mock_model_config`).
- **Mocks**: Use `unittest.mock.AsyncMock` for coroutines.

### Enzyme Kinetics Extraction

```bash
# Run via Plan (recommended)
gptase plan run -p enzyme_extraction_pipeline -i data/paper.md -o output/

# Batch processing
for file in data/papers/*.md; do
    gptase plan run -p enzyme_extraction_pipeline -i "$file" -o output/
done
```

Output JSON structure:
```json
{
  "reactions": [
    {
      "enzyme_name": "Des27",
      "substrates": ["5-nitrobenzisoxazole"],
      "products": ["2-nitrophenol"],
      "conditions": {"temperature": "25 C", "pH": "7.3"},
      "kinetics": {"Km": null, "kcat": null, "kcat_over_KM": 130},
      "pdb_ids": []
    }
  ]
}
```

## Communication Patterns

- **Code Organization Scope**: Clarify upfront whether refactoring is generic framework or domain-specific
- **Dead Code Removal**: Grep references -> Check exports -> Identify tests -> Present findings -> Run tests

## Streaming Output

```python
from gptase.models.model import Model

model = Model()
async for chunk in model.generate_stream(messages):
    print(chunk.content, end="", flush=True)
    if chunk.reasoning_content:
        print(f"[Thinking] {chunk.reasoning_content}")
    if chunk.is_complete:
        break
```

## CI/CD Pipeline

GitHub Actions (`.github/workflows/ci.yml`): Format check -> Type checking -> Tests (pytest across Python 3.8-3.12)

## Per-Agent Model Configuration

In `config/llm_config.json`:

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

No code changes needed - `Model.get_config_for_agent()` handles resolution automatically.

## HTTP 413 Context Overflow (Non-Claude Path)

When using a non-Claude model (e.g., Doubao) with skills and tools enabled, the AI Ping API may return **HTTP 413 Request Entity Too Large**.

**Trigger conditions** (all three must be true):
1. Non-Claude model path (`_run_with_llm`, not `_run_with_sdk`)
2. Skill content appended to system prompt (increases base payload)
3. Tools enabled — model uses `Bash+curl` as fallback (WebSearch/WebFetch are not registered in the non-Claude tool loop), and raw HTML responses can reach 4MB+

**Key facts:**
- `max_tokens` controls **output length only**, NOT input context window. Hard limit: 131072 (131073 returns HTTP 422).
- Fix: set `provider.sort = "input_length"` in `extra_body.provider` to route to longer-context providers. Already implemented via `extra_body` passthrough in `gptase/models/providers.py`.
- The issue does NOT occur in the Claude SDK path (`_run_with_sdk`) because WebSearch/WebFetch are registered and return structured, size-bounded results.

**Workaround in agent definition**: Force Claude model via global `llm_config.json` (frontmatter `model:` field is silently ignored — `AgentDefinition` has no model field).

Full investigation: `.claude/skills/deep-research-workspace/gptase-context-413-repro.md`
