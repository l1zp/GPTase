# GPTase - Multi-Agent Framework

A comprehensive, elegant framework for building and managing AI agent systems with support for multiple LLM providers, multimodal messages, code execution, and unified Plan-based Standard Operating Procedures.

## Features

### Multi-Agent System (AI-Native)
- **Markdown-Driven Agents** - Define persona, prompt, and tools via `.md` files
- **Plan Orchestration** - Execute complex workflows defined in DAG format with parallel execution
- **Unified Plan Manager** - Multi-agent coordination with dispatch-collect pattern
- **AI-Driven Failure Recovery** - Intelligent abort/skip/retry decisions on task failures
- **Variable Data Flow** - Seamless data passing between agents using `{{taskN.path}}` syntax
- **Goal-Oriented Harness** - Create draft plans, review them, then execute toward a user goal
- **Multimodal Support** - Vision agents with automatic image encoding and analysis
- **Pytest Generation** - Built-in expert skill for generating idiomatic, high-quality tests from source code

### LLM Integration
- **Unified Provider Interface** - Support for OpenAI-compatible endpoints (including custom base URLs)
- **Provider Routing Controls** - Pass provider-specific routing/options via `extra_body.provider`
- **Thinking Mode** - Native support for reasoning-enabled models (e.g., Qwen3, GPT-4o)
- **Multimodal Messages** - Vision support with `TextContent` and `ImageUrlContent` types
- **Specialized Roles** - Optimized configurations for Extraction, Analysis, and Planning
- **Agent Working Memory** - Named agents automatically reuse compressed prior context across runs

### Tools Architecture
- **Consolidated Tool System** - Unified base classes with timeout handling and error management
- **MCP Tool Integration** - Register tools from stdio/SSE MCP servers into the same tool loop
- **Safer Tool Feedback** - Large tool outputs are truncated before the next model turn to avoid context blowups
- **Document Processing** - PDF/HTML/Text loading from files or URLs (including MinerU integration)
- **Vision Analysis** - Scientific figure analysis with CSV data extraction
- **System Tools** - Code writing, execution, and file management
- **External Databases** - PDB, Rhea, KEGG, Expasy, PubChem lookup tools
- **Biochemical Analysis** - Enzyme kinetics, design methodology extraction, and summary generation

## Project Structure

```
gptase/
├── gptase/                      # Source code
│   ├── agents/                  # Agent implementations
│   │   ├── base.py              # Base agent interface
│   │   ├── agent.py             # Unified Agent with multimodal support
│   │   ├── markdown_agent.py    # Markdown-driven agent & factory
│   │   ├── planner.py           # Plan generation & management
│   │   ├── plan_loader.py       # YAML/JSON plan loading
│   │   ├── plan_dispatcher.py   # Task dispatch and result collection
│   │   ├── plan_failure_handler.py # AI-driven failure recovery
│   │   ├── execution_types.py   # Context and checkpoint models
│   │   └── types.py             # Agent and Plan models (Plan, Task, etc.)
│   ├── models/                  # LLM management
│   │   ├── model.py             # Model manager with agent-specific configs
│   │   ├── providers.py         # OpenAI provider with streaming
│   │   └── types.py             # ModelConfig, TextContent, ImageUrlContent
│   ├── core/                    # Config, constants, logging, exceptions, paths
│   ├── memory/                  # SQLite-based storage (manager, storage, models, types)
│   ├── main.py                  # CLI entry point
│   └── utils.py                 # Utility functions
├── .claude/                     # Claude Code integration
│   └── agents/                  # Agent definitions (directory layout)
│       ├── document-structure-analyzer/
│       │   └── document-structure-analyzer.md
│       ├── enzyme-kinetics-extractor/
│       │   └── enzyme-kinetics-extractor.md
│       ├── enzyme-extraction-summary/
│       │   └── enzyme-extraction-summary.md
│       ├── planner/
│       │   └── planner.md
│       └── vision-image-analyzer/
│           ├── vision-image-analyzer.md
│           └── evals/
├── config/                      # Configuration
│   └── plans/                   # Unified Plans (YAML/JSON)
│       └── enzyme_extraction_pipeline.yaml
├── tests/                       # Comprehensive test suite
│   ├── test_planner.py          # Plan system tests
│   ├── test_agent_multimodal.py # Multimodal Agent tests
│   ├── test_models.py           # Model and multimodal type tests
│   └── test_agents/             # Agent-specific tests
└── examples/                    # Usage examples
    ├── vision_image_analyzer.py # Multimodal image analysis
    ├── reaction_extractor.py    # Enzyme extraction (Plan mode)
    └── chat_demo.py             # Chat with thinking mode
```

## Web UI

The repository keeps the frontend in the `ui/` subproject.

- Development: run the Python API locally, then run the Vite dev server in `ui/`
- Production: build `ui/dist`, then let `gptase web` serve the SPA and assets

This is a single-repo setup with split responsibilities: frontend code lives under `ui/`, while final production hosting stays in the FastAPI service. See [ui/README.md](ui/README.md) for frontend-specific commands and route contracts.

## Quick Start

### Installation

```bash
git clone https://github.com/l1zp/GPTase.git
cd GPTase

# Create conda environment (recommended)
conda create -n llm python=3.11 -y
conda activate llm

# Install in development mode
pip install -e ".[models,dev]"
```

For detailed setup instructions, see [Environment Setup Guide](docs/environment_setup.md).

### Configuration

Set your API key in `config/llm_config.template.json` or via environment:

```bash
export OPENAI_API_KEY="your-api-key-here"
export BRAVE_API_KEY="your-brave-key"      # optional, for MCP search servers
export TAVILY_API_KEY="your-tavily-key"    # optional, for MCP search servers
```

Common config knobs:

```json
{
  "model_name": "GLM-5",
  "base_url": "https://aiping.cn/api/v1",
  "max_tokens": 131072,
  "provider": {
    "sort": "input_length"
  },
  "mcp_servers": {
    "brave-search": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "YOUR_BRAVE_API_KEY"
      }
    }
  }
}
```

Notes:
- `max_tokens` controls output length, not total input context size.
- `provider` is forwarded to upstream providers as `extra_body.provider`.
- `mcp_servers` is loaded by both the Claude SDK path and the non-Claude `ToolExecutor` path.

### Basic Usage

```bash
# List available agents
gptase list

# Run a task
gptase agent -n <name> -d "Analyze this document"

# Plan workflow execution
gptase plan --list                           # List available plans
gptase plan -p enzyme_extraction_pipeline -i data/paper.md -o output/

# Enzyme extraction from paper (example script)
python examples/reaction_extractor.py -i data/paper.md

# Multimodal image analysis
python examples/vision_image_analyzer.py path/to/image.png

# Chat with thinking mode
python examples/chat_demo.py
```

### Execution Modes

Agents run in direct execution mode by default:

```python
# Direct execution (default)
result = await agent.run("Analyze this data")

# You can also manually access the planner:
plan = await agent.planner.create_plan("Complex task description")
print(f"Plan created with {len(plan.tasks)} steps.")
result = await agent.planner.execute_plan(plan)
```

## Multimodal Support

### Vision Agent

Analyze scientific figures with vision models:

```bash
# Single image
python examples/vision_image_analyzer.py figure.png

# Multiple images
python examples/vision_image_analyzer.py fig1.png fig2.png

# Use ReAct agent for complex figures
python examples/vision_image_analyzer.py figure.png --agent vision_image_analyzer_react
```

### Programmatic Usage

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
result = await agent.run(
    content="Extract tabular data from this figure",
    image_paths=["figure.png"],
)
```

## Agent Memory

Named agents now maintain a compressed working-memory summary in SQLite and
automatically inject it into future runs. This provides lightweight continuity
without replaying full chat history.

Key behavior:
- only agents with a non-empty `agent_id` participate
- memory is injected automatically before execution
- successful runs update the summary after execution
- failed runs do not update memory unless `memory.update_on_failure = true`

## Standard Enzyme Extraction Plan

The framework provides an industrial-grade pipeline for enzyme data processing.

### The Workflow

Defined in `config/plans/enzyme_extraction_pipeline.yaml`:

1. **document_structure_analyzer**: Physical scan to locate relevant tables
2. **enzyme_kinetics_extractor**: Expert LLM extraction from text
3. **vision_image_analyzer**: Extract data from figures using vision models
4. **enzyme_extraction_summary**: Statistical synthesis and ranking

### Running the Pipeline

```bash
# Via CLI
gptase plan -p enzyme_extraction_pipeline -i data/paper.md -o output/

# List available plans
gptase plan --list

# Via Python
python examples/reaction_extractor.py -i data/paper.md
```

### Plan Features

- **YAML Format**: Readable, supports comments
- **Parallel Execution**: Automatic parallelization of independent tasks
- **Template Variables**: `{{input_text}}`, `{{task1.field.nested}}`
- **Workspace Management**: Unified `workspace_dir` automatically maps agents to the input document's directory
- **Failure Recovery**: AI-driven abort/skip/retry decisions
- **Checkpointing**: Resume long-running plans from failure points
- **Retro-compatibility**: Existing Plan YAMLs are automatically loaded as Plans

### Writing a New Plan

Create `config/plans/my_pipeline.yaml`:

```yaml
plan_id: my_pipeline
name: My Pipeline
description: What this pipeline does
version: "1.0"

tasks:
  - task_id: "1"
    agent_id: document_structure_analyzer
    description: Analyze document structure
    inputs:
      text: "{{input_text}}"

  - task_id: "2a"
    agent_id: extractor_a
    dependencies: ["1"]
    inputs:
      data: "{{task1}}"

  - task_id: "2b"
    agent_id: extractor_b
    dependencies: ["1"]
    inputs:
      data: "{{task1}}"

  - task_id: "3"
    agent_id: summarizer
    dependencies: ["2a", "2b"]
    inputs:
      result_a: "{{task2a}}"
      result_b: "{{task2b}}"
```

### Behind the Scenes

- **Agent Initialization**: The orchestrator loads agent definitions from `.claude/agents/`
- **Dispatch-Collect Pattern**: Tasks dispatched to agents, results collected and aggregated
- **Data Flow**: Output from each task automatically flows to the next via template variables

## Advanced Orchestration

### Dynamic Planning And Harness Sessions

For novel tasks, let the orchestrator create a draft plan first, then optionally
review and approve it before execution:

```python
result = await orchestrator.dispatch({
    "description": "Analyze this paper and compare variants against wild-type",
    "auto_execute": False,
})
```

Approve the draft later with the returned `session_id`:

```python
result = await orchestrator.approve_plan(session_id)
```

### Writing a New Agent

Create a Markdown file with YAML frontmatter in `.claude/agents/my-expert/my-expert.md`:

```markdown
---
name: my-expert
description: A specialized expert for data analysis tasks
tools: Read, Grep, Glob
model: sonnet
color: blue
---

You are a specialized expert in data analysis.

## Workflow
1. Parse the input data
2. Apply analysis algorithms
3. Generate structured output

## Output Guidance
Return results in JSON format with the following schema:
{
  "analysis": "string",
  "metrics": {"accuracy": "number"},
  "recommendations": ["string"]
}
```

### Agent Format Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique agent identifier (use hyphens) |
| `description` | Yes | What the agent does (used for triggering) |
| `tools` | No | Comma-separated tool list (Read, Grep, Bash, Glob) |
| `model` | No | Model to use: `opus`, `sonnet` (default), `haiku` |
| `color` | No | Display color for UI purposes |

## Testing

GPTase follows strict testing conventions:
- **Async Mode**: `asyncio_mode = "auto"`. **No** `@pytest.mark.asyncio` needed.
- **Structure**: Tests must be inside `class Test...`.
- **Smart Generation**: Use the `pytest-writer` skill to generate tests following project style.

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=gptase

# Run specific test categories
pytest tests/test_agents/ -v
pytest tests/test_models.py -v
```

## License

CC BY-NC 4.0 License. See [LICENSE](LICENSE) for details.
