# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working with this repository.

## Project Overview

GPTase is a multi-agent framework for AI task automation with specialized capabilities for biochemical analysis. Supports multiple LLM providers, multimodal messages, and SQLite-based memory management.

## Quick Reference

| Command | Purpose |
|---------|---------|
| `conda activate llm` | Activate Python environment |
| `pip install -e .` | Install in development mode |
| `gptase list` | List available agents |
| `gptase run -d "task description"` | Run a task |
| `python examples/reaction_extractor.py` | Enzyme extraction (SOP mode) |
| `python examples/vision_image_analyzer.py` | Multimodal image analysis |
| `pytest tests/ -v --cov=gptase` | Run tests with coverage |
| `isort gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/` | Format code |

## Environment

Conda environment: `llm`

```bash
conda activate llm
```

## Architecture

```
gptase/
  core/           Configuration, exceptions, constants, logging, paths
  agents/         BaseAgent, MarkdownAgent, Agent, AgentOrchestrator
  models/         LLM abstraction (Model, providers, types)
                   - Multimodal support: TextContent, ImageUrlContent
  memory/         SQLite-based storage (manager, storage, models, types)
  main.py         CLI entry point
  utils.py        Utility functions
config/
  agents/         Markdown-based agent definitions (*.md)
  sops/           Standard Operating Procedures (JSON workflows)
  llm_config.*.json  Model configuration templates
```

### Agent System

All agents use `BaseAgent` ([gptase/agents/base.py](gptase/agents/base.py)) or `MarkdownAgent` ([gptase/agents/markdown_agent.py](gptase/agents/markdown_agent.py)).

The unified `Agent` class ([gptase/agents/agent.py](gptase/agents/agent.py)) provides:
- **Dual execution**: Claude SDK for Claude models, custom LLM loop for others
- **Multimodal support**: `run_with_images()` for vision tasks
- **Skill integration**: Load skills from markdown files

## Code Style

- Import sorting: isort with Google profile
- Code formatting: yapf (88 char limit, 4 space indent)
- Type checking: mypy
- **NO EMOJI** in any files (use `[ERROR]`, `[OK]`, `[INFO]`, `[WARNING]` instead)

## Pre-Commit Requirements

1. Run tests: `pytest tests/ -v --cov=gptase` (or `pytest tests/test_agents/ -v` for quick check)
2. Format: `isort gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/`
3. Type check (optional): `mypy gptase/ --ignore-missing-imports`

Exception: Documentation-only changes can skip tests.

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
from gptase.models.model import Model
model = Model()

# Create agent
from gptase.agents.markdown_agent import MarkdownAgentFactory
from gptase.memory.manager import MemoryManager
from gptase.core.config import FrameworkConfig

config = FrameworkConfig()
memory_manager = MemoryManager(config=config.memory)
factory = MarkdownAgentFactory()
agent = factory.create_agent("enzyme_kinetics_extractor", memory_manager, model_manager=model)

# Run via orchestrator
from gptase.agents.orchestrator import AgentOrchestrator
orchestrator = AgentOrchestrator(config)
result = await orchestrator.execute_task({"description": "..."})
```

### Multimodal Agent Usage

```python
from gptase.agents.agent import Agent
from gptase.models.model import Model

model = Model()
model_config = model.get_config_for_agent("vision_image_analyzer")

agent = Agent(
    system_prompt="You are a scientific figure analyst.",
    model_config=model_config,
)

# Analyze images
result = await agent.run_with_images(
    task="Extract tabular data from this figure",
    image_paths=["figure.png"],
)

# Or via MarkdownAgent (automatic image detection)
from gptase.agents.markdown_agent import MarkdownAgentFactory
factory = MarkdownAgentFactory()
agent = factory.create_agent("vision_image_analyzer", memory_manager, model_manager=model)

task = {
    "description": "Analyze this figure",
    "image_paths": ["figure.png"],  # Automatic multimodal handling
}
result = await agent.process_task(task)
```

## Specialized Features

| Feature | Location |
|---------|----------|
| Enzyme Reaction Extraction | `enzyme_extraction_pipeline` SOP, `enzyme_kinetics_extractor` agent |
| Document Structure Analysis | `document_structure_analyzer` agent |
| Vision Image Analysis | `vision_image_analyzer` agent (multimodal) |
| ReAct-style Analysis | `vision_image_analyzer_react` agent |

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
