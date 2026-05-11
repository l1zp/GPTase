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
| `gptase chat` | Start Coordinator (free-form mode) |
| `gptase chat -p <plan_id> -i <doc>` | Run a plan via Coordinator (LLM-driven) |
| `gptase agent -n <name> -d "task"` | Run a single agent |
| `gptase memory --agent <name>` | Inspect agent working memory |
| `gptase eval -a <agent>` | Evaluate agent |
| `gptase eval -a <agent> --live` | Evaluate with live LLM run |
| `gptase web` | Start Web UI |
| `gptase web --port 8080 --host 0.0.0.0` | Start Web UI with custom port/host |
| `pytest -v --cov=gptase` | Run full test suite (uses `testpaths` from pyproject — covers `tests/` + agent-co-located tests) |
| `pytest tests/<pkg>/test_<module>.py -v` | Run a single module's tests (mirrors `gptase/<pkg>/<module>.py` layout) |
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
  └─> dispatch             Routes to one of two modes
        ├─> Agent              Direct tool loop for a single agent
        └─> Coordinator        LLM-driven orchestrator loop with DelegateTask
                               (artifact-based worker comms + sibling hooks.py
                               LLM-bypass for pure-Python worker agents)
```

Auto-routing: `claude-*` models -> Claude SDK; other models -> OpenAI-compatible LLM loop.

### Directory Structure

```
.claude/agents/          Agent definitions (directory layout)
  {name}/{name}.md       Agent definition file        <- Add agents here
  {name}/tools.py        Optional agent-local tools (auto-discovered)
config/plans/            Plan templates (*.yaml)      <- Used by `chat -p`
config/llm_config.*.json LLM configuration            <- Set API key here

gptase/
  agents/                Agent execution logic
                         - base.py: Agent class + from_markdown factory
                         - runtime.py: Interactive tool-calling runtime
                         - runtime_types.py: SessionTrace, coordinator summary
                         - types.py: Task, AgentDefinition, AgentState, sessions
                         - plan_prompt.py: YAML plan -> Coordinator prompt
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

After implementing any new feature or non-trivial change, run `/simplify` to review the changed code for reuse, quality, and efficiency, and fix any issues it surfaces.

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

1. Run tests: `pytest -v --cov=gptase` (full suite via `testpaths`; or `pytest tests/<pkg>/test_<module>.py -v` for a single-file quick check)
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

## Adding hooks to an agent

An agent can ship a sibling `hooks.py` next to its `.md` to inject
behavior around the LLM call without touching the framework. The file
is auto-discovered by `Agent.from_markdown` (mirrors the `tools.py`
convention) and may export either or both of:

- `pre_run(ctx: HookContext) -> Optional[dict]` — runs **after** memory
  injection / multimodal assembly, **before** the SDK/LLM dispatch.
  Mutate `ctx.prompt` or `ctx.image_paths` in place to influence what
  the LLM sees. Return a `dict` to short-circuit the run entirely (the
  dict becomes the final result and the LLM is never invoked); return
  `None` to continue the normal flow.

- `post_run(ctx: HookContext) -> Optional[dict]` — runs after dispatch
  (or after a short-circuited `pre_run`). Inspect or replace
  `ctx.result`. `ctx.short_circuited` distinguishes the two paths.

Hooks may be sync or async; `Agent.run` detects coroutines and awaits.
Hook exceptions propagate (fail-fast). See
`gptase/agents/hooks.py` for the `HookContext` dataclass and
`.claude/agents/enzyme-variant-normalizer/hooks.py` for a working
LLM-bypass example.

## Adding a New Plan

Create `config/plans/my_pipeline.yaml`. Plans are expanded by
`gptase.agents.plan_prompt.expand_plan_to_prompt` into a structured
to-do list that the Coordinator reads at session start; each step
becomes one or more `DelegateTask` calls.

```yaml
plan_id: my_pipeline
name: "My Workflow"
version: "1.0"

steps:
  - id: "1"
    agent: document-structure-analyzer
    description: Scan the document for tables and figures.
    inputs:
      document_path: "{{document_path}}"

  - id: "2a"
    agent: my-extractor-a
    description: Extract structured data from text.
    replicas: 3                      # 3 parallel DelegateTask calls
    parallel_with: ["2b"]            # also runs concurrently with 2b
    inputs:
      document_path: "{{document_path}}"
      structure: "{{step1.sections}}"

  - id: "2b"
    agent: my-extractor-b
    description: Analyze figures.
    replicas: 3
    parallel_with: ["2a"]
    inputs:
      images: "{{step1.images}}"

  - id: "3"
    agent: my-summarizer
    description: Combine results from both extractors.
    inputs:
      result_a: "{{step2a}}"
      result_b: "{{step2b}}"
```

Step fields:
| Field | Required | Description |
|---|---|---|
| `id` | Yes | Step identifier; surface in prompt + referenced by `{{stepN}}` |
| `agent` | Yes | Agent ID (dash form, matches `.claude/agents/<name>/`) |
| `description` | No | Human-readable purpose; fed into `task_description` |
| `inputs` | No | Map of arguments; string values undergo `{{var}}` substitution |
| `replicas` | No | Run N parallel DelegateTask calls in one assistant message (default 1) |
| `parallel_with` | No | List of sibling step IDs that run concurrently |
| `optional` | No | Allow Coordinator to SKIP if `skip_if` evaluates true |
| `skip_if` | No | Free-form skip condition rendered into the prompt |

Template variables:
| Template | Resolves to |
|---|---|
| `{{document_path}}` | CLI `-i` argument |
| `{{si_document_path}}` | Auto-detected supplementary doc (sibling `_si.md` or SI subdir) |
| `{{workspace_dir}}` | CLI `-o` argument |
| `{{stepN}}` / `{{stepN.field}}` | Left as-is in prompt — Coordinator pastes the upstream `output_path` from the prior `DelegateTask` result |

Agents may ship a sibling `hooks.py` next to their `.md` to bypass the
LLM hop. A `pre_run` hook that returns a result dict short-circuits the
run — see `gptase/agents/hooks.py` for the `HookContext` contract, and
`.claude/agents/enzyme-variant-normalizer/hooks.py` for a working
LLM-bypass example. Hooks may also be used to mutate the prompt before
LLM dispatch (return `None`) or to post-process the result via
`post_run`.

Verify: `gptase chat -p my_pipeline -i <doc>` should accept the plan and start delegating.

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
| Document Analysis | `document-structure-analyzer` agent |
| Vision Analysis | `vision-image-analyzer` agent (multimodal) |
| Agent Eval Framework | `gptase/evals/`, golden data in `data/evals/` |
| PDF Extraction | `pdf-extractor` skill，后端 MinerU Cloud API；Token 见 `.env`（`MINERU_TOKEN`），获取地址：`https://mineru.net/apiManage/token`；加载方式见 `.claude/skills/pdf-extractor/references/cloud_api.md` |

### Pytest Conventions

When writing or updating tests, follow these project rules:
- **Layout**: `tests/` mirrors the `gptase/` package tree — every source file `gptase/<pkg>/<module>.py` has a matching `tests/<pkg>/test_<module>.py`. Cross-module wiring lives in `tests/integration/`.
- **Agent-co-located tests**: domain-pure code that lives under `.claude/agents/<agent>/` (e.g. `enzyme-variant-normalizer/normalizer.py`) ships its tests next to the agent at `.claude/agents/<agent>/tests/`. `pyproject.toml`'s `testpaths` collects both roots when you run `pytest` with no args.
- **Async**: `asyncio_mode = "auto"`. **DO NOT** use `@pytest.mark.asyncio`.
- **Structure**: All tests must be inside a `class Test...`.
- **Fixtures**: Use fixtures from `tests/conftest.py` (`framework_config`, `sample_image_png`, `sample_image_jpeg`). Per-package fixtures should live in `tests/<pkg>/conftest.py` if they are reused across multiple test files in that package.
- **Mocks**: Use `unittest.mock.AsyncMock` for coroutines. Module-level singletons (e.g. `gptase.web.server.orchestrator`) are swapped via `monkeypatch.setattr("module.path.name", mock)`.
- **Heavy `__init__`**: `AgentOrchestrator.__init__` scans `.claude/agents/`, builds a `Model`, and opens sqlite. For pure-helper tests, build instances via `AgentOrchestrator.__new__(AgentOrchestrator)` + manual attribute injection to skip that cost; for dispatch/coordinator state-machine tests, use a real instance under `tmp_path`-isolated sqlite.

### Enzyme Kinetics Extraction

```bash
# Coordinator-driven (LLM orchestrates the plan via DelegateTask)
gptase chat -p enzyme_extraction_pipeline -i data/paper.md -o output/

# Batch processing
for file in data/papers/*.md; do
    gptase chat -p enzyme_extraction_pipeline -i "$file" -o output/
done

# Force a specific SI document (auto-detection looks for sibling *_si.md
# and SI subdirectories like SI_*/main.md, MOESM*/main.md):
gptase chat -p enzyme_extraction_pipeline -i paper.md --si paper/SI/main.md -o out/
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

GitHub Actions (`.github/workflows/ci.yml`): Format check -> Type checking -> Tests (pytest across Python 3.10/3.11/3.12)

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
