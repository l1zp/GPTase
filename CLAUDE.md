# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working with this repository.

## Project Overview

GPTase is a multi-agent framework for AI task automation with specialized capabilities for biochemical analysis. Supports multiple LLM providers, code execution engines, and memory management.

## Quick Reference

| Command | Purpose |
|---------|---------|
| `pip install -e .` | Install in development mode |
| `streamlit run src/webui/app.py` | Start web UI |
| `python examples/reaction_extractor.py` | Enzyme extraction (SOP mode) |
| `python examples/chat_demo.py` | Streaming chat demo |
| `python examples/planner_demo.py` | Interactive planning demo |
| `pytest tests/ -v --cov=src` | Run tests with coverage |
| `isort src/ tests/ examples/` | Format imports |
| `yapf --in-place --parallel --recursive src/ tests/ examples/` | Format code |
| `mypy src/ --ignore-missing-imports` | Type checking |

## Architecture

```
src/
  core/           Configuration, exceptions, base interfaces
  agents/         Unified Base agent + Markdown-driven agents
  models/         LLM abstraction (OpenAI, Anthropic, custom)
  tools/          Tool registry and implementations (Structure, Extraction, Refinement)
  executors/      Python, Shell, Docker, Sandbox execution
  memory/         Persistent storage and context
  conversations/  SQLite-based tracking
  webui/          Streamlit interface
```

All agents use `BaseAgent` (src/agents/base.py) or `MarkdownAgent`.

## Configuration

### LLM Configuration

Config file: `config/llm_config.template.json`

API key resolution priority:
1. Value in config file (if not placeholder)
2. `API_KEY` environment variable
3. `OPENAI_API_KEY` environment variable
4. `GPTASE_OPENAI_API_KEY` environment variable

```bash
export API_KEY="your-api-key-here"
```

### Model Role Types

| Role | Purpose |
|------|---------|
| `GENERAL` | General purpose tasks |
| `EXTRACTION` | Data extraction |
| `ANALYSIS` | Document analysis |
| `SPECIALIZED` | Domain-specific tasks |
| `PLANNING` | Planning and orchestration |
| `CODE_EXECUTION` | Code generation/execution |

### Code Style

- Import sorting: isort with Google profile
- Code formatting: yapf (88 char limit, 4 space indent)
- Type checking: mypy
- Pre-commit hooks: runs isort, yapf automatically

**NO EMOJI** in any files (use `[ERROR]`, `[OK]`, `[INFO]`, `[WARNING]` instead).

## Pre-Commit Requirements

Before committing code changes:

1. Run tests: `pytest tests/ -v --cov=src` (or `pytest tests/test_tools/ -v` for quick check)
2. Format imports: `isort src/ tests/ examples/`
3. Format code: `yapf --in-place --parallel --recursive src/ tests/ examples/`
4. Type check (optional): `mypy src/ --ignore-missing-imports`

Exception: Documentation-only changes can skip tests.

## Key Entry Points

### Initialize Model Manager

```python
from src.utils import default_manager

manager = default_manager()
```

### Create Agent (Markdown-native)

```python
from src.agents.markdown_factory import MarkdownAgentFactory

factory = MarkdownAgentFactory()
agent = factory.create_agent(
    "enzyme_kinetics_extractor",
    memory_manager,
    tool_registry,
    model_manager=manager
)
```

### Run SOP (Predefined Workflow)

```python
from src.agents.orchestrator import AgentOrchestrator
orchestrator = AgentOrchestrator(config)
result = await orchestrator.execute_task({
    "plan_id": "enzyme_extraction_pipeline_sop",
    "text": "..."
})
```

## Specialized Features

### Enzyme Reaction Extraction

| Component | Purpose |
|-------|---------|
| `enzyme_extraction_pipeline_sop` | SOP for standard extraction workflow |
| `enzyme_kinetics_extractor` | Agent for kinetic parameters (Km, kcat, Tm) |

```bash
python examples/reaction_extractor.py
python examples/reaction_extractor.py -i data/my_paper.md
```

Features: AI-native SOP, data-driven flow, token-efficient pre-processing tools.

## Architecture Patterns

### Async-First Design

All I/O operations are async:

```python
async def process_task(self, task: Dict) -> Dict:
    result = await self.tool_registry.execute("document_loader", **params)
    return result
```

### Resource Management

Implement `shutdown()` for cleanup:

```python
async def shutdown(self):
    await self.model_manager.close()
```

### Delegation Pattern

```
SOP/Plan (Logic) -> Executor (Engine) -> MarkdownAgent (Persona) -> Tool (Worker)
```

- Agents: Markdown personas with tool capabilities.
- Tools: Business logic, heavy parsing, data processing.
- SOPs: Predefined standard pipelines.
- Executor: Variable-aware runtime.

## Working with the Codebase

### Adding a New Tool

1. Create class in `src/tools/` inheriting from `BaseTool`.
2. Implement `async execute(**kwargs) -> ToolResult`.
3. Register in `src/agents/orchestrator.py`.
4. Add tests in `tests/test_tools/test_{tool_name}.py` (required).

### Adding a New Agent

**Markdown-based (recommended):**
1. Create config in `config/agents/your_agent.md`.
2. Reference necessary tools via `@tools`.
3. Use `MarkdownAgentFactory` to instantiate.

### Adding a New SOP

1. Create workflow in `config/sops/your_sop.json`.
2. Use `{{stepN.path}}` for data flow between agents.

## Agent Markdown Specification (`config/agents/*.md`)

GPTase uses a unified Markdown-based system to define agents. Follow these standards for consistent parsing and optimal performance.

### Metadata Markers (HTML Comments)
Include a marker block at the very top of the file to define core agent attributes.
- `@agent_id`: Unique identifier (must match filename).
- `@capabilities`: Comma-separated list of skills.
- `@requires_model`: `true` or `false`.
- `@model_role`: `general`, `extraction`, `analysis`, `planning`.
- `@temperature`: Float (0.0 - 1.0).
- `@max_tokens`: Integer limit for responses.

### Mandatory Sections (## Headers)
The parser (`MarkdownParser`) expects the following headers to build the system prompt:
1. `## Agent Description`: High-level persona and objective.
2. `## System Prompt`: Detailed instructions and rules for the LLM.
3. `## Task Processing`: Sequential steps for handling tasks.
4. `## Output Format`: Definition of expected result structure (e.g., JSON schema).
5. `## Examples`: Few-shot task/response pairs for guidance.

### Best Practices
- **Conciseness**: Keep instructions sharp. Use `[RULES]` or `[STRATEGY]` tags instead of emojis.
- **Expert Delegation**: When writing for the `planner`, focus on "who" (agent) handles "what" (task).
- **Format Consistency**: Always specify structured output (JSON preferred) in the `Output Format`.
- **Progressive Disclosure**: Guide the agent to find deep rules in `CLAUDE.md` or `docs/` rather than over-documenting within the prompt.

## CI/CD Pipeline

GitHub Actions (`.github/workflows/ci.yml`):
1. Format check (isort, yapf)
2. Type checking (mypy)
3. Tests (pytest across Python 3.8-3.12)
