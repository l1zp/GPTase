# 🚀 GPTase - Multi-Agent Framework

A comprehensive, elegant framework for building and managing AI agent systems with support for multiple LLM providers, code execution, memory management, and specialized biochemical analysis tools.

## ✨ Features

### 🤖 Multi-Agent System
- **Planner Agent** - Task decomposition and planning
- **Executor Agent** - Task implementation and execution
- **Tool Manager** - Resource and tool management
- **Memory Manager** - Persistent memory and learning
- **Specialized Agents** - Enzyme design, literature analysis, and more

### 🧠 LLM Integration
- **OpenAI GPT** - GPT-3.5, GPT-4, GPT-4 Turbo
- **Anthropic Claude** - Claude 3 series
- **Custom Models** - Support for custom API endpoints
- **Flexible Configuration** - Role-based model selection
- **Template-based Config** - Environment variable support

### 🔧 Code Execution
- **Python Executor** - Safe Python code execution
- **Shell Executor** - System command execution
- **Docker Executor** - Containerized execution
- **Sandbox Executor** - Secure sandboxed execution

## 🏗️ Project Structure

```
gptase/
├── src/                    # Source code
│   ├── core/              # Core framework and configuration
│   ├── agents/            # Agent implementations
│   │   └── specialized/   # Specialized agent types
│   ├── models/            # LLM management
│   ├── executors/         # Code execution engines
│   ├── memory/            # Memory management
│   └── tools/             # Tool registry and implementations
├── tests/                 # Test suite
├── examples/              # Usage examples
├── data/                  # Sample data files
├── config/                # Configuration templates
├── scripts/               # Utility scripts
└── requirements/          # Dependencies
```

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/l1zp/GPTase.git
cd GPTase

# Install dependencies
pip install -r requirements.txt

# Optional: install as editable package
pip install -e .
```

### Configuration

Configure your LLM settings in `config/llm_config.template.json`:

```json
{
  "model_name": "Kimi-K2",
  "api_key": "${API_KEY}",
  "temperature": 0.7,
  "max_tokens": 10240,
  "base_url": "https://your-api-endpoint.com"
}
```

**API Key Resolution:**

The framework automatically resolves API keys in this order:
1. Value in `config/llm_config.template.json` (if not a placeholder)
2. Environment variable `API_KEY`
3. Environment variable `OPENAI_API_KEY`
4. Environment variable `GPTASE_OPENAI_API_KEY`

Set your API key via environment:

```bash
export API_KEY="your-api-key-here"
```

### Basic Usage

#### Simple Chat Example

```python
import asyncio
from src.utils import default_manager
from src.models.types import ModelRole

async def main():
    # Initialize manager with default config
    manager = default_manager()

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say hello and tell me a fun fact."},
    ]

    response = await manager.generate(messages, role=ModelRole.GENERAL)
    print(response.content)

asyncio.run(main())
```

Run the example:

```bash
python examples/chat_demo.py
```

## 🧪 Enzyme Reaction Extraction

The framework includes a specialized agent for extracting enzyme reaction data from scientific literature. This powerful feature demonstrates the full capabilities of the multi-agent system for biochemical analysis.

### Overview

The `LLMEnzymeExtractorAgent` uses Large Language Models to parse academic-style biochemical documents and extract structured reaction data including:

- **Enzyme Information** - Names, isoforms, and classifications
- **Reaction Components** - Substrates and products
- **Reaction Conditions** - Temperature, pH, buffer, time
- **Kinetic Parameters** - Km, Vmax with proper units
- **Additional Data** - Yields, citations, PDB IDs

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│              Enzyme Extraction Pipeline                     │
└─────────────────────────────────────────────────────────────┘

  Step 1: Document Loading
  ┌──────────────────────────────────────────┐
  │ • Load markdown/text files               │
  │ • Track word count and token estimates   │
  │ • Prepare content for LLM processing     │
  └────────────┬─────────────────────────────┘
               │
  Step 2: LLM Processing
  ┌──────────────────────────────────────────┐
  │ • Send document to LLM with system       │
  │   prompt defining extraction schema      │
  │ • Extract structured JSON data           │
  │ • Validate against schema requirements  │
  └────────────┬─────────────────────────────┘
               │
  Step 3: Result Validation
  ┌──────────────────────────────────────────┐
  │ • Parse LLM response as JSON             │
  │ • Validate against ExtractionResult      │
  │   schema (Pydantic model)                │
  │ • Extract PDB IDs using regex            │
  └────────────┬─────────────────────────────┘
               │
  Step 4: Output Generation
  ┌──────────────────────────────────────────┐
  │ • Save structured results to JSON        │
  │ • Include extraction metadata            │
  │ • Store in data/extraction/ directory    │
  └──────────────────────────────────────────┘
```

### Running the Demo

```bash
# Ensure API key is configured
export API_KEY="your-api-key-here"

# Run the extraction demo
python examples/reaction_extractor_demo.py
```

### Complete Workflow

The `reaction_extractor_demo.py` demonstrates the complete extraction process:

#### 1. Initialization Phase

```python
# Load default Model manager
manager = default_manager()

# Create tool registry and register document loader
tool_registry = ToolRegistry()
tool_registry.register_tools([DocumentLoaderTool()])

# Initialize memory manager
memory_manager = MemoryManager()

# Create the enzyme extraction agent
agent = LLMEnzymeExtractorAgent(
    "enzyme",
    memory_manager,
    tool_registry,
    model_manager=manager
)
```

**What happens:**
- `default_manager()` reads `config/llm_config.template.json`
- Resolves API key from environment variables
- Initializes Model with configured provider
- Sets up tool registry for document handling

#### 2. Document Processing

```python
# Process a markdown document
result = await agent.process_task({
    "document": {
        "source_type": "file",
        "path": "data/listov2025.md"
    }
})
```

**What happens:**
- DocumentLoaderTool reads the markdown file
- Content is analyzed for token count
- Document is passed to LLM with extraction prompt
- LLM extracts structured reaction data

#### 3. Result Handling

```python
if result["status"] == "success":
    extraction = result["data"].get("extraction", {})
    reactions = extraction.get("reactions", [])
    print(f"Reactions parsed: {len(reactions)}")

    # Save to JSON file
    output_file = "data/extraction/listov2025_extraction.json"
    with open(output_file, "w") as f:
        json.dump(result["data"], f, indent=2, default=str)
```

**What happens:**
- Validates extraction was successful
- Counts extracted reactions
- Saves structured JSON to output file
- Includes all metadata and pipeline info

### Expected Output Format

```json
{
  "extraction": {
    "reactions": [
      {
        "source_file": "listov2025.md",
        "enzyme_name": "ketol-acid reductoisomerase",
        "substrates": ["acetolactate", "NADPH"],
        "products": ["2,3-dihydroxy-3-isovalerate", "NADP+"],
        "conditions": {
          "temperature": "25°C",
          "pH": "7.5",
          "buffer": "Tris-HCl",
          "time": "30 min",
          "notes": "Optimal conditions"
        },
        "kinetics": {
          "Km": 0.15,
          "Km_unit": "mM",
          "Vmax": 45.2,
          "Vmax_unit": "μmol/min/mg"
        },
        "yield_percent": 85.0,
        "citations": ["DOI:10.1016/j.chembiol.2024.01.001"],
        "pdb_ids": ["1YZH", "2ABC"]
      }
    ],
    "pipeline": {
      "steps": [
        {
          "name": "llm_extract",
          "description": "LLM extraction completed",
          "status": "success"
        }
      ],
      "validations": ["Schema valid", "PDB IDs extracted"],
      "errors": []
    }
  }
}
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `LLMEnzymeExtractorAgent` | `src/agents/specialized/` | Main extraction agent |
| `DocumentLoaderTool` | `src/tools/implementations.py` | Loads document content |
| `ExtractionResult` | `src/tools/markdown_enzyme_parser.py` | Result schema validation |
| `default_manager` | `src/utils.py` | Model initialization |

### Customization

**Modify System Prompt:**

Edit the extraction prompt in `src/agents/specialized/llm_enzyme_extractor.py`:

```python
SYSTEM_PROMPT = (
    "You are an expert biochemical text parser. "
    "Extract enzyme reaction data from academic-style text..."
)
```

**Extend Schema:**

Modify `ExtractionResult` in `src/tools/markdown_enzyme_parser.py` to add new fields.

**Process Multiple Files:**

```python
data_dir = Path("data")
for md_file in data_dir.glob("*.md"):
    result = await agent.process_task({
        "document": {"source_type": "file", "path": str(md_file)}
    })
```

## 🎯 Advanced Usage

### Orchestrator Pattern

```python
import asyncio
from src.core.config import FrameworkConfig
from src.agents.orchestrator import AgentOrchestrator

async def main():
    config = FrameworkConfig(
        llm={
            "provider": "openai",
            "model": "gpt-4"
        }
    )
    orchestrator = AgentOrchestrator(config)
    result = await orchestrator.execute_task({
        "id": "demo_001",
        "description": "Create a Python script for fibonacci numbers"
    })
    print(result)
    await orchestrator.shutdown()

asyncio.run(main())
```

### Custom Agents

```python
from src.agents.base import BaseAgent

class CustomAgent(BaseAgent):
    async def execute_task(self, task):
        # Your custom logic here
        return {"status": "success", "result": "custom result"}
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/test_agents/ -v
pytest tests/test_models/ -v
pytest tests/test_executors/ -v
```

## 🔧 Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -e .[dev]
```

### Code Quality

The project uses automated code formatting and linting:

```bash
# Format code (runs automatically on commit)
isort src/ tests/ examples/
yapf --in-place --recursive src/ tests/ examples/

# Type checking
mypy src/

# Install pre-commit hooks (runs automatically on commit)
pre-commit install
```

### CI/CD

The project includes GitHub Actions workflows that:
- Check code formatting (isort, yapf)
- Run type checking (mypy)
- Execute tests across Python 3.8-3.12
- Generate coverage reports

## 📈 Performance

- **Async-first** architecture for high concurrency
- **Memory-efficient** execution with cleanup
- **Scalable** design for production workloads

## 🌍 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and formatting
5. Submit a pull request

## 📄 License

CC BY-NC 4.0 License - see [LICENSE](../LICENSE) file for details.
