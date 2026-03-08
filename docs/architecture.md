# Architecture Overview

## Agent-Tool Delegation Pattern

GPTase uses a **delegation pattern** that separates configuration from business logic:

```
Agent Definition (.claude/agents/*.md)
    ↓ parsed by
AgentParser (YAML frontmatter)
    ↓ creates
MarkdownAgent (generic runtime)
    ↓ delegates to
Agent (unified execution with multimodal support)
    ↓ calls
Model (LLM with vision support)
```

### Agent Layer — Zero-Code Configuration

Agents are defined as Markdown files with **YAML frontmatter**. No Python code required.

```markdown
---
name: my-agent
description: What this agent does
tools: Read, Grep, Bash
model: sonnet
color: blue
---

You are a specialized expert...

## Workflow
1. Parse the input data
2. Apply analysis algorithms
3. Generate structured output

## Output Guidance
Return results in JSON format...
```

The `AgentOrchestrator` automatically discovers agents in `.claude/agents/`.

### Agent Format (Claude Code Style)

Agents use YAML frontmatter with markdown body:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique agent identifier |
| `description` | Yes | What the agent does (used for triggering) |
| `tools` | No | Comma-separated tool list (Read, Grep, Bash, Glob) |
| `model` | No | Model to use: opus, sonnet (default), haiku |
| `color` | No | Display color for UI |

### Multimodal Support

The agent system supports multimodal messages (text + images):

```python
from gptase.agents.agent import Agent
from gptase.models.model import Model

model = Model()
model_config = model.get_config_for_agent("vision-image-analyzer")

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

## Project Structure

```
gptase/                          # Source code
├── agents/                      # Agent implementations
│   ├── agent.py                 # Unified Agent with multimodal support
│   ├── loader.py                # Agent loading & factory
│   └── orchestrator.py          # Agent orchestration
├── sop/                         # SOP execution system
│   ├── types.py                 # Pydantic models (SOPStep, SOPDefinition, etc.)
│   ├── loader.py                # YAML/JSON SOP loading
│   ├── dispatcher.py            # Task dispatch and result collection
│   ├── failure_handler.py       # AI-driven failure recovery
│   └── orchestrator_agent.py    # Unified SOP orchestrator
├── models/                      # LLM management
│   ├── model.py                 # Model manager with agent-specific configs
│   ├── providers.py             # Provider implementations
│   └── types.py                 # Multimodal types
├── memory/                      # SQLite-based storage
├── core/                        # Configuration, constants, logging
└── utils.py                     # Utility functions
config/
├── llm_config.*.json            # Model configuration templates
└── sops/                        # Standard Operating Procedures (YAML/JSON workflows)
.claude/
└── agents/                      # Claude Code Agent definitions (*.md)
```

## LLM Integration

- **Unified Provider Interface** - Support for OpenAI-compatible endpoints (including custom base URLs)
- **Thinking Mode** - Native support for reasoning-enabled models (e.g., Qwen3, GPT-4)
- **Multimodal Messages** - Vision support with `TextContent` and `ImageUrlContent` types
- **Specialized Roles** - Optimized configurations for Extraction, Analysis, Planning

## Tools Architecture

- **Consolidated Tool System** - Unified base classes with timeout handling and error management
- **Document Processing** - PDF/HTML/Text loading from files or URLs (including MinerU integration)
- **Vision Analysis** - Scientific figure analysis with CSV data extraction
- **System Tools** - Code writing, execution, and file management
- **External Databases** - PDB, Rhea, KEGG, Expasy, UniProt, PubChem lookup tools
- **Biochemical Analysis** - Enzyme kinetics, design methodology extraction, and summary generation
