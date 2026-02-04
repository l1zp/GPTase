# 🚀 GPTase - Multi-Agent Framework

A comprehensive, elegant framework for building and managing AI agent systems with support for multiple LLM providers, code execution, and AI-native Standard Operating Procedures (SOP).

## ✨ Features

### 🤖 Multi-Agent System (AI-Native)
- **Markdown-Driven Agents** - Define persona, prompt, and tools via `.md` files.
- **SOP Orchestration** - Execute complex workflows defined in JSON production lines.
- **Executor Engine** - Unified runtime for both dynamic plans and static SOPs.
- **Variable Data Flow** - Seamless data passing between agents using `{{stepN.path}}` syntax.

### 🧠 LLM Integration
- **Unified Provider Interface** - Support for OpenAI, Anthropic, and custom endpoints.
- **Thinking Mode** - Native support for reasoning-enabled models (e.g., Qwen-VL, GPT-4o).
- **Specialized Roles** - Optimized configurations for Extraction, Analysis, and Planning.

### 🔧 Code & Analysis Tools
- **Physical Document Scan** - Regex-based high-speed extraction of sections and tables.
- **Biochemical Post-Processing** - Automated PDB mapping and data sanitization.
- **Statistical Analysis** - Pandas-driven synthesis of kinetic parameters.

## 🏗️ Project Structure

```
gptase/
├── src/                    # Source code
│   ├── agents/            # Unified Agent implementations
│   ├── models/            # LLM management
│   ├── executors/         # Multi-engine execution (Python, Shell, Docker)
│   ├── tools/             # Specialized Tools (Extraction, Scanning, Analysis)
│   └── core/              # Config and base interfaces
├── config/                # Configuration
│   ├── agents/            # Agent Markdown definitions
│   └── sops/              # Predefined Standard Operating Procedures
├── tests/                 # Comprehensive test suite
└── examples/              # Usage examples
```

## 🚀 Quick Start

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

## 🧪 Standard Enzyme Extraction SOP

The framework provides an industrial-grade pipeline for enzyme data processing, driven by the `enzyme_extraction_pipeline` SOP.

### 1. The Workflow (SOP)
The process is defined in `config/sops/enzyme_extraction_pipeline.json`:
1. **document_structure_analyzer**: Physical scan to locate relevant tables.
2. **enzyme_kinetics_extractor**: Expert LLM extraction from scanned segments.
3. **enzyme_extraction_summary**: Statistical synthesis and ranking.

### 2. Running the Pipeline
Simply run the modernized extractor script:
```bash
python examples/reaction_extractor.py -i data/listov2025.md
```

### 3. Behind the Scenes
- **Agent Initialization**: The orchestrator loads Markdown configs from `config/agents/`.
- **Tool Execution**: Specialized tools perform heavy-duty parsing before the LLM "thinks".
- **Data Flow**: Output from the structural scan is automatically passed to the extraction agent.

## 🎯 Advanced Orchestration

### Dynamic Planning
For novel tasks, use the **Planner Agent** to generate custom plans:
```python
result = await orchestrator.execute_task({
    "use_planner": True,
    "description": "Analyze this paper and compare variants against wild-type"
})
```

### Writing a New Agent
Simply create a Markdown file in `config/agents/`:
```markdown
<!-- @agent_id: my_expert @model_role: analysis @tools: web_search -->
## System Prompt
You are a specialized expert...
```

## 🧪 Testing
```bash
# Run all core and agent tests
pytest tests/ -v
```

## 📄 License
CC BY-NC 4.0 License. See [LICENSE](LICENSE) for details.
