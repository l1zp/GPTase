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
| `pytest tests/ -v --cov=src` | Run tests with coverage |
| `isort src/ tests/ examples/ && yapf --in-place --parallel --recursive src/ tests/ examples/` | Format code |

## Architecture

```
src/
  core/           Configuration, exceptions, base interfaces
  agents/         Unified Base agent + Markdown-driven agents
  models/         LLM abstraction (OpenAI, Anthropic, custom)
  tools/          General-purpose tool registry and implementations
  mcp/            MCP-specific enzyme tools and databases
  memory/         Persistent storage and context
  conversations/  SQLite-based tracking
  webui/          Streamlit interface
```

All agents use `BaseAgent` ([src/agents/base.py](src/agents/base.py)) or `MarkdownAgent` ([src/agents/markdown_agent.py](src/agents/markdown_agent.py)).

## Code Style

- Import sorting: isort with Google profile
- Code formatting: yapf (88 char limit, 4 space indent)
- Type checking: mypy
- **NO EMOJI** in any files (use `[ERROR]`, `[OK]`, `[INFO]`, `[WARNING]` instead)

## Pre-Commit Requirements

1. Run tests: `pytest tests/ -v --cov=src` (or `pytest tests/test_tools/ -v` for quick check)
2. Format: `isort src/ tests/ examples/ && yapf --in-place --parallel --recursive src/ tests/ examples/`
3. Type check (optional): `mypy src/ --ignore-missing-imports`

Exception: Documentation-only changes can skip tests.

## Tool Architecture

**Base Components** ([src/tools/base.py](src/tools/base.py)): `ToolResult`, `TrackingMixin`, `BaseTool`, `FunctionTool`, `@tool` decorator

**Tool Categories**:
- **General Tools** ([src/tools/](src/tools/)): Document, system, utility tools + framework core (executor, planner)
- **MCP Domain-Specific** ([src/mcp/tools/](src/mcp/tools/)): enzyme_kinetics, enzyme_design, vision, document_structure
- **MCP Databases** ([src/mcp/databases/](src/mcp/databases/)): PDB, Rhea, KEGG, Expasy, PubChem lookup

### Adding a New Tool

1. Create class in `src/tools/` inheriting from `BaseTool`
2. Implement `async execute(**kwargs) -> ToolResult` and `get_schema() -> dict`
3. Register in `src/agents/orchestrator.py`
4. Add tests in `tests/test_tools/test_{tool_name}.py`

### Adding a New Agent

1. Create config in `config/agents/your_agent.md`
2. Include metadata markers: `@agent_id`, `@capabilities`, `@requires_model`, `@model_role`, `@temperature`, `@max_tokens`
3. Include sections: `## Agent Description`, `## System Prompt`, `## Task Processing`, `## Output Format`, `## Examples`
4. Use `MarkdownAgentFactory` to instantiate

### Adding a New SOP

Create workflow in `config/sops/your_sop.json` with `{{stepN.path}}` for data flow between agents.

## Key Entry Points

```python
# Initialize model manager
from src.utils import default_manager
manager = default_manager()

# Create agent
from src.agents.markdown_factory import MarkdownAgentFactory
factory = MarkdownAgentFactory()
agent = factory.create_agent("enzyme_kinetics_extractor", memory_manager, tool_registry, model_manager=manager)

# Run SOP
from src.agents.orchestrator import AgentOrchestrator
orchestrator = AgentOrchestrator(config)
result = await orchestrator.execute_task({"plan_id": "enzyme_extraction_pipeline", "text": "..."})
```

## Specialized Features

| Feature | Location |
|---------|----------|
| Enzyme Reaction Extraction | `enzyme_extraction_pipeline` SOP, `enzyme_kinetics_extractor` agent |
| 5-Phase Planning System | [src/tools/planner_tool.py](src/tools/planner_tool.py) |
| External Database Tools | [src/mcp/databases/](src/mcp/databases/): PDB, Rhea, KEGG, Expasy, PubChem |

## Communication Patterns

- **Code Organization Scope**: Clarify upfront whether refactoring is generic framework or domain-specific
- **Dead Code Removal**: Grep references -> Check exports -> Identify tests -> Present findings -> Run tests

## MCP Integration

### Context7

**Always use Context7 MCP when library/API documentation, code generation, setup or configuration steps are needed** - do not wait for explicit request.

Usage pattern:
1. Resolve library ID: `mcp__context7__resolve-library-id` with library name
2. Query docs: `mcp__context7__query-docs` with library ID and query

## CI/CD Pipeline

GitHub Actions (`.github/workflows/ci.yml`): Format check -> Type checking -> Tests (pytest across Python 3.8-3.12)
