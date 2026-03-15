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
| `gptase agent -n <name> -d "task"` | Run a single agent |
| `gptase agent -n <name> -i input.md` | Run agent with input file |
| `gptase agent -n <name> --images img.png` | Run multimodal agent with images |
| `gptase sop --list` | List available SOPs |
| `gptase sop -p enzyme_extraction_pipeline -i input.md -o output/` | Execute SOP workflow |
| `gptase sop --resume SESSION_ID` | Resume failed session |
| `gptase sop --list-sessions` | List all sessions |
| `gptase sop --session-status ID` | View session progress |
| `gptase web` | Start Web UI |
| `gptase web --port 8080 --host 0.0.0.0` | Start Web UI with custom port/host |
| `pytest tests/ -v --cov=gptase` | Run tests with coverage |
| `isort gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/` | Format code |

## Environment

Conda environment: `llm`

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
  └─> Agent                    Single AI work unit, executes one task
        └─> SOP Orchestrator   Coordinates multiple Agents
              ├─> Step 1
              ├─> Step 2a ─┐   Parallel execution
              ├─> Step 2b ─┘
              └─> Step 3
```

Auto-routing: `claude-*` models -> Claude SDK; other models -> OpenAI-compatible LLM loop.

### Directory Structure

```
.claude/agents/          Agent definitions (*.md)     <- Add agents here
config/sops/             SOP workflows (*.yaml)       <- Add workflows here
config/llm_config.*.json LLM configuration            <- Set API key here

gptase/
  agents/                Agent execution logic
                         - base.py: Agent class + MarkdownAgentFactory (from_markdown)
                         - types.py: AgentTask, AgentDefinition, AgentState
  core/                  Core execution engine
                         - orchestrator.py: AgentOrchestrator (multi-agent coordination)
  sop/                   SOP system
                         - orchestrator_agent.py: SOPOrchestratorAgent
                         - types.py: SOPDefinition, SOPStep, StepResult
                         - loader.py: SOPRegistry
                         - dispatcher.py: TaskDispatcher
                         - failure_handler.py: AI-driven failure recovery
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

## Pre-Commit Requirements

1. Run tests: `pytest tests/ -v --cov=gptase` (or `pytest tests/test_agents/ -v` for quick check)
2. Format: `isort gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/`
3. Type check (optional): `mypy gptase/ --ignore-missing-imports`

Exception: Documentation-only changes can skip tests and the post-feature skills above.

## Commit Conventions

- **NEVER add co-author metadata** to commit messages (e.g., "Co-Authored-By: ...")
- Use simple, descriptive commit messages

## Adding a New Agent

Create `.claude/agents/my-agent.md`:

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
| `name` | Yes | Agent ID - must match filename (without extension) |
| `description` | Yes | Displayed in `gptase list` output |
| `tools` | No | Comma-separated tool names |
| `model` | No | Model override for this agent |
| `color` | No | Display color in Claude Code UI |

Verify: `gptase list` should show `my-agent`

## Adding a New SOP

Create `config/sops/my_pipeline.yaml`:

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

Verify: `gptase sop --list` should show `my_pipeline`

## Key Entry Points

```python
# Initialize model manager
from gptase.models.model import Model

model = Model()

# Create agent from .md definition
from gptase.agents.base import Agent

agent = Agent.from_markdown("enzyme-kinetics-extractor", model_manager=model)

# Run agent
result = await agent.run("Extract all Km and kcat values...")
print(result["status"])           # "success" or "error"
print(result["data"]["content"])  # Agent output

# Multimodal task (vision)
result = await agent.run(
    content="Extract data from these figures",
    image_paths=["figure1.png", "figure2.png"],
)

# Structured task input
from gptase.agents.types import AgentTask

task = AgentTask(
    description="Extract enzyme kinetics parameters",
    image_paths=["table.png"],
    document_text="Full paper text...",
    source="Nature 2024",
)
result = await agent.process_task(task)

# Execute SOP workflow
from gptase.sop import SOPOrchestratorAgent

orchestrator = SOPOrchestratorAgent()
try:
    result = await orchestrator.execute_sop(
        plan_id="enzyme_extraction_pipeline",
        input_data={"text": open("paper.md").read()},
        document_path="/path/to/paper_dir",
        workspace_dir="/path/to/workspace",
        auto_checkpoint=True,
    )
    print(result["step_results"]["1"])   # Step 1 output
finally:
    await orchestrator.close()  # Must close, otherwise SQLite connection errors

# Resume interrupted session
result = await orchestrator.resume_sop(session_id="sop_20240301_120000_abc12345")
```

## Specialized Features

| Feature | Location |
|---------|----------|
| Enzyme Reaction Extraction | `enzyme_extraction_pipeline` SOP, `enzyme-kinetics-extractor` agent |
| Document Structure Analysis | `document-structure-analyzer` agent |
| Vision Image Analysis | `vision-image-analyzer` agent (multimodal) |
| Pytest Generation | `.claude/skills/pytest-writer/SKILL.md` (Expert test writer) |

### Pytest Writer Skill

Use the `pytest-writer` skill to generate high-quality, idiomatic tests.
- **Organization**: Tests follow `tests/test_<module>.py` structure.
- **Async**: `asyncio_mode = "auto"`. **DO NOT** use `@pytest.mark.asyncio`.
- **Structure**: All tests must be inside a `class Test...`.
- **Fixtures**: Use fixtures from `tests/conftest.py` (e.g., `framework_config`, `mock_model_config`).
- **Mocks**: Use `unittest.mock.AsyncMock` for coroutines.

### Enzyme Kinetics Extraction

```bash
# Run via SOP (recommended)
gptase sop -p enzyme_extraction_pipeline -i data/paper.md -o output/

# Batch processing
for file in data/papers/*.md; do
    gptase sop -p enzyme_extraction_pipeline -i "$file" -o output/
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
