# GPTase Reference

> Multi-agent AI task automation framework.

## Quick Start

```bash
conda activate llm && pip install -e .

gptase list                                          # list available agents
gptase run -d "Extract enzyme kinetics from paper"   # run a task
gptase sop -p enzyme_extraction_pipeline -i paper.md # run a workflow
```

**Three things to know:**
- Agents live in `.claude/agents/*.md` — add one with no code
- Skills live in `.claude/skills/*/SKILL.md` — reusable prompt fragments
- SOPs live in `config/sops/*.yaml` — add a workflow with no code
- Config lives in `config/llm_config.template.json` — set your API key there

## Architecture

```
Input
  └─> Agent                    single AI worker, one task
        └─> SOP Orchestrator   coordinates multiple agents
              ├─> Step 1
              ├─> Step 2a ─┐   parallel
              ├─> Step 2b ─┘
              └─> Step 3
```

Agents auto-route: `claude-*` models → Claude SDK, everything else → OpenAI-compatible LLM loop.

## CLI

| Command | Description |
|---|---|
| `gptase list` | List all agents |
| `gptase run -d "..."` | Run a task |
| `gptase run -d "..." -a agent-name` | Run with specific agent |
| `gptase sop --list` | List all SOPs |
| `gptase sop -p PLAN -i file.md` | Execute SOP |
| `gptase sop -p PLAN -i file.md -o out/` | Execute with output dir |
| `gptase sop --resume SESSION_ID` | Resume failed session |
| `gptase sop --list-sessions` | List all sessions |
| `gptase sop --session-status ID` | Check session progress |
| `gptase sop --no-checkpoint` | Skip checkpointing |
| any + `--debug` | Enable DEBUG logging |

## Documentation Map

| File | Level | What you'll find |
|---|---|---|
| **You are here** | L1 | Quick start, CLI, navigation |
| [core-concepts.md](./core-concepts.md) | L2 | Mental model, 5 core concepts, routing |
| [common-tasks.md](./common-tasks.md) | L3 | Code recipes for everyday work |
| [api/agent.md](./api/agent.md) | L4 | Agent, AgentTask, Skills, image loading |
| [api/sop.md](./api/sop.md) | L4 | SOPOrchestratorAgent, SOPDefinition, templates |
| [api/model.md](./api/model.md) | L4 | Model, ModelConfig, streaming |
| [api/config.md](./api/config.md) | L4 | FrameworkConfig, env vars, JSON schema |
| [api/memory.md](./api/memory.md) | L4 | MemoryManager, SQLite tables |
| [internals/execution-flow.md](./internals/execution-flow.md) | L5 | Detailed execution traces |
| [internals/dispatcher.md](./internals/dispatcher.md) | L5 | TaskDispatcher internals |
| [internals/types.md](./internals/types.md) | L5 | All types, exceptions |

## Pre-commit Checklist

```bash
pytest tests/test_agents/ -v
isort gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/
mypy gptase/ --ignore-missing-imports   # optional
```
