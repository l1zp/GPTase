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
| `python examples/enzyme_design_planner_demo.py paper.md` | Enzyme design planning demo |
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
  tools/          General-purpose tool registry and implementations
  mcp/            MCP-specific enzyme tools and databases
  memory/         Persistent storage and context
  conversations/  SQLite-based tracking
  webui/          Streamlit interface
```

All agents use `BaseAgent` ([src/agents/base.py](src/agents/base.py)) or `MarkdownAgent` ([src/agents/markdown_agent.py](src/agents/markdown_agent.py)).

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
    "plan_id": "enzyme_extraction_pipeline",
    "text": "..."
})
```

## Specialized Features

### Enzyme Reaction Extraction

| Component | Purpose |
|-------|---------|
| `enzyme_extraction_pipeline` SOP | SOP for standard extraction workflow |
| `enzyme_kinetics_extractor` | Agent for kinetic parameters (Km, kcat, Tm) |

```bash
python examples/reaction_extractor.py
python examples/reaction_extractor.py -i data/my_paper.md
```

Features: AI-native SOP, data-driven flow, token-efficient pre-processing tools.

### 5-Phase Planning System

The framework includes an interactive planning workflow for complex tasks:

1. **Understanding Phase** - Ask clarifying questions about requirements
2. **Design Phase** - Create detailed implementation approach with agent delegation
3. **Review Phase** - Present plan and collect user feedback
4. **Final Plan Phase** - Generate executable workflow JSON
5. **Exit Phase** - Request final approval before execution

See [src/tools/planner_tool.py](src/tools/planner_tool.py) for implementation details.

### External Database Tools

Located in [src/mcp/databases/](src/mcp/databases/):

| Tool | Purpose |
|------|---------|
| `pdb.py` | PDB -> EC number lookup via RCSB API |
| `rhea.py` | Rhea biochemical reaction database |
| `kegg.py` | KEGG pathway database lookup |
| `expasy.py` | Expasy enzyme nomenclature |
| `pubchem.py` | PubChem SMILES notation lookup |

All external database tools inherit from the base class in [src/mcp/databases/base.py](src/mcp/databases/base.py).

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

- Agents: Markdown personas with tool capabilities
- Tools: Business logic, heavy parsing, data processing
- SOPs: Predefined standard pipelines
- Executor: Variable-aware runtime

### Tool Architecture

The tool system has been consolidated with a unified base class structure:

**Base Components** ([src/tools/base.py](src/tools/base.py)):
- `ToolResult` - Standardized result structure with status, data, error tracking
- `TrackingMixin` - Mixin for conversation tracking (agent_id, session_id, step_id)
- `BaseTool` - Abstract base class for all tools with timeout handling
- `FunctionTool` - Quick tool creation from functions
- `@tool` decorator - Convert async functions to tools

**Tool Categories**:
- **General Tools** ([src/tools/](src/tools/)):
  - Document Tools ([src/tools/document.py](src/tools/document.py)): DocumentLoaderTool, MinerUTool
  - System Tools ([src/tools/system.py](src/tools/system.py)): CodeWriterTool, CodeExecutorTool, FileManagerTool
  - Utility Tools ([src/tools/utils.py](src/tools/utils.py)): Calculator, WebSearch
  - Framework Core: executor_tool.py, planner_tool.py
- **MCP Domain-Specific Tools** ([src/mcp/tools/](src/mcp/tools/)): enzyme_kinetics_tool.py, enzyme_design_tool.py, vision_tool.py, document_structure_tool.py
- **MCP Databases** ([src/mcp/databases/](src/mcp/databases/)): PDB, Rhea, KEGG, Expasy, PubChem lookup tools

## Communication Patterns

### Code Organization Scope

When restructuring or reorganizing tools, **clarify the scope upfront**:
- Is this a generic framework refactor (affecting core architecture)?
- Or is it domain-specific (e.g., enzyme-related MCP tools)?

This prevents misunderstandings where generic framework solutions are proposed when domain-specific separation is intended. Always confirm the architectural boundary before proceeding with reorganization work.

### Dead Code Removal Workflow

For dead code removal projects, follow this safety pattern:
1. **Grep for imports/references** across the entire codebase before deletion
2. **Check for any exports** or public API exposure
3. **Identify related tests** that may need updates
4. **Present findings** before deletion
5. **Run tests** after removing potentially unused code

This verification step prevents accidental breaking changes and ensures no remaining references exist.

## Working with the Codebase

### Adding a New Tool

1. Create class in `src/tools/` inheriting from `BaseTool`.
2. Implement `async execute(**kwargs) -> ToolResult`.
3. Implement `get_schema() -> dict` for parameter validation.
4. Register in `src/agents/orchestrator.py`.
5. Add tests in `tests/test_tools/test_{tool_name}.py` (required).

Example:

```python
from src.tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="Description of what this tool does",
            timeout=30
        )

    async def execute(self, **kwargs) -> ToolResult:
        # Implementation here
        return ToolResult.success(data={"result": "value"})

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string"}
            },
            "required": ["param1"]
        }
```

### Adding a New Agent

**Markdown-based (recommended):**
1. Create config in `config/agents/your_agent.md`.
2. Use HTML comment metadata markers at the top:
   - `@agent_id`: Unique identifier (must match filename)
   - `@capabilities`: Comma-separated list of skills
   - `@requires_model`: `true` or `false`
   - `@model_role`: `general`, `extraction`, `analysis`, `planning`
   - `@temperature`: Float (0.0 - 1.0)
   - `@max_tokens`: Integer limit for responses
3. Include required sections: `## Agent Description`, `## System Prompt`, `## Task Processing`, `## Output Format`, `## Examples`
4. Use `MarkdownAgentFactory` to instantiate.

### Adding a New SOP

1. Create workflow in `config/sops/your_sop.json`.
2. Use `{{stepN.path}}` for data flow between agents.
3. Define workflow steps with agent, action, and inputs.

Example structure:
```json
{
  "plan_id": "my_pipeline",
  "name": "My Pipeline",
  "workflow": [
    {
      "step_id": 1,
      "agent": "agent_name",
      "action": "action_name",
      "inputs": {"param": "{{input_text}}"}
    },
    {
      "step_id": 2,
      "agent": "another_agent",
      "action": "extract",
      "inputs": {"text": "{{step1.output_path}}"}
    }
  ]
}
```

## Agent Markdown Specification (`config/agents/*.md`)

GPTase uses a unified Markdown-based system to define agents. Follow these standards for consistent parsing and optimal performance.

### Metadata Markers (HTML Comments)
Include a marker block at the very top of the file to define core agent attributes.
- `@agent_id`: Unique identifier (must match filename)
- `@capabilities`: Comma-separated list of skills
- `@requires_model`: `true` or `false`
- `@model_role`: `general`, `extraction`, `analysis`, `planning`
- `@temperature`: Float (0.0 - 1.0)
- `@max_tokens`: Integer limit for responses

### Mandatory Sections (## Headers)
The parser (`MarkdownParser`) expects the following headers to build the system prompt:
1. `## Agent Description`: High-level persona and objective
2. `## System Prompt`: Detailed instructions and rules for the LLM
3. `## Task Processing`: Sequential steps for handling tasks
4. `## Output Format`: Definition of expected result structure (e.g., JSON schema)
5. `## Examples`: Few-shot task/response pairs for guidance

### Best Practices
- **Conciseness**: Keep instructions sharp. Use `[RULES]` or `[STRATEGY]` tags instead of emojis
- **Expert Delegation**: When writing for the `planner`, focus on "who" (agent) handles "what" (task)
- **Format Consistency**: Always specify structured output (JSON preferred) in the `Output Format`
- **Progressive Disclosure**: Guide the agent to find deep rules in `CLAUDE.md` or `docs/` rather than over-documenting within the prompt

## Tool Registry

Tools are registered centrally in [src/tools/registry.py](src/tools/registry.py). The `ToolRegistry` class manages:
- Tool registration and retrieval
- Tool execution with error handling
- Tracking parameter injection for tools that inherit from `TrackingMixin`

## CI/CD Pipeline

GitHub Actions (`.github/workflows/ci.yml`):
1. Format check (isort, yapf)
2. Type checking (mypy)
3. Tests (pytest across Python 3.8-3.12)

## Recent Architecture Changes

### Tools/MCP Reorganization (2025)
- Separated general-purpose tools from enzyme-specific MCP tools
- Moved enzyme-specific tools to [src/mcp/tools/](src/mcp/tools/):
  - enzyme_kinetics_tool.py
  - enzyme_design_tool.py
  - document_structure_tool.py
  - vision_tool.py
- Moved external database tools to [src/mcp/databases/](src/mcp/databases/):
  - PDB, Rhea, KEGG, Expasy, PubChem lookup tools
- Kept general-purpose tools in [src/tools/](src/tools/):
  - Document, system, utility tools
  - Framework core: executor_tool.py, planner_tool.py

### Tool Consolidation (2024)
- Merged `src/tools/implementations.py` content into individual tool files
- Moved prompts from `src/tools/prompts.py` into respective tool files
- Integrated `TrackingMixin` into `src/tools/base.py`
- Created [src/mcp/databases/](src/mcp/databases/) for database lookup tools
- Added new system tools in [src/tools/system.py](src/tools/system.py)
- Added document processing tools in [src/tools/document.py](src/tools/document.py)

### Markdown-Driven Agents (2024)
- Removed `src/agents/specialized/` directory (Python-based agents)
- Migrated all agent definitions to Markdown configs in `config/agents/`
- Added `MarkdownAgentFactory` for instantiating agents from Markdown
- Added `executor.md` agent for SOP/plan execution

### 5-Phase Planning System (2024)
- Implemented interactive planning workflow in [src/tools/planner_tool.py](src/tools/planner_tool.py)
- Added `planner.md` agent configuration
- Planning phases: Understanding, Design, Review, Final Plan, Exit
