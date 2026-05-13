# GPTase - Multi-Agent Framework

A comprehensive, elegant framework for building and managing AI agent systems with support for multiple LLM providers, multimodal messages, code execution, and unified Plan-based workflows.

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
│   │   ├── hooks.py             # Agent hook context and lifecycle hooks
│   │   ├── runtime.py           # Tool-calling runtime
│   │   ├── runtime_types.py     # Runtime trace and coordinator summaries
│   │   └── types.py             # Agent, task, and session models
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
│       ├── enzyme-kinetics-screener/
│       ├── enzyme-kinetics-content-tagger/
│       ├── enzyme-kinetics-table-extractor/
│       ├── enzyme-kinetics-figure-extractor/
│       ├── enzyme-kinetics-text-extractor/
│       ├── enzyme-variant-normalizer/
│       ├── enzyme-extraction-summary/
│       └── vision-image-analyzer/
│           ├── vision-image-analyzer.md
│           └── evals/
├── config/                      # Configuration
│   └── plans/                   # Coordinator-driven plans (one .md per plan_id)
├── scripts/
│   └── run_kinetics_extraction.py   # Per-item kinetics driver (Step 3)
├── tests/                       # Test suite (mirrors gptase/ tree)
│   ├── conftest.py              # Shared fixtures (framework_config, sample_image_*)
│   ├── utils/ models/ memory/   # L0 — leaf data types
│   ├── tools/ agents/           # L1/L2 — internals + agent runtime
│   ├── core/ evals/ web/ cli/   # L3 — top-level + user-facing
│   └── integration/             # Cross-module wiring smoke tests
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

Set your API keys via environment variables or a local `.env` file. Do
not put real keys in tracked JSON templates:

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

# Plan workflow execution (Coordinator-driven)
gptase chat -p my_pipeline -i data/paper.md -o output/

# Enzyme kinetics extraction across the paper corpus (Python driver, not a plan)
python scripts/run_kinetics_extraction.py --enable-figures --enable-text

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

## Enzyme Kinetics Pipeline

A multi-step pipeline tuned for harvesting Michaelis-Menten parameters
(kcat, Km, kcat/Km, Tm) and full-length variant sequences from a corpus
of designed-enzyme papers. The pipeline is driven by
`scripts/run_kinetics_extraction.py`, not a Coordinator plan.

### The Workflow

1. **enzyme-kinetics-screener** — TRUE/FALSE per paper on whether
   measured kinetic data is present.
2. **enzyme-kinetics-content-tagger** — tags each section / table /
   figure in the paper's MinerU outline as relevant or not (also tags
   protein-sequence sections so they reach the text extractor).
3. **enzyme-kinetics-table-extractor** — per-table LLM call on each TRUE
   table, emits canonical `reactions[]` + `protein_sequences[]`.
4. **enzyme-kinetics-figure-extractor** — per-figure vision call; emits
   the same canonical schema plus a `figure_kind` taxonomy.
5. **enzyme-kinetics-text-extractor** — per-section LLM call with a
   literal-substring validator that drops hallucinated rows.
6. **enzyme-variant-normalizer** — deterministic reconciliation across
   sources, plus vision-confirmed footnote-letter dedup
   (HG3.3bh → HG3.3b when the figure displays only HG3.3b).

### Running the Pipeline

```bash
# Full corpus, all three extractors
python scripts/run_kinetics_extraction.py --enable-figures --enable-text

# Single paper canary
python scripts/run_kinetics_extraction.py --only blomberg_2013_precision_kemp_eliminase \
    --enable-figures --enable-text

# Force re-LLM, ignore per-call artifact cache
python scripts/run_kinetics_extraction.py --force --enable-figures --enable-text
```

Output: `papers/extractions/<paper>/kinetics.json` per paper carrying
`raw_extractions`, `normalized.normalized_variants`,
`paper_sequences`, `vision_dedup_audit`, and
`unresolved_footnote_candidates`.

### Plan Features

- **YAML Format**: Readable, supports comments
- **Parallel Execution**: Automatic parallelization of independent tasks
- **Template Variables**: `{{input_text}}`, `{{task1.field.nested}}`
- **Workspace Management**: Unified `workspace_dir` automatically maps agents to the input document's directory
- **Failure Recovery**: AI-driven abort/skip/retry decisions
- **Checkpointing**: Resume long-running plans from failure points
- **Drop-in additions**: Drop a new `<plan_id>.md` under `config/plans/` and `gptase chat -p <plan_id>` picks it up — no code changes

### Writing a New Plan

Create `config/plans/<plan_id>.md` — a plain markdown prompt with
`{{document_path}}` / `{{workspace_dir}}` placeholders. The CLI reads
it, substitutes the template variables, and feeds it to the
Coordinator as the session's opening message.

```markdown
Goal: My Pipeline

Document: {{document_path}}
Workspace: {{workspace_dir}}

Execute these steps IN ORDER, using DelegateTask to invoke each agent.

Step 1 — DelegateTask(agent_id="document-structure-analyzer", ...)
Step 2 — Two parallel DelegateTask calls in one assistant message
Step 3 — DelegateTask(agent_id="my-summarizer", ...) passing the
         upstream output_path strings.
```

See [CLAUDE.md#adding-a-new-plan](CLAUDE.md#adding-a-new-plan) for
the full template guide.

### Behind the Scenes

- **Agent Initialization**: The orchestrator loads agent definitions from `.claude/agents/`
- **Dispatch-Collect Pattern**: Tasks dispatched to agents, results collected and aggregated
- **Data Flow**: Output from each task automatically flows to the next via template variables

## Advanced Orchestration

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
- **Layout**: `tests/` mirrors the `gptase/` package tree — one `tests/<pkg>/test_<module>.py` per source file. Cross-module wiring lives in `tests/integration/`.
- **Agent-co-located tests**: domain-pure code under `.claude/agents/<agent>/` ships its tests at `.claude/agents/<agent>/tests/` (currently `enzyme-variant-normalizer/`).
- **Async Mode**: `asyncio_mode = "auto"`. **No** `@pytest.mark.asyncio` needed.
- **Structure**: Tests must be inside `class Test...`.

```bash
# Run the full suite — pyproject testpaths covers tests/ + agent-co-located
pytest -v

# With coverage
pytest -v --cov=gptase --cov-report=term-missing

# Run a single module's tests (mirrors gptase/<pkg>/<module>.py)
pytest tests/core/test_orchestrator.py -v
pytest tests/evals/ -v

# Integration smoke tests only
pytest tests/integration/ -v
```

## License

CC BY-NC 4.0 License. See [LICENSE](LICENSE) for details.
