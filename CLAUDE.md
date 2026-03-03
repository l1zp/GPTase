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
| `gptase sop --list` | List available SOPs |
| `gptase sop -p enzyme_extraction_pipeline -i input.md -o output/` | Execute SOP workflow |
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
  sop/            SOP execution system
                   - types.py: Pydantic models (SOPStep, SOPDefinition, etc.)
                   - loader.py: YAML/JSON SOP loading, SOPRegistry
                   - dispatcher.py: Task dispatch and result collection
                   - failure_handler.py: AI-driven failure recovery
                   - orchestrator_agent.py: Unified SOP orchestrator
  models/         LLM abstraction (Model, providers, types)
                   - Multimodal support: TextContent, ImageUrlContent
  memory/         SQLite-based storage (manager, storage, models, types)
  main.py         CLI entry point
  utils.py        Utility functions
config/
  agents/         Markdown-based agent definitions (*.md)
  sops/           Standard Operating Procedures (YAML/JSON workflows)
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

## Commit Conventions

- **NEVER add co-author metadata** to commit messages (e.g., "Co-Authored-By: ...")
- Use simple, descriptive commit messages

### Adding a New Agent

1. Create config in `config/agents/your_agent.md`
2. Include metadata markers: `@agent_id`, `@capabilities`, `@requires_model`, `@model_role`, `@temperature`, `@max_tokens`
3. Include sections: `## Agent Description`, `## System Prompt`, `## Task Processing`, `## Output Format`, `## Examples`
4. Use `MarkdownAgentFactory` to instantiate

### Adding a New SOP

1. Create `config/sops/my_pipeline.yaml` (or `.json`)
2. Define workflow with steps and parallel groups
3. Use `{{input_text}}`, `{{stepN}}`, `{{stepN.field}}` for data flow
4. Ensure referenced agents exist in `config/agents/`

Example:
```yaml
plan_id: my_pipeline
name: My Pipeline
version: "1.0"

workflow:
  - step_id: "1"
    agent: document_structure_analyzer
    action: analyze
    inputs:
      text: "{{input_text}}"

  - parallel:
      - step_id: "2a"
        agent: extractor_a
        inputs:
          data: "{{step1}}"
      - step_id: "2b"
        agent: extractor_b
        inputs:
          data: "{{step1}}"

  - step_id: "3"
    agent: summarizer
    inputs:
      result_a: "{{step2a}}"
      result_b: "{{step2b}}"
```

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

# Execute SOP workflow
from gptase.sop import SOPOrchestratorAgent
orchestrator = SOPOrchestratorAgent()
result = await orchestrator.execute_sop(
    plan_id="enzyme_extraction_pipeline",
    input_data={"text": "..."},
    document_path="/path/to/document",
)
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
