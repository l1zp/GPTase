# GPTase - Multi-Agent Framework

A comprehensive, elegant framework for building and managing AI agent systems with support for multiple LLM providers, multimodal messages, code execution, and AI-native Standard Operating Procedures (SOP).

## Features

### Multi-Agent System (AI-Native)
- **Markdown-Driven Agents** - Define persona, prompt, and tools via `.md` files
- **SOP Orchestration** - Execute complex workflows defined in YAML/JSON with parallel execution
- **Unified Orchestrator Agent** - Single agent drives all SOP execution with dispatch-collect pattern
- **AI-Driven Failure Recovery** - Intelligent abort/skip/retry decisions on step failures
- **Variable Data Flow** - Seamless data passing between agents using `{{stepN.path}}` syntax
- **5-Phase Planning** - Interactive planning system for complex workflow orchestration
- **Multimodal Support** - Vision agents with automatic image encoding and analysis

### LLM Integration
- **Unified Provider Interface** - Support for OpenAI-compatible endpoints (including custom base URLs)
- **Thinking Mode** - Native support for reasoning-enabled models (e.g., Qwen3, GPT-4o)
- **Multimodal Messages** - Vision support with `TextContent` and `ImageUrlContent` types
- **Specialized Roles** - Optimized configurations for Extraction, Analysis, and Planning

### Tools Architecture
- **Consolidated Tool System** - Unified base classes with timeout handling and error management
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
│   │   └── orchestrator.py      # Agent orchestration
│   ├── sop/                     # SOP execution system
│   │   ├── types.py             # Pydantic models (SOPStep, SOPDefinition, etc.)
│   │   ├── loader.py            # YAML/JSON SOP loading
│   │   ├── dispatcher.py        # Task dispatch and result collection
│   │   ├── failure_handler.py   # AI-driven failure recovery
│   │   └── orchestrator_agent.py # Unified SOP orchestrator
│   ├── models/                  # LLM management
│   │   ├── model.py             # Model manager with agent-specific configs
│   │   ├── providers.py         # OpenAI provider with streaming
│   │   └── types.py             # ModelConfig, TextContent, ImageUrlContent
│   ├── core/                    # Config, constants, logging, exceptions, paths
│   ├── memory/                  # SQLite-based storage (manager, storage, models, types)
│   ├── main.py                  # CLI entry point
│   └── utils.py                 # Utility functions
├── .claude/                     # Claude Code integration
│   └── agents/                  # Agent definitions (Claude Code format)
│       ├── planner.md
│       ├── executor.md
│       ├── document-structure-analyzer.md
│       ├── enzyme-kinetics-extractor.md
│       ├── enzyme-design-extractor.md
│       ├── enzyme-extraction-summary.md
│       ├── vision-image-analyzer.md
│       └── vision-image-analyzer-react.md
├── config/                      # Configuration
│   └── sops/                    # Standard Operating Procedures (YAML/JSON)
│       └── enzyme_extraction_pipeline.yaml
├── tests/                       # Comprehensive test suite
│   ├── test_sop.py              # SOP system tests
│   ├── test_agent_multimodal.py # Multimodal Agent tests
│   ├── test_models.py           # Model and multimodal type tests
│   └── test_agents/             # Agent-specific tests
└── examples/                    # Usage examples
    ├── vision_image_analyzer.py # Multimodal image analysis
    ├── reaction_extractor.py    # Enzyme extraction (SOP mode)
    └── chat_demo.py             # Chat with thinking mode
```

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
export API_KEY="your-api-key-here"
```

### Basic Usage

```bash
# List available agents
gptase list

# Run a task
gptase run -d "Analyze this document"

# SOP workflow execution
gptase sop --list                           # List available SOPs
gptase sop -p enzyme_extraction_pipeline -i data/paper.md -o output/

# Enzyme extraction from paper (example script)
python examples/reaction_extractor.py -i data/paper.md

# Multimodal image analysis
python examples/vision_image_analyzer.py path/to/image.png

# Chat with thinking mode
python examples/chat_demo.py
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
result = await agent.run_with_images(
    task="Extract tabular data from this figure",
    image_paths=["figure.png"],
)
```

## Standard Enzyme Extraction SOP

The framework provides an industrial-grade pipeline for enzyme data processing.

### The Workflow (SOP)

Defined in `config/sops/enzyme_extraction_pipeline.yaml`:

1. **document_structure_analyzer**: Physical scan to locate relevant tables
2. **enzyme_kinetics_extractor** (parallel with vision): Expert LLM extraction from text
3. **vision_image_analyzer**: Extract data from figures using vision models
4. **enzyme_extraction_summary**: Statistical synthesis and ranking

### Running the Pipeline

```bash
# Via CLI
gptase sop -p enzyme_extraction_pipeline -i data/paper.md -o output/

# List available SOPs
gptase sop --list

# Via Python
python examples/reaction_extractor.py -i data/paper.md
```

### SOP Features

- **YAML Format**: Readable, supports comments
- **Parallel Execution**: Steps in `parallel:` block run concurrently
- **Template Variables**: `{{input_text}}`, `{{step1.field.nested}}`
- **Failure Recovery**: AI-driven abort/skip/retry decisions
- **No Code Changes**: Add new SOPs by creating YAML files

### Writing a New SOP

Create `config/sops/my_pipeline.yaml`:

```yaml
plan_id: my_pipeline
name: My Pipeline
description: What this pipeline does
version: "1.0"

workflow:
  - step_id: "1"
    agent: document_structure_analyzer
    action: analyze
    description: Analyze document structure
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

### Behind the Scenes

- **Agent Initialization**: The orchestrator loads agent definitions from `.claude/agents/`
- **Dispatch-Collect Pattern**: Tasks dispatched to agents, results collected and aggregated
- **Data Flow**: Output from each step automatically flows to the next via template variables

## Advanced Orchestration

### Dynamic Planning (5-Phase System)

For novel tasks, use the **Planner Agent** with its 5-phase workflow:

1. **Understanding** - Ask clarifying questions
2. **Design** - Create detailed implementation approach
3. **Review** - Present plan and collect feedback
4. **Final Plan** - Generate executable workflow JSON
5. **Exit** - Request final approval before execution

```python
result = await orchestrator.execute_task({
    "use_planner": True,
    "description": "Analyze this paper and compare variants against wild-type"
})
```

### Writing a New Agent

Create a Markdown file with YAML frontmatter in `.claude/agents/`:

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

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=gptase

# Run specific test categories
pytest tests/test_agent_multimodal.py -v
pytest tests/test_models.py -v
pytest tests/test_agents/ -v
```

## License

CC BY-NC 4.0 License. See [LICENSE](LICENSE) for details.
