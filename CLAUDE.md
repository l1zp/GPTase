# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working with this repository.

## Project Overview

GPTase is a multi-agent framework for AI task automation with specialized capabilities for biochemical analysis. Supports multiple LLM providers, code execution engines, and memory management.

## Quick Reference

| Command | Purpose |
|---------|---------|
| `pip install -e .` | Install in development mode |
| `streamlit run src/webui/app.py` | Start web UI |
| `python examples/reaction_extractor.py` | Enzyme extraction |
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
  agents/         Base agent + specialized agents
  models/         LLM abstraction (OpenAI, Anthropic, custom)
  tools/          Tool registry and implementations
  executors/      Python, Shell, Docker, Sandbox execution
  memory/         Persistent storage and context
  conversations/  SQLite-based tracking
  webui/          Streamlit interface
```

All agents inherit from `BaseAgent` (src/agents/base.py).

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

Supported providers: OpenAI (GPT-3.5/4), Anthropic (Claude 3), Custom endpoints.

**Thinking Mode:**
```json
{
  "model_name": "your-model",
  "api_key": "your-api-key",
  "enable_thinking": true,
  "provider_config": {
    "stream": true,
    "extra_body": {"enable_thinking": true}
  }
}
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

**NO CO-AUTHOR in commit messages** - Do not add "Co-Authored-By" trailers to commits.

## Key Entry Points

### Initialize Model Manager

```python
from src.utils import default_manager

manager = default_manager()
```

### Create Agent

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

### Use Orchestrator

```python
from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig

config = FrameworkConfig()
orchestrator = AgentOrchestrator(config)
result = await orchestrator.execute_task(task)
```

## Specialized Features

### Enzyme Reaction Extraction

| Agent | Purpose |
|-------|---------|
| `enzyme_kinetics_extractor` | Kinetic parameters (Km, kcat, Tm) |
| `EnzymeDesignExtractorAgent` | Enzyme design workflows |

```bash
python examples/reaction_extractor.py
python examples/reaction_extractor.py -i data/my_paper.md
python examples/design_workflow_extractor.py
```

Features: Two-phase architecture, session tracking, 60-80% token reduction.

Docs: [docs/features/enzyme_extraction.md](docs/features/enzyme_extraction.md)

### Conversation & Session Tracking

Automatic SQLite tracking of all LLM interactions. Four-level hierarchy:

```
Agent (enzyme_kinetics_extractor)
  Task (document processing)
    Job (individual LLM calls)
      LLM Call Details (prompts, thinking, response)
```

View in Web UI: `streamlit run src/webui/app.py` -> Agent Sessions

### Vision Image Analyzer

```bash
python examples/vision_image_analyzer.py           # Image 7
python examples/vision_image_analyzer.py --all     # All images
```

Docs: [docs/tools/vision_image_analyzer.md](docs/tools/vision_image_analyzer.md)

### Available Tools

| Tool | Purpose |
|------|---------|
| DocumentLoaderTool | Load files with token estimation |
| CodeExecutorTool | Execute Python code |
| CodeWriterTool | Write code files |
| FileManagerTool | File system operations |
| WebSearchTool | Web content retrieval |
| CalculatorTool | Mathematical calculations |
| PDBECLookupTool | Protein database lookup |
| PlanningTool | 5-phase planning workflow |
| ExecutorTool | Execute finalized plans |

## Architecture Patterns

### Async-First Design

All I/O operations are async:

```python
async def process_task(self, task: Dict) -> Dict:
    result = await self.tool_registry.execute("document_loader", **params)
    return result

# Parallel execution
results = await asyncio.gather(*[agent.process_task(t) for t in tasks])
```

### Resource Management

Implement `shutdown()` for cleanup:

```python
async def shutdown(self):
    await self.model_manager.close()
```

### Delegation Pattern

```
Agent (orchestrator) -> Tool (business logic) -> ModelManager (LLM operations)
```

- Agents: Thin orchestrators coordinating workflows
- Tools: Business logic, LLM calls, data processing
- Prompts: Centralized templates
- TrackingMixin: Automatic session tracking

Docs: [docs/architecture/delegation_pattern.md](docs/architecture/delegation_pattern.md)

## Working with the Codebase

### Adding a New Tool

1. Create class in `src/tools/implementations.py` inheriting from `BaseTool`
2. Implement `async execute(**kwargs) -> ToolResult`
3. Register: `tool_registry.register_tools([MyNewTool()])`
4. Add tests in `tests/test_tools/test_{tool_name}.py` (required)

### Adding a New Agent

**Markdown-based (recommended):**
1. Create config in `config/agents/your_agent.md`
2. Use `MarkdownAgentFactory` to instantiate

**Python class-based:**
1. Create in `src/agents/specialized/` inheriting from `BaseAgent`
2. Implement `execute_task()`, `shutdown()`
3. Add tests in `tests/test_agents/test_{agent_name}.py` (required)

### Adding Streaming Support

```python
async for chunk in model_manager.generate_stream(messages, role=ModelRole.GENERAL):
    if chunk.is_thinking:
        process_thinking(chunk.reasoning_content)
    if chunk.content:
        process_content(chunk.content)
    if chunk.is_complete:
        handle_complete(chunk.metadata)
```

### Modifying LLM Prompts

| Feature | Location |
|---------|----------|
| Enzyme kinetics | `src/tools/prompts.py` - `ENZYME_KINETICS_EXTRACTION_PROMPT` |
| Enzyme design | `src/tools/prompts.py` - `ENZYME_DESIGN_EXTRACTION_PROMPT` |
| Vision analysis | `src/tools/prompts.py` - `VISION_IMAGE_ANALYSIS_PROMPT_TEMPLATE` |
| Planning phases | `src/tools/prompts.py` - `PLANNING_PHASE_{1-5}_PROMPT` |

### Planning Workflow

The planner implements a 5-phase workflow for complex tasks:

```python
from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig

config = FrameworkConfig()
orchestrator = AgentOrchestrator(config)

# Start planning (Phase 1)
task = {
    "id": "my_task",
    "description": "Extract enzyme kinetics from data/papers/lipase.md",
    "use_planner": True,
    "phase": 1,
    "user_input": ""
}

result = await orchestrator.execute_task(task)
plan_id = result["plan_id"]

# Continue through phases 2-5 with user input
# Phase 2: Design approach
# Phase 3: Review and validate
# Phase 4: Generate final plan
# Phase 5: Approve for execution

# Execute approved plan
result = await orchestrator.execute_task({"plan_id": plan_id})
```

Docs: [docs/features/planner.md](docs/features/planner.md)

### Code Simplification Before Commits

1. Make code changes
2. Run code-simplifier agent to refactor
3. Review changes
4. Format code (isort + yapf)
5. Create commit

## Common Patterns

### Configuration

```python
from src.core.config import FrameworkConfig

config = FrameworkConfig()
model_config = config.get_model_config(ModelRole.GENERAL)
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Processing document: %s", document_path)
```

**NOTE**: For interactive demo scripts in `examples/` directory, `print` is
acceptable for user-facing output, but internal state should still use `logger`.

**NOTE**: For interactive demo scripts in `examples/` directory, `print` is
acceptable for user-facing output, but internal state should still use `logger`.

### Type Hints

```python
from typing import Optional

from pydantic import BaseModel


class MyData(BaseModel):
    field1: str
    field2: Optional[int] = None
```

## File Organization

| Directory | Contents |
|-----------|----------|
| `config/` | LLM config template, agent markdown configs |
| `examples/` | Runnable demos |
| `data/` | Test documents, SQLite DB, analysis outputs |
| `scripts/` | Startup and utility scripts |
| `docs/` | Detailed documentation |

## Important Notes

- Never commit API keys
- All async methods must be properly awaited
- Enzyme extraction requires two phases: structure analysis then LLM extraction
- PDB IDs are 4-character codes starting with a digit (e.g., 1ABC)
- HTML tables supported for enzyme extraction

## CI/CD Pipeline

GitHub Actions (`.github/workflows/ci.yml`):
1. Format check (isort, yapf)
2. Type checking (mypy)
3. Tests (pytest across Python 3.8-3.12)
