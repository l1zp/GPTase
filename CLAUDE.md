# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GPTase is a multi-agent framework for AI task automation with specialized capabilities for biochemical analysis. It provides a flexible architecture for building AI agent systems with support for multiple LLM providers, code execution engines, and memory management.

## Core Architecture

The framework follows a layered architecture:

1. **Core Layer** (`src/core/`): Configuration, exceptions, and base interfaces
2. **Agent Layer** (`src/agents/`): Base agent class and specialized agents (Planner, Executor, Tool Manager, Memory Manager, Enzyme Kinetics Extractor, Enzyme Design Parser)
3. **Model Layer** (`src/models/`): LLM abstraction supporting OpenAI, Anthropic, and custom endpoints
4. **Tool Layer** (`src/tools/`): Tool registry and implementations (document loader, code executor, file manager, web search, etc.)
5. **Executor Layer** (`src/executors/`): Python, Shell, Docker, and Sandbox execution engines
6. **Memory Layer** (`src/memory/`): Persistent storage and context management

All agents inherit from `BaseAgent` (src/agents/base.py) which provides message passing, state management, and health checks.

## Development Commands

### Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install in development mode (includes dev tools)
pip install -e .

# Install pre-commit hooks (runs on every commit)
pre-commit install
```

### Running the Application

```bash
# Start MCP server
./scripts/start_mcp.sh
```

### Testing

```bash
# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test categories
pytest tests/test_agents/ -v
pytest tests/test_models/ -v
pytest tests/test_executors/ -v

# Run a single test file
pytest tests/test_models/test_model.py -v

# Run a specific test
pytest tests/test_models/test_model.py::test_generate -v
```

### Code Quality

```bash
# Format imports (Google profile)
isort src/ tests/ examples/

# Format code (yapf with .style.yapf config)
yapf --in-place --parallel --recursive src/ tests/ examples/

# Type checking
mypy src/ --ignore-missing-imports

# Run pre-commit hooks manually
pre-commit run --all-files
```

## Configuration

### LLM Configuration

The framework reads LLM settings from `config/llm_config.template.json`. API key resolution priority:

1. Value in config file (if not a placeholder)
2. Environment variable `API_KEY`
3. Environment variable `OPENAI_API_KEY`
4. Environment variable `GPTASE_OPENAI_API_KEY`

Set your API key:
```bash
export API_KEY="your-api-key-here"
```

The config supports multiple providers:
- **OpenAI**: GPT-3.5, GPT-4, GPT-4 Turbo
- **Anthropic**: Claude 3 series (Sonnet, Opus, Haiku)
- **Custom**: Any API endpoint via `base_url` field

### Code Style Configuration

- **Import sorting**: isort with Google profile (`--profile=google`)
- **Code formatting**: yapf with custom style (`.style.yapf`: 88 char limit, 4 space indent)
- **Type checking**: mypy (ignores missing imports)
- **Pre-commit hooks**: Automatically runs isort, yapf, and basic checks on commit

## Key Entry Points

### Initializing the Model Manager

```python
from src.utils import default_manager

# Loads config from config/llm_config.template.json
# Resolves API key from environment variables
manager = default_manager()
```

### Creating an Agent

**Recommended: Markdown-based agents**

```python
from src.agents.markdown_factory import MarkdownAgentFactory

factory = MarkdownAgentFactory()
agent = factory.create_agent("enzyme_kinetics_extractor",
                             memory_manager,
                             tool_registry,
                             model_manager=manager)
```

**Legacy: Python class-based agents**

```python
from src.agents.specialized.llm_enzyme_extractor import LLMEnzymeExtractorAgent
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry
from src.tools.implementations import DocumentLoaderTool

tool_registry = ToolRegistry()
tool_registry.register_tools([DocumentLoaderTool()])
memory_manager = MemoryManager()

agent = LLMEnzymeExtractorAgent(
    "enzyme",
    memory_manager,
    tool_registry,
    model_manager=manager
)
```

### Using the Orchestrator

```python
from src.core.config import FrameworkConfig
from src.agents.orchestrator import AgentOrchestrator

config = FrameworkConfig()
orchestrator = AgentOrchestrator(config)
result = await orchestrator.execute_task(task)
```

## Specialized Features

### Enzyme Reaction Extraction

The framework provides specialized agents for extracting enzyme reaction data from scientific literature:

**Available Agents:**
- `enzyme_kinetics_extractor` - Extracts kinetic parameters (Km, kcat, Tm, etc.) from tables
- `enzyme_design_parser` - Extracts enzyme design workflows and methodology

**Phase 1: Document Structure Analysis** (`src/tools/document_structure_analyzer.py`)
- Identifies document sections and hierarchy
- Extracts tables (Markdown and HTML format)
- Locates key paragraphs containing kinetic keywords
- Saves analysis to `data/analysis/` directory

**Phase 2: Targeted LLM Extraction** (Markdown-based agents)
- `config/agents/enzyme_kinetics_extractor.md` - Kinetics data extraction
- `config/agents/enzyme_design_parser.md` - Design workflow extraction
- Processes only relevant content identified in Phase 1
- Extracts structured reaction data (enzymes, substrates, products, kinetics, conditions)
- Validates results against Pydantic schema
- Outputs to `data/extraction/` directory

**Legacy Python Agent:** (`src/agents/specialized/llm_enzyme_extractor.py`)
- Retained as backup reference
- Provides equivalent functionality to markdown-based agents

Run the extraction demo:
```bash
python examples/reaction_extractor_demo.py
```

### Tool System

Tools are registered in `src/tools/registry.py` and implement the `BaseTool` interface. Available tools:

- **DocumentLoaderTool**: Loads text/markdown files with token estimation
- **CodeExecutorTool**: Executes Python code
- **CodeWriterTool**: Writes code files
- **FileManagerTool**: File system operations
- **WebSearchTool**: Web content retrieval
- **CalculatorTool**: Mathematical calculations
- **PDBECLookupTool**: Protein database lookup

### Agent Communication

Agents communicate through `AgentMessage` objects with sender/recipient structure. Messages are passed through the memory system and support state synchronization across agents.

## Important Architecture Patterns

### Async-First Design

All I/O operations are async. Use `async def` for agent methods and `await` for calls:
```python
async def process_task(self, task: Dict) -> Dict:
    result = await self.tool_registry.execute("document_loader", **params)
    return result
```

Use `asyncio.gather()` for parallel execution:
```python
results = await asyncio.gather(*[agent.process_task(t) for t in tasks])
```

### Resource Management

Implement `shutdown()` method in agents for cleanup:
```python
async def shutdown(self):
    await self.model_manager.close()
    # Clean up resources
```

### Error Handling

Use custom exceptions from `src/core/exceptions.py`. Always provide meaningful error messages and log errors for debugging.

## Testing Strategy

- **Unit tests**: Individual component testing (models, tools, executors)
- **Integration tests**: Agent interaction testing
- **End-to-end tests**: Full workflow testing
- **Test configuration**: `tests/conftest.py` adds `src/` to Python path

Tests run on Python 3.8-3.12 via CI/CD. Coverage reports are generated on each test run.

## CI/CD Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and PR:

1. **Format check**: isort and yapf must pass
2. **Lint**: mypy type checking
3. **Test**: pytest across Python 3.8-3.12 with coverage reporting

## Working with the Codebase

### Adding a New Tool

1. Create tool class in `src/tools/implementations.py` inheriting from `BaseTool`
2. Implement `async execute(**kwargs) -> ToolResult`
3. Register in tool registry: `tool_registry.register_tools([MyNewTool()])`

### Adding a New Agent

1. Create agent in `src/agents/specialized/` inheriting from `BaseAgent`
2. Implement required abstract methods: `execute_task()`, `shutdown()`
3. Initialize with required dependencies (memory_manager, tool_registry, model_manager)

### Modifying LLM Prompts

**For enzyme kinetics extraction:**
Edit the system prompt in `config/agents/enzyme_kinetics_extractor.md`

**For enzyme design parsing:**
Edit the system prompt in `config/agents/enzyme_design_parser.md`

**Legacy (Python-based agents):**
For enzyme extraction, edit prompts in `src/agents/specialized/llm_enzyme_extractor.py`. The system prompt defines the extraction schema and rules.

### Extending Extraction Schema

Modify Pydantic models in `src/tools/markdown_enzyme_parser.py` to add new fields to extraction results. Update the system prompt accordingly.

## Common Patterns

### Reading Configuration

```python
from src.core.config import FrameworkConfig

config = FrameworkConfig()
model_config = config.get_model_config(ModelRole.GENERAL)
```

### Logging

Use Python's standard logging with Rich formatting:
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Processing document: %s", document_path)
```

### Type Hints

All functions should have type hints. Use Pydantic models for data structures:
```python
from typing import Optional, Dict, List
from pydantic import BaseModel

class MyData(BaseModel):
    field1: str
    field2: Optional[int] = None
```

## File Organization Notes

- **Configuration**: `config/llm_config.template.json` is the source of truth for LLM settings
- **Examples**: `examples/` contains runnable demos showing framework usage
- **Test data**: `data/` contains sample documents for testing
- **Scripts**: `scripts/` contains startup and utility scripts
- **Documentation**: `docs/` contains detailed workflow documentation

## Performance Considerations

- The framework is async-first for high concurrency
- Document structure analysis (Phase 1 of enzyme extraction) reduces token usage by 60-80%
- Use batch operations where possible (tool registry supports batch execution)
- Implement proper cleanup in `shutdown()` methods to prevent resource leaks
- Profile performance-critical paths before optimization

## Important Notes

- Never commit actual API keys to the repository
- Use placeholder values in config files and rely on environment variables
- All async methods must be properly awaited
- The enzyme extraction pipeline requires two phases: structure analysis before LLM extraction
- PDB IDs are 4-character codes starting with a digit (e.g., 1ABC)
- HTML tables are supported in addition to Markdown tables for enzyme extraction
- Agent configuration uses markdown-based system (`config/agents/*.md`)
  - `enzyme_kinetics_extractor` - Extracts kinetic data (formerly `enzyme_extractor`)
  - `enzyme_design_parser` - Parses design workflows (formerly `enzyme_design`)
  - Legacy Python classes remain in `src/agents/specialized/` as backup references
