# GPTase Reference

> Multi-agent AI task automation framework.

## Quick Start

```bash
conda activate llm && pip install -e .

gptase list                                          # list available agents
gptase agent -n <name> -d "Extract enzyme kinetics from paper"   # run a task
gptase plan -p enzyme_extraction_pipeline -i paper.md # run a workflow
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
  └─> Interactive Runtime      direct agent loop with tools
        └─> Auto Orchestrator  may answer directly, coordinate workers, or hand off to a plan
              └─> Plan Manager executes structured draft plans when a harness session exists
```

Agents auto-route: `claude-*` models → Claude SDK, everything else → OpenAI-compatible LLM loop.

## CLI

| Command | Description |
|---|---|
| `gptase list` | List all agents |
| `gptase agent -n <name> -d "..."` | Run a single agent |
| `gptase agent -n <name> -i file.md` | Run agent with input file |
| `gptase agent -n <name> --images img.png` | Run multimodal agent |
| `gptase plan --list` | List all plans |
| `gptase plan -p PLAN -i file.md` | Execute plan |
| `gptase plan -p PLAN -i file.md -o out/` | Execute with output dir |
| `gptase plan --resume SESSION_ID` | Resume failed session |
| `gptase plan --list-sessions` | List all sessions |
| `gptase plan --session-status ID` | Check session progress |
| `gptase plan --no-checkpoint` | Skip checkpointing |
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
| [api/agent.md](./api/agent.md) | L4 | Agent, AgentTask, Skills, image loading |
| [api/plan.md](./api/plan.md) | L4 | PlanManager, Plan, PlannedTask, templates |
| [api/model.md](./api/model.md) | L4 | Model, ModelConfig, streaming |
| [api/config.md](./api/config.md) | L4 | FrameworkConfig, env vars, JSON schema |
| [api/memory.md](./api/memory.md) | L4 | MemoryManager, SQLite tables |
| [api/web.md](./api/web.md) | L4 | Web UI API endpoints, WebSocket |
| [api/eval.md](./api/eval.md) | L4 | Eval framework, EvalRunner, golden.yaml, field path DSL |
| [internals/execution-flow.md](./internals/execution-flow.md) | L5 | Detailed execution traces |
| [internals/dispatcher.md](./internals/dispatcher.md) | L5 | TaskDispatcher internals |
| [internals/types.md](./internals/types.md) | L5 | All types, exceptions |

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
