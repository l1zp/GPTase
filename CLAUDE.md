# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GPTase is a multi-agent framework for AI task automation with specialized capabilities for biochemical analysis. It provides a flexible architecture for building AI agent systems with support for multiple LLM providers, code execution engines, and memory management.

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

# Start Streamlit web UI for conversation viewing
streamlit run src/webui/app.py

# Run enzyme reaction extraction with session tracking
python examples/reaction_extractor.py

# Run streaming chat demo with thinking mode
python examples/chat_demo.py              # Streaming with thinking mode (default)
python examples/chat_demo.py --no-thinking # Streaming without thinking
python examples/chat_demo.py --simple      # Simple mode (non-streaming)

# Analyze scientific figures with vision model
python examples/vision_image_analyzer.py                    # Analyze Image 7 (Fig 3a) by default
python examples/vision_image_analyzer.py --image-number 9   # Analyze specific image
python examples/vision_image_analyzer.py --all              # Analyze all relevant images
python examples/vision_image_analyzer.py --config config/llm_config.qwen_vl.example.json
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
from src.agents.specialized.llm_enzyme_extractor_orchestrator import LLMEnzymeExtractorAgent
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry
from src.tools.implementations import DocumentLoaderTool

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

**Extraction Pipeline with Session Tracking:**

The extraction process uses a **two-phase architecture** with session tracking:

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT: Scientific Literature (Markdown/HTML/Text)              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: Document Structure Analysis                          │
│  ────────────────────────────────────────────────────────────  │
│  Tool: DocumentStructureAnalyzer                                │
│  Step: structure_analysis (phase1_structure)                    │
│  ────────────────────────────────────────────────────────────  │
│  ✓ Identify document sections and hierarchy                     │
│  ✓ Extract ALL tables (Markdown & HTML formats)                 │
│  ✓ Classify tables using LLM (confidence > 0.6)                 │
│    - Kinetics tables, mutation tables, etc.                    │
│  ✓ Locate key paragraphs with kinetic keywords                 │
│  ✓ Save analysis to data/analysis/{doc}_analysis.json          │
│  ────────────────────────────────────────────────────────────  │
│  Output: Structured tables + relevant paragraphs               │
│  Tokens: ~60-80% reduction vs. full document                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: Targeted LLM Extraction                              │
│  ────────────────────────────────────────────────────────────  │
│  Agent: LLMEnzymeExtractorAgent                                 │
│  Step: main_extraction (phase2_extraction)                      │
│  ────────────────────────────────────────────────────────────  │
│  ✓ Process ONLY relevant content from Phase 1                   │
│  ✓ Extract structured reaction data:                           │
│    - Enzyme variants (ALL rows from tables)                     │
│    - Substrates & products                                      │
│    - Kinetics: kcat, KM, kcat/KM, Tm, Vmax                     │
│    - Experimental conditions (temp, pH, buffer)                │
│    - PDB IDs, citations, yields                                 │
│  ✓ Validate against Pydantic schema                             │
│  ✓ Output to data/extraction/{doc}_extraction.json              │
│  ────────────────────────────────────────────────────────────  │
│  Output: Structured JSON with EnzymeReaction[]                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Session Tracking (SQLite Database)                             │
│  ────────────────────────────────────────────────────────────  │
│  Database: data/conversations.db                                 │
│  ✓ extraction_sessions: One entry per document processed        │
│  ✓ extraction_session_steps: structure_analysis + main_extraction│
│  ✓ conversations: Full LLM prompts & responses                 │
│  ✓ messages: Individual message history                         │
│  ✓ responses: Metadata (tokens, latency, thinking process)      │
│  ────────────────────────────────────────────────────────────  │
│  View in Web UI: Agent Sessions page                             │
│  → See prompts, thinking, responses for each step              │
└─────────────────────────────────────────────────────────────────┘
```

**Quick Start:**

Run extraction on a document:
```bash
# Extract from default file (data/listov2025.md)
python examples/reaction_extractor.py

# Extract from specific file
python examples/reaction_extractor.py -i data/my_paper.md

# Specify custom output path
python examples/reaction_extractor.py -i data/paper.md -o data/results/output.json
```

View extraction sessions in Web UI:
```bash
streamlit run src/webui/app.py
# Navigate to: Agent Sessions
```

**Key Features:**

1. **Comprehensive Extraction**: Extracts ALL enzyme variants from tables
   - Not just "important" or "main" variants
   - Each table row = separate reaction entry
   - Handles uncertainties (±), "n.c." (not calculable), "n.d." (not detected)

2. **Smart Content Selection** (Phase 1):
   - LLM-based table classification (kinetics, mutations, methods)
   - Identifies paragraphs with experimental details
   - Reduces token usage by 60-80% vs. full document

3. **Structured Output** (Phase 2):
   - Enzyme names, substrates, products
   - Kinetic parameters: kcat, KM, kcat/KM, Tm, Vmax
   - Experimental conditions: temperature, pH, buffer, time
   - PDB IDs, citations, yields
   - Validates against Pydantic schema

4. **Full Traceability** (Session Tracking):
   - View complete prompts sent to LLM
   - See thinking/reasoning process (when enabled)
   - Monitor tokens, latency, throughput
   - Hierarchical display: Agent → Task → Job → Details

**Output Format:**

```json
{
  "reactions": [
    {
      "source_file": "inline_text.md",
      "enzyme_name": "Des27",
      "substrates": ["5-nitrobenzisoxazole"],
      "products": ["2-nitrophenol"],
      "conditions": {
        "temperature": "25 °C",
        "pH": "7.3",
        "buffer": "20 mM HEPES",
        "time": null,
        "notes": null
      },
      "kinetics": {
        "Km": null,
        "Km_unit": "mM",
        "Vmax": null,
        "Vmax_unit": null,
        "kcat": null,
        "kcat_unit": "s^-1",
        "kcat_over_KM": 130,
        "kcat_over_KM_unit": "M^-1s^-1",
        "Tm": null,
        "Tm_unit": "°C"
      },
      "yield_percent": null,
      "citations": [],
      "pdb_ids": []
    }
  ]
}
```

**Session Tracking in Web UI:**

The Agent Sessions page displays a 4-level hierarchy:
```
Agent (reaction_extractor)
├── Task 1: listov2025.md (COMPLETED, 2 jobs, 45.2s)
│   ├── Job 01: structure_analysis (COMPLETED)
│   │   └── LLM Call Details: tables identified, paragraphs located
│   └── Job 02: main_extraction (COMPLETED)
│       └── LLM Call Details: prompts, thinking, extracted reactions
└── Task 2: another_doc.md (IN_PROGRESS, 1 job, 12.1s)
    └── Job 01: main_extraction (IN_PROGRESS)
        └── LLM Call Details: prompts, thinking, response
```

Click "View Job Details" to see:
- **Prompt Messages**: Collapsible sections for each role (User/Assistant/System)
- **Thinking Process**: LLM reasoning (when thinking mode enabled)
- **Response**: Extracted reaction data
- **Metrics**: Tokens, latency, throughput

### Streaming Support with Thinking Mode

The framework supports real-time streaming of LLM responses with optional thinking/reasoning mode:

```python
from src.utils import default_manager
from src.models.types import ModelRole

manager = default_manager()
config = manager.get_role_config(ModelRole.GENERAL)

# Enable thinking mode for models that support it (e.g., Claude with extended thinking)
config_with_thinking = config.model_copy(update={"enable_thinking": True})

# Streaming with thinking mode
async for chunk in manager.generate_stream(
    messages,
    role=ModelRole.GENERAL,
    config=config_with_thinking
):
    if chunk.is_thinking and chunk.reasoning_content:
        print(f"Thinking: {chunk.reasoning_content}")
    elif chunk.content:
        print(f"Answer: {chunk.content}")
```

The `StreamChunk` type provides:
- `content`: Response text chunk
- `reasoning_content`: Thinking/reasoning chunk (when thinking mode enabled)
- `is_thinking`: Whether current chunk is reasoning content
- `is_complete`: Whether streaming is complete
- `metadata`: Usage info, errors, etc.

**Enabling Thinking Mode via Configuration:**

Thinking mode can be enabled globally in `config/llm_config.template.json`:

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

This will enable thinking mode for all LLM calls automatically. The `FrameworkConfig` class properly loads these settings and passes them to `ModelConfig`, which then uses them when constructing API requests.

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

**Extraction Session Tracking**

Multi-step workflows like enzyme extraction are tracked as sessions:

```python
# Sessions are automatically created when running agents
# Each LLM call is linked to a step within a session
from src.conversations.storage import ConversationStorage

storage = ConversationStorage(db_path="data/conversations.db", enabled=True)

# Start an extraction session
session_id = await storage.start_extraction_session(
    document_path="data/document.md",
    extraction_type="kinetics",
    agent_id="reaction_extractor",
)

# Track workflow steps
step_id = await storage.start_session_step(
    session_id=session_id,
    step_name="structure_analysis",
    step_phase="phase1_structure",
    step_order=1,
)

# Complete step
await storage.complete_session_step(step_id)

# Complete session
await storage.complete_extraction_session(session_id, ExtractionSessionStatus.COMPLETED)
```

**Session Tracking Features:**
- Groups related LLM calls into workflows
- Tracks step order and phases (structure analysis, extraction)
- Links LLM calls to extraction steps
- Stores session statistics (total steps, tokens, latency)
- Visualized in Web UI under "Agent Sessions" page with 4-level hierarchy:
  - Agent → Task (document processing) → Job (LLM call) → Details

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
  - **Agent Level**: Shows agent_id with aggregated stats (total tasks, jobs, duration)
  - **Task Level**: Shows extraction sessions (individual document processing runs)
    - Displays document name, extraction type, job count, duration
    - Status badges (COMPLETED, IN_PROGRESS, FAILED)
  - **Job Level**: Shows workflow steps (LLM conversations)
    - All jobs are visible including technical steps (e.g., `structure_analysis`)
    - Jobs are renumbered sequentially (JOB_01, JOB_02, ...)
    - Animated pulsing nodes with status-based colors
  - **LLM Call Details**: Expandable sections showing:
    - Full prompts and responses
    - Thinking/reasoning process (when enabled)
    - Token usage, latency, throughput metrics
  - Filtering by agent, status, and display limit
- **Scientific Laboratory Theme**: Dark background with neon green/blue bio-luminescent accents
  - Monospace fonts for technical precision
  - Animated workflow nodes with pulsing indicators
  - Glowing status badges and hover effects
- Thinking/reasoning content display in expandable sections
- Response metadata (tokens, latency, throughput)

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

A tool for analyzing scientific figures and extracting tabular data using vision models:

```bash
python examples/vision_image_analyzer.py --help
```

**Key Features:**
- Loads image information from CSV files
- Uses vision models (Qwen3-VL) to analyze scientific figures
- Extracts tabular data and outputs in CSV format
- Supports batch processing of multiple images
- Configuration file support for API settings

**Usage Examples:**

```bash
# Analyze specific image (default: Image 7 / Fig 3a)
python examples/vision_image_analyzer.py

# Analyze different image
python examples/vision_image_analyzer.py --image-number 9

# Analyze all relevant images
python examples/vision_image_analyzer.py --all

# Limit to first 5 images
python examples/vision_image_analyzer.py --all --max-images 5

# Use custom configuration file
python examples/vision_image_analyzer.py --config config/llm_config.qwen_vl.example.json

# Specify custom CSV path
python examples/vision_image_analyzer.py --csv-path data/analysis/custom_images.csv
```

**Configuration:**

The tool reads configuration from JSON files (default: `config/llm_config.qwen_vl.example.json`):

```json
{
  "model_name": "Qwen3-VL-235B-A22B-Thinking",
  "api_key": "your-api-key",
  "base_url": "https://api.example.com/v1/",
  "temperature": 1,
  "max_tokens": 16384
}
```

**Output:**
- `data/image_analysis_results.json` - Full analysis results (JSON format)
- `data/image_analysis_extracted_tables.csv` - Extracted tabular data (CSV format)

**Prompt Engineering:**

The tool uses specialized prompts for scientific figure analysis:
- Automatic detection of figure type (table, plot, diagram, etc.)
- Extraction of all numerical values and data
- Structured CSV output for tabular data
- Support for enzyme kinetics data (variants, substitutions, kinetic parameters)

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
  - `app.py` - Main application with Scientific Laboratory theme CSS
  - `agent_sessions_lab.py` - Agent Sessions page with hierarchical display
  - Features 4-level hierarchy: Agent → Task → Job → LLM Call Details
  - **Scientific Laboratory Theme**:
    - Dark gradient background (#1a1f2e to #0f1a1f)
    - Neon green (#00ff9d) and blue (#00d4ff) accent colors
    - Monospace fonts (SF Mono, Fira Code) for technical content
    - Animated pulsing workflow nodes
    - Glowing status badges with hover effects
    - Custom scrollbar styling
- **Conversations**: `src/conversations/` contains SQLite-based tracking system
  - `schema.sql` - Database schema with extraction_sessions, extraction_session_steps tables
  - `storage.py` - Session management and query methods
  - `models.py` - Pydantic models for sessions and steps

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
