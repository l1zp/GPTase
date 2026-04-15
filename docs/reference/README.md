# GPTase Reference

> Multi-agent AI task automation framework.

## Quick Start

```bash
conda activate llm && pip install -e .

gptase list                                          # list available agents
gptase chat                                          # Coordinator mode
gptase agent -n <name> -d "Extract enzyme kinetics"  # run a single agent
gptase plan run -p enzyme_extraction_pipeline         # run a workflow
gptase web                                           # start Web UI
```

**Three things to know:**
- Agents live in `.claude/agents/{name}/{name}.md` — add one with no code
- Skills live in `.claude/skills/*/SKILL.md` — reusable prompt fragments
- Plans live in `config/plans/*.yaml` — add a workflow with no code
- Config lives in `config/llm_config.template.json` — set your API key there

## Architecture

```
Input
  └─> dispatch routing      Three paths: Agent / Coordinator / Plan
        ├─> Agent              Direct tool loop for a single agent
        ├─> Coordinator        Orchestrator loop with delegation + plan handoff
        └─> Plan Manager       Executes structured plans (draft or auto-generated)
```

Agents auto-route: `claude-*` models → Claude SDK, everything else → OpenAI-compatible LLM loop.

Key boundaries:
- `.claude/agents/*` defines worker agents only
- `AgentOrchestrator` in `gptase/core/orchestrator.py` is the orchestrator runtime, not a markdown agent
- Multi-step orchestration enters through the orchestrator runtime, not through a worker prompt

## CLI

| Command | Description |
|---|---|
| `gptase list` | List all agents |
| `gptase chat` | Coordinator mode |
| `gptase agent -n <name> -d "..."` | Run a single agent |
| `gptase plan list` | List all plans |
| `gptase plan run -p PLAN` | Execute plan |
| `gptase plan sessions` | List all sessions |
| `gptase plan status ID` | Check session progress |
| `gptase plan resume ID` | Resume a session |
| `gptase eval -a <agent>` | Evaluate agent (cached output) |
| `gptase eval -a <agent> --live` | Run live and evaluate |
| `gptase web` | Start Web UI |
| `gptase web --port 8080 --host 0.0.0.0` | Custom port and host |
| any + `--debug` | Enable DEBUG logging |

## Web UI

GPTase provides a web-based visual interface for agent chat and plan workflow management.

```bash
cd ui && ./build.sh    # Build first time
gptase web             # Start server (default http://127.0.0.1:8000)
```

→ Full guide: [common-tasks.md#web-ui](./common-tasks.md#web-ui)
→ API docs: [api/web.md](./api/web.md)

## Documentation Map

| File | Level | What you'll find |
|---|---|---|
| **You are here** | L1 | Quick start, CLI, navigation |
| [core-concepts.md](./core-concepts.md) | L2 | Mental model, 5 core concepts, routing |
| [common-tasks.md](./common-tasks.md) | L3 | Code recipes for everyday work |
| [api/agent.md](./api/agent.md) | L4 | Agent, Task, Skills, image loading |
| [api/plan.md](./api/plan.md) | L4 | PlanManager, Plan, Task, templates |
| [api/model.md](./api/model.md) | L4 | Model, ModelConfig, streaming |
| [api/config.md](./api/config.md) | L4 | FrameworkConfig, env vars, JSON schema |
| [api/memory.md](./api/memory.md) | L4 | MemoryManager, SQLite tables |
| [api/web.md](./api/web.md) | L4 | Web UI API endpoints, WebSocket |
| [api/eval.md](./api/eval.md) | L4 | Eval framework, EvalRunner, golden.yaml, field path DSL |
| [internals/execution-flow.md](./internals/execution-flow.md) | L5 | Detailed execution traces |
| [internals/dispatcher.md](./internals/dispatcher.md) | L5 | TaskDispatcher internals |
| [internals/types.md](./internals/types.md) | L5 | All types, exceptions |
| [../development/memory-and-session-storage.md](../development/memory-and-session-storage.md) | Dev | Full storage walkthrough for conversations, direct sessions, checkpoints, and memory |

## Automated Testing & Quality

GPTase emphasizes code quality through automated testing.

- **Core Convention**: All tests are located in the `tests/` directory.
- **Async Testing**: Configured with `asyncio_mode = "auto"`. **DO NOT** use `@pytest.mark.asyncio` on test methods.
- **Structured Tests**: Tests must be inside `class Test...`.
- **Smart Generation**: Includes the `pytest-writer` Skill to automatically generate project-idiomatic tests from source code.

```bash
# Run all tests
pytest tests/ -v

# Check coverage for a specific module
pytest tests/test_models.py --cov=gptase.models --cov-report=term-missing
```

## Pre-commit Checklist

```bash
pytest tests/test_agents/ -v
isort gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/
mypy gptase/ --ignore-missing-imports   # optional
```
