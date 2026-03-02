# GPTase - Multi-Agent Framework

A comprehensive, elegant framework for building and managing AI agent systems with support for multiple LLM providers, multimodal messages, code execution, and AI-native Standard Operating Procedures (SOP).

## Features

### Multi-Agent System (AI-Native)
- **Markdown-Driven Agents** - Define persona, prompt, and tools via `.md` files
- **SOP Orchestration** - Execute complex workflows defined in JSON production lines
- **Executor Engine** - Unified runtime for both dynamic plans and static SOPs
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
│   ├── models/                  # LLM management
│   │   ├── model.py             # Model manager with agent-specific configs
│   │   ├── providers.py         # OpenAI provider with streaming
│   │   └── types.py             # ModelConfig, TextContent, ImageUrlContent
│   ├── core/                    # Config, constants, logging, exceptions, paths
│   ├── memory/                  # SQLite-based storage (manager, storage, models, types)
│   ├── main.py                  # CLI entry point
│   └── utils.py                 # Utility functions
├── config/                      # Configuration
│   ├── agents/                  # Agent Markdown definitions
│   │   ├── planner.md
│   │   ├── executor.md
│   │   ├── document_structure_analyzer.md
│   │   ├── enzyme_kinetics_extractor.md
│   │   ├── enzyme_design_extractor.md
│   │   ├── enzyme_extraction_summary.md
│   │   ├── vision_image_analyzer.md
│   │   └── vision_image_analyzer_react.md
│   └── sops/                    # Standard Operating Procedures
│       └── enzyme_extraction_pipeline.json
├── tests/                       # Comprehensive test suite
│   ├── test_agent_multimodal.py # Multimodal Agent tests
│   ├── test_models.py           # Model and multimodal type tests
│   └── test_agents/             # Agent-specific tests
└── examples/                    # Usage examples
    ├── vision_image_analyzer.py # Multimodal image analysis
    ├── reaction_extractor.py    # Enzyme extraction
    └── chat_demo.py             # Chat with thinking mode
```

## Quick Start

### Installation

```bash
git clone https://github.com/l1zp/GPTase.git
cd GPTase
pip install -e .
```

### Configuration

Set your API key in `config/llm_config.template.json` or via environment:

```bash
export API_KEY="your-api-key-here"
```

### Basic Usage

```bash
# Enzyme extraction from paper
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

Defined in `config/sops/enzyme_extraction_pipeline.json`:

1. **document_structure_analyzer**: Physical scan to locate relevant tables
2. **enzyme_kinetics_extractor**: Expert LLM extraction from scanned segments
3. **enzyme_extraction_summary**: Statistical synthesis and ranking

### Running the Pipeline

```bash
python examples/reaction_extractor.py -i data/listov2025.md
```

### Behind the Scenes

- **Agent Initialization**: The orchestrator loads Markdown configs from `config/agents/`
- **Tool Execution**: Specialized tools perform heavy-duty parsing before the LLM processes
- **Data Flow**: Output from each step automatically flows to the next via `{{stepN.path}}` syntax

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

Simply create a Markdown file in `config/agents/`:

```markdown
<!--
@agent_id: my_expert
@capabilities: data_analysis
@requires_model: true
@model_role: analysis
@temperature: 0.0
-->

## Agent Description
A specialized expert for data analysis tasks.

## System Prompt
You are a specialized expert in data analysis...

## Task Processing
1. Parse the input data
2. Apply analysis algorithms
3. Generate structured output

## Output Format
Return results in JSON format with the following schema:
{
  "analysis": "string",
  "metrics": {"accuracy": "number"},
  "recommendations": ["string"]
}

## Examples
Input: {...}
Output: {...}
```

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
