# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GPTase is a multi-agent framework for AI task automation with specialized capabilities for biochemical analysis. It provides a flexible architecture for building AI agent systems with support for multiple LLM providers, code execution engines, and memory management.

## Quick Start

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
# Start Streamlit web UI for conversation viewing
streamlit run src/webui/app.py

# Run enzyme reaction extraction with session tracking
python examples/reaction_extractor.py

# Run streaming chat demo with thinking mode
python examples/chat_demo.py              # Streaming with thinking mode (default)
python examples/chat_demo.py --no-thinking # Streaming without thinking
python examples/chat_demo.py --simple      # Simple mode (non-streaming)

# Analyze scientific figures with vision model
python examples/vision_image_analyzer.py
```

### Testing Commands

```bash
# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test categories
pytest tests/test_agents/ -v
pytest tests/test_models/ -v
pytest tests/test_executors/ -v

# Run a single test file
pytest tests/test_models/test_model.py -v
```

### Code Quality Commands

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

## Core Architecture

The framework follows a layered architecture:

1. **Core Layer** (`src/core/`): Configuration, exceptions, and base interfaces
2. **Agent Layer** (`src/agents/`): Base agent class and specialized agents (Planner, Executor, Tool Manager, Memory Manager, Enzyme Kinetics Extractor, Enzyme Design Parser)
3. **Model Layer** (`src/models/`): LLM abstraction supporting OpenAI, Anthropic, and custom endpoints with streaming and thinking mode
4. **Tool Layer** (`src/tools/`): Tool registry and implementations (document loader, code executor, file manager, web search, etc.)
5. **Executor Layer** (`src/executors/`): Python, Shell, Docker, and Sandbox execution engines
6. **Memory Layer** (`src/memory/`): Persistent storage and context management
7. **Conversations Layer** (`src/conversations/`): SQLite-based conversation tracking and storage
8. **Web UI Layer** (`src/webui/`): Streamlit-based web interface for conversation visualization

All agents inherit from `BaseAgent` (src/agents/base.py) which provides message passing, state management, and health checks.

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

The config supports multiple providers and special modes:
- **OpenAI**: GPT-3.5, GPT-4, GPT-4 Turbo
- **Anthropic**: Claude 3 series (Sonnet, Opus, Haiku)
- **Custom**: Any API endpoint via `base_url` field
- **Thinking Mode**: Enable via `enable_thinking: true` and `provider_config.extra_body`

Example configuration with thinking mode:
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

### Code Style Configuration

- **Import sorting**: isort with Google profile (`--profile=google`)
- **Code formatting**: yapf with custom style (`.style.yapf`: 88 char limit, 4 space indent)
- **Type checking**: mypy (ignores missing imports)
- **Pre-commit hooks**: Automatically runs isort, yapf, and basic checks on commit

### Code Style Guidelines

**IMPORTANT: No emoji in code**
- **NEVER** use emoji in any files, including source code, comments, log messages, and documentation
- Use plain text alternatives instead:
  - `[ERROR]` or `Error:` (instead of ❌)
  - `[OK]` or `Success:` (instead of ✅)
  - `[INFO]` or `[CSV]` or other descriptive labels (instead of 📊)
  - `[WARNING]` or `Warning:` (instead of ⚠️)
  - `[INFO]` or `Info:` (instead of ℹ️)
- This applies to:
  - Python source files (.py)
  - Configuration files (.json, .yaml)
  - Log messages and print statements
  - Comments and docstrings
  - Markdown documentation files (.md)
- Examples:
  ```python
  # Good
  print(f"[ERROR] Failed to load file: {filename}")
  print(f"[OK] Success - processed {count} items")
  print(f"[CSV] Extracted table data")

   # Bad
  print(f"Failed to load file: {filename}")
  print(f"Success - processed {count} items")
  print(f"Extracted table data")
  ```

**Rationale**: Emoji can cause encoding issues, are not universally supported in all terminals and editors, and reduce code professionalism. Use clear, descriptive text labels instead.

### Pre-Commit Requirements

**MANDATORY: Run tests before committing code changes**

Before committing any code changes, you MUST run the following checks to ensure code quality:

1. **Run Tests**:
   ```bash
   # Run all tests with coverage
   pytest tests/ -v --cov=src --cov-report=term-missing

   # OR run quick smoke tests (faster)
   pytest tests/test_tools/ -v
   ```

2. **Format Code**:
   ```bash
   # Format imports
   isort src/ tests/ examples/

   # Format code
   yapf --in-place --parallel --recursive src/ tests/ examples/
   ```

3. **Type Check** (optional but recommended):
   ```bash
   mypy src/ --ignore-missing-imports
   ```

**Exception**: For documentation-only changes (e.g., deleting .md files), you can skip running tests.

**Rationale**: Catching bugs and style issues before committing prevents broken code from entering the repository and reduces CI/CD failures.

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

**Legacy: Orchestrator-based agent** (for multi-phase extraction)

```python
from src.agents.specialized.llm_enzyme_extractor_orchestrator import \
    LLMEnzymeExtractorAgent
from src.memory.manager import MemoryManager
from src.tools.implementations import DocumentLoaderTool
from src.tools.registry import ToolRegistry

tool_registry = ToolRegistry()
tool_registry.register_tools([DocumentLoaderTool()])
memory_manager = MemoryManager()

agent = LLMEnzymeExtractorAgent(
    "reaction_extractor",
    memory_manager,
    tool_registry,
    model_manager=manager
)
```

### Using the Orchestrator

```python
from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig

config = FrameworkConfig()
orchestrator = AgentOrchestrator(config)
result = await orchestrator.execute_task(task)
```

## Specialized Features

### Enzyme Reaction Extraction

Specialized agents for extracting enzyme reaction data from scientific literature.

**Available Agents:**
- `enzyme_kinetics_extractor` - Kinetic parameters (Km, kcat, Tm, etc.)
- `enzyme_design_parser` - Enzyme design workflows

**Quick Start:**
```bash
# Extract from default file
python examples/reaction_extractor.py

# Extract from specific file
python examples/reaction_extractor.py -i data/my_paper.md

# View extraction sessions in Web UI
streamlit run src/webui/app.py  # Navigate to Agent Sessions
```

**Features:**
- Two-phase architecture (structure analysis → targeted extraction)
- Extracts ALL enzyme variants with kinetics data
- Session tracking with hierarchical display (Agent → Task → Job → Details)
- Reduces token usage by 60-80%

📖 **Detailed Documentation**: [docs/features/enzyme_extraction.md](docs/features/enzyme_extraction.md)

### Streaming Support with Thinking Mode

Real-time streaming of LLM responses with optional thinking/reasoning mode.

**Enable via config:**
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

📖 **Detailed Documentation**: [docs/features/streaming_thinking_mode.md](docs/features/streaming_thinking_mode.md)

### Conversation Tracking

All LLM interactions can be tracked automatically using SQLite-based storage:

```python
from src.conversations.storage import ConversationStorage

# Initialize storage (enabled by default if configured)
storage = ConversationStorage(db_path="data/conversations.db", enabled=True)
await storage.initialize()

# Conversation tracking happens automatically through ModelManager
# Features:
# - Full message history
# - Token usage tracking
# - Response metadata (latency, model parameters)
# - Streaming chunk replay
# - Search across conversations
# - Statistics and analytics
```

**Universal Agent Session Tracking:**

The framework uses a universal agent tracking system that works for any agent type:
- **Agent**: An agent type (e.g., `enzyme_kinetics_extractor`, `planner`, `executor`)
- **Task**: One execution run of an agent (e.g., processing one document)
  - Stored in `extraction_sessions` table
  - Represents a complete workflow execution
- **Job**: Individual LLM calls within a task
  - Stored in `extraction_session_steps` table
  - Linked to conversations via `conversation_id`
- **LLM Call**: The actual conversation with prompts, responses, and metadata

**Hierarchical Display in Agent Sessions Page:**
```
Agent (enzyme_kinetics_extractor)
├── Task 1: listov2025.md (COMPLETED, 2 jobs, 45.2s)
│   ├── Job 01: main_extraction (COMPLETED)
│   │   └── LLM Call Details: prompts, thinking, response
│   └── Job 02: validation (COMPLETED)
│       └── LLM Call Details: prompts, thinking, response
└── Task 2: another_doc.md (IN_PROGRESS, 1 job, 12.1s)
    └── Job 01: main_extraction (IN_PROGRESS)
        └── LLM Call Details: prompts, thinking, response
```

**Key Implementation Details:**
- All jobs are visible including technical steps (e.g., `structure_analysis`)
- Jobs are renumbered sequentially (JOB_01, JOB_02, ...)
- Agent-level stats aggregate all tasks (total tasks, jobs, duration)
- Task-level stats show individual execution metrics
- Each job expands to show full LLM call details with thinking process

View in Web UI:
1. Run: `streamlit run src/webui/app.py`
2. Navigate to: **Agent Sessions**
3. View hierarchical display: Agent → Task → Job → Details
4. Click "View Job Details" to see prompts and responses

### Web UI (Streamlit)

A Streamlit-based web interface for conversation visualization with a Scientific Laboratory theme:

```bash
streamlit run src/webui/app.py
```

Features:
- **Live View**: Real-time streaming conversations with auto-refresh
- **History**: Search and browse all conversations with filtering
- **Statistics**: Token usage, model distribution, success rates
- **Agent Sessions**: Universal agent execution tracking with hierarchical display
  - **4-Level Hierarchy**: Agent → Task → Job → LLM Call Details
  - Filtering by agent, status, and display limit
- **Scientific Laboratory Theme**: Dark background with neon green/blue bio-luminescent accents

📖 **Theme Guide**: [docs/webui/theme_guide.md](docs/webui/theme_guide.md)

### Tool System

Tools are registered in `src/tools/registry.py` and implement the `BaseTool` interface. Available tools:

- **DocumentLoaderTool**: Loads text/markdown files with token estimation
- **CodeExecutorTool**: Executes Python code
- **CodeWriterTool**: Writes code files
- **FileManagerTool**: File system operations
- **WebSearchTool**: Web content retrieval
- **CalculatorTool**: Mathematical calculations
- **PDBECLookupTool**: Protein database lookup

### Vision Image Analyzer

Analyze scientific figures and extract tabular data using vision models.

**Usage:**
```bash
python examples/vision_image_analyzer.py                    # Image 7 (Fig 3a)
python examples/vision_image_analyzer.py --image-number 9   # Specific image
python examples/vision_image_analyzer.py --all              # All images
```

📖 **Detailed Documentation**: [docs/tools/vision_image_analyzer.md](docs/tools/vision_image_analyzer.md)

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

### Delegation Pattern for Specialized Agents

Specialized agents use a **delegation pattern** to separate orchestration from business logic:

```
Agent (Lightweight Orchestrator)
    ↓ delegates to
Tool (Business Logic + LLM Calls)
    ↓ calls
ModelManager (LLM Operations)
```

**Key Principles:**
- **Agents** (`src/agents/specialized/`) - Thin orchestrators that coordinate workflows
- **Tools** (`src/tools/`) - Contain business logic, LLM calls, and data processing
- **Prompts** (`src/tools/prompts.py`) - Centralized prompt templates
- **TrackingMixin** - Provides automatic session tracking for tools

**Benefits:**
- Clear separation of concerns
- Tools are reusable across agents
- Easy to test (tools can be unit tested independently)
- Prompts managed in one location
- Automatic session tracking via TrackingMixin

**Example:**
```python
# Agent (orchestrator)
class EnzymeKineticsExtractorAgent(BaseAgent):
    async def process_task(self, task, session_id=None, agent_id=None, step_id=None):
        # Extract parameters
        text = task.get("text", "")

        # Create tool with tracking
        extractor = EnzymeKineticsExtractorTool(
            model_manager=self.model_manager,
            agent_id=agent_id or self.agent_id,
            session_id=session_id,
            step_id=step_id,
        )

        # Delegate to tool
        result = await extractor.execute(text=text)
        return {"status": STATUS_SUCCESS, "data": result.data}

# Tool (business logic)
class EnzymeKineticsExtractorTool(BaseTool, TrackingMixin):
    async def execute(self, text: str) -> ToolResult:
        # Build prompts, call LLM, process results
        messages = [{"role": "system", "content": ENZYME_KINETICS_EXTRACTION_PROMPT}, ...]
        resp = await self.model_manager.generate(messages, **self.get_tracking_params())
        return ToolResult.success(data)
```

**Reference Implementations:**
- [DocumentStructureAnalyzer](src/tools/document_structure_analyzer.py) + [DocumentStructureAnalyzerAgent](src/agents/specialized/document_structure_agent.py)
- [EnzymeKineticsExtractorTool](src/tools/enzyme_kinetics_extractor.py) + [EnzymeKineticsExtractorAgent](src/agents/specialized/enzyme_kinetics_extractor_agent.py)
- [VisionImageAnalyzerTool](src/tools/vision_image_analyzer.py) + [VisionImageAnalyzerAgent](src/agents/specialized/vision_image_analyzer.py)

**Detailed Documentation:** See [docs/architecture/delegation_pattern.md](docs/architecture/delegation_pattern.md)

## Testing Strategy

**Test Types:**
- Unit tests: Individual components (models, tools, executors)
- Integration tests: Agent interactions
- End-to-end tests: Full workflows

**MANDATORY: Test Requirement for New Features**

Every new feature, tool, or agent MUST have corresponding tests before merging.

**When adding new functionality:**
1. **Tools**: Add tests in `tests/test_tools/test_{tool_name}.py`
2. **Agents**: Add tests in `tests/test_agents/test_{agent_name}.py`

📖 **Detailed Testing Guide**: [docs/testing.md](docs/testing.md)

## CI/CD Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and PR:

1. **Format check**: isort and yapf must pass
2. **Lint**: mypy type checking
3. **Test**: pytest across Python 3.8-3.12 with coverage reporting

## Working with the Codebase

### Code Simplification Before Commits

**IMPORTANT: Always run code-simplifier before committing changes**

When performing commit tasks, you must first execute the code-simplifier agent to ensure code quality:

```python
# Before any commit operation, run:
Task tool with subagent_type="code-simplifier:code-simplifier"
```

**Workflow for commits:**
1. Make code changes
2. Run `code-simplifier:code-simplifier` to refactor and simplify
3. Review simplification changes
4. Clean up documentation .md files (excluding data/ directory)
   - Target: README.md, docs/*.md, etc.
   - Exclude: data/*.md (data files must remain unchanged), CLAUDE.md
5. Format code (isort + yapf)
6. Create commit, but not add claude as co-authors

This ensures all committed code is clean, well-structured, and maintainable, while preserving data files.

### Adding a New Tool

1. Create tool class in `src/tools/implementations.py` inheriting from `BaseTool`
2. Implement `async execute(**kwargs) -> ToolResult`
3. Register in tool registry: `tool_registry.register_tools([MyNewTool()])`
4. **[REQUIRED]** Add tests in `tests/test_tools/test_{tool_name}.py`:
   - Test initialization
   - Test execute() with valid inputs
   - Test error handling and edge cases
   - Test timeout behavior
   - Ensure all tests pass before committing

### Adding a New Agent

**Recommended: Markdown-based agents**

1. Create markdown config in `config/agents/your_agent.md`
2. Define system prompt and tool requirements in markdown
3. Use `MarkdownAgentFactory` to instantiate:
   ```python
   factory = MarkdownAgentFactory()
   agent = factory.create_agent("your_agent", memory_manager, tool_registry, model_manager)
   ```

**Legacy: Python class-based agents**

1. Create agent in `src/agents/specialized/` inheriting from `BaseAgent`
2. Implement required abstract methods: `execute_task()`, `shutdown()`
3. Initialize with required dependencies (memory_manager, tool_registry, model_manager)

4. **[REQUIRED]** Add tests in `tests/test_agents/test_{agent_name}.py`:
   - Test agent initialization
   - Test process_task() or execute_task() methods
   - Test integration with dependencies (memory_manager, tool_registry, model_manager)
   - Test error scenarios
   - Ensure all tests pass before committing

### Adding Streaming Support

When implementing tools or agents that use LLM:

```python
async for chunk in model_manager.generate_stream(messages, role=ModelRole.GENERAL):
    if chunk.is_thinking:
        # Handle reasoning content
        process_thinking(chunk.reasoning_content)
    if chunk.content:
        # Handle response content
        process_content(chunk.content)
    if chunk.is_complete:
        # Handle completion
        handle_complete(chunk.metadata)
```

### Modifying LLM Prompts

**For enzyme kinetics extraction:**
Edit the system prompt in `config/agents/enzyme_kinetics_extractor.md`

**For enzyme design parsing:**
Edit the system prompt in `config/agents/enzyme_design_parser.md`

**Legacy (Python-based agents):**
For enzyme extraction, edit prompts in `config/agents/enzyme_kinetics_extractor.md`. The system prompt defines the extraction schema and rules.

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
  - Supports `enable_thinking` and `provider_config` for advanced features
- **Agent Configs**: `config/agents/*.md` contains markdown-based agent definitions
- **Examples**: `examples/` contains runnable demos showing framework usage
  - `chat_demo.py` - Streaming chat with thinking mode
  - `reaction_extractor.py` - Enzyme kinetics extraction with session tracking
- **Test data**: `data/` contains sample documents for testing
  - `data/conversations.db` - SQLite database for conversation and session tracking
  - `data/analysis/` - Document structure analysis outputs
  - `data/extraction/` - Extracted reaction data in JSON format
- **Scripts**: `scripts/` contains startup and utility scripts
- **Documentation**: `docs/` contains detailed workflow documentation
- **Web UI**: `src/webui/` contains Streamlit web interface

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
  - `planner` - Task planning agent
  - `executor` - Task execution agent
  - `tool_manager` - Tool management agent
  - `memory_manager` - Memory management agent
  - Legacy Python classes remain in `src/agents/specialized/` as backup references

### Model Role Types

The framework uses `ModelRole` enum for different model configurations:
- `ModelRole.GENERAL` - General purpose tasks
- `ModelRole.EXTRACTION` - Data extraction tasks
- `ModelRole.ANALYSIS` - Document analysis tasks
- `ModelRole.SPECIALIZED` - Specialized domain tasks
- `ModelRole.PLANNING` - Planning and orchestration tasks
- `ModelRole.CODE_EXECUTION` - Code generation and execution tasks

Each role can have its own model configuration in `llm_config.template.json`.

### Conversation Tracking Configuration

Conversation tracking is controlled via the ModelManager. When enabled, all LLM interactions are automatically stored in SQLite:

```python
from src.utils import default_manager

manager = default_manager()

# Tracking is enabled by default if ConversationStorage is initialized
# The database is created at: data/conversations.db
# Web UI reads from this database for visualization
```
