# GPTase - Multi-Agent Framework

A comprehensive, elegant framework for building and managing AI agent systems with support for multiple LLM providers, code execution, and AI-native Standard Operating Procedures (SOP).

## Features

### Multi-Agent System (AI-Native)
- **Markdown-Driven Agents** - Define persona, prompt, and tools via `.md` files
- **SOP Orchestration** - Execute complex workflows defined in JSON production lines
- **Executor Engine** - Unified runtime for both dynamic plans and static SOPs
- **Variable Data Flow** - Seamless data passing between agents using `{{stepN.path}}` syntax
- **5-Phase Planning** - Interactive planning system for complex workflow orchestration

### LLM Integration
- **Unified Provider Interface** - Support for OpenAI, Anthropic, and custom endpoints
- **Thinking Mode** - Native support for reasoning-enabled models (e.g., Qwen-VL, GPT-4o)
- **Specialized Roles** - Optimized configurations for Extraction, Analysis, and Planning

### Tools Architecture
- **Consolidated Tool System** - Unified base classes with timeout handling and error management
- **Document Processing** - PDF/HTML/Text loading from files or URLs (including MinerU integration)
- **System Tools** - Code writing, execution, and file management
- **External Databases** - PDB, Rhea, KEGG, Expasy, PubChem lookup tools
- **Biochemical Analysis** - Enzyme kinetics, design methodology extraction, and summary generation

## Project Structure

```
gptase/
├── src/                         # Source code
│   ├── agents/                  # Agent implementations
│   │   ├── base.py              # Base agent interface
│   │   ├── markdown_agent.py    # Markdown-driven agent
│   │   ├── orchestrator.py      # Agent orchestration
│   │   └── markdown_factory.py  # Agent factory from Markdown configs
│   ├── tools/                   # General-purpose tool implementations
│   │   ├── base.py              # BaseTool, ToolResult, TrackingMixin
│   │   ├── document.py          # Document loader and MinerU tool
│   │   ├── system.py            # Code writer, executor, file manager
│   │   ├── utils.py             # Calculator and web search
│   │   ├── planner_tool.py      # 5-phase planning system
│   │   ├── executor_tool.py     # SOP/Plan execution engine
│   │   └── registry.py          # Tool registry
│   ├── mcp/                     # MCP-specific enzyme tools and databases
│   │   ├── tools/               # Enzyme-specific tools
│   │   │   ├── enzyme_kinetics_tool.py
│   │   │   ├── enzyme_design_tool.py
│   │   │   ├── vision_tool.py
│   │   │   └── document_structure_tool.py
│   │   ├── databases/           # External database lookup tools
│   │   │   ├── base.py          # Base class for external DB tools
│   │   │   ├── pdb.py           # PDB -> EC number lookup
│   │   │   ├── rhea.py          # Rhea reaction database
│   │   │   ├── kegg.py          # KEGG pathway database
│   │   │   ├── expasy.py        # Expasy enzyme database
│   │   │   └── pubchem.py       # PubChem SMILES lookup
│   │   ├── server.py            # MCP server
│   │   └── tools.py             # MCP tools integration
│   ├── models/                  # LLM management
│   ├── core/                    # Config and base interfaces
│   ├── memory/                  # Persistent storage
│   ├── conversations/           # SQLite-based tracking
│   └── webui/                   # Streamlit interface
├── config/                      # Configuration
│   ├── agents/                  # Agent Markdown definitions
│   │   ├── planner.md
│   │   ├── executor.md
│   │   ├── document_structure_analyzer.md
│   │   ├── enzyme_kinetics_extractor.md
│   │   ├── enzyme_design_extractor.md
│   │   ├── enzyme_extraction_summary.md
│   │   └── vision_image_analyzer.md
│   └── sops/                    # Standard Operating Procedures
│       └── enzyme_extraction_pipeline.json
├── tests/                       # Comprehensive test suite
└── examples/                    # Usage examples
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

### Adding a New Tool

Create a class inheriting from `BaseTool`:

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
        # Tool implementation here
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

Then register it in the orchestrator.

## External Database Tools

The framework includes tools for querying biochemical databases:

- **PDB Lookup** (`pdb_ec_lookup`): Convert PDB IDs to EC numbers
- **Rhea Database** (`rhea_lookup`): Query biochemical reactions
- **KEGG Pathway** (`kegg_lookup`): Retrieve pathway information
- **Expasy** (`expasy_lookup`): Enzyme nomenclature and information
- **PubChem** (`pubchem_smiles_lookup`): Get SMILES notation for compounds

Example usage:

```python
from src.tools.external_databases.pdb import PdbEcLookupTool

tool = PdbEcLookupTool()
result = await tool.execute(pdb_id="1ABC")
# Returns: {"pdb_id": "1ABC", "ec_numbers": ["1.1.1.1", ...]}
```

## Testing

```bash
# Run all tests
pytest tests/ -v --cov=src

# Run specific tool tests
pytest tests/test_tools/ -v

# Quick check (no coverage)
pytest tests/test_tools/ -v
```

## License

CC BY-NC 4.0 License. See [LICENSE](LICENSE) for details.
