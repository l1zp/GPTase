# GPTase Examples

This directory contains example scripts demonstrating various features of the GPTase framework.

## Directory Structure

```
examples/
├── chat_demo.py                      # Chat interface with thinking mode
├── claude_agent_sdk_demo.py          # Claude Agent SDK demo (requires standalone terminal)
├── gemini_demo.py                    # Gemini API integration demo
├── gptase_agent_demo.py              # GPTase Agent unified interface demo
├── gptase_file_explorer_demo.py      # File explorer agent with workspace support
├── reaction_extractor.py             # Enzyme reaction extraction (harness + draft plan)
├── vision_image_analyzer.py          # Scientific figure analysis
└── file-explorer.md                  # Agent definition for file explorer demo
```

## Quick Start

### 1. Chat Interface (`chat_demo.py`)

```bash
# Interactive streaming chat
python examples/chat_demo.py

# Non-streaming mode
python examples/chat_demo.py --simple

# Disable thinking mode
python examples/chat_demo.py --no-thinking
```

Demonstrates the chat interface with streaming responses and thinking mode.

### 2. GPTase Agent Demo (`gptase_agent_demo.py`)

```bash
python examples/gptase_agent_demo.py --prompt "What is 2+2?"
```

Demonstrates the unified Agent interface that works with multiple LLM providers.

### 3. File Explorer Agent (`gptase_file_explorer_demo.py`)

```bash
# Default prompt
python examples/gptase_file_explorer_demo.py

# Custom prompt
python examples/gptase_file_explorer_demo.py --prompt "List all Python files"

# With workspace directory
python examples/gptase_file_explorer_demo.py --workspace ./gptase/core

# Debug mode
python examples/gptase_file_explorer_demo.py --debug
```

Demonstrates markdown-defined agents with workspace support for file operations.

### 4. Vision Analysis (`vision_image_analyzer.py`)

```bash
# Analyze specific images
python examples/vision_image_analyzer.py path/to/image.jpg

# Multiple images
python examples/vision_image_analyzer.py image1.jpg image2.png

# Use different agent
python examples/vision_image_analyzer.py image.jpg --agent vision_image_analyzer_react
```

Analyzes scientific figures and extracts tabular data using vision models.

**Options:**
- `--config, -c`: Path to LLM config file
- `--agent, -a`: Agent to use (`vision_image_analyzer` or `vision_image_analyzer_react`)

### 5. Reaction Extraction (`reaction_extractor.py`)

```bash
# List available predefined plans
python examples/reaction_extractor.py --list-plans

# Extract enzyme kinetics data
python examples/reaction_extractor.py -i data/paper.md -o output/

# Use specific draft plan
python examples/reaction_extractor.py -i data/paper.md -p enzyme_extraction_pipeline
```

Extracts enzyme kinetics data from scientific literature using a predefined draft plan through the orchestrator harness.

**Options:**
- `-i, --input`: Input markdown file path
- `-o, --output`: Output directory
- `-p, --plan`: Draft plan ID to execute
- `--list-plans`: List available predefined plans
- `--debug`: Enable debug logging

### 6. Claude Agent SDK Demo (`claude_agent_sdk_demo.py`)

```bash
# Run in a standalone terminal (not inside Claude Code session)
python examples/claude_agent_sdk_demo.py --prompt "List files in current directory"
```

Demonstrates Claude Agent SDK integration with tool restrictions.

**Note:** Cannot be run inside another Claude Code session. Run in a standalone terminal.

### 7. Gemini Demo (`gemini_demo.py`)

```bash
# Set API key via environment
export GEMINI_API_KEY="your-api-key"
python examples/gemini_demo.py

# Or via command line
python examples/gemini_demo.py --api-key "your-api-key"

# Or use config file
python examples/gemini_demo.py --config config/llm_config.gemini.json
```

Demonstrates Gemini API integration.

---

## Requirements Summary

| Example | Requirements |
|---------|-------------|
| `chat_demo.py` | None (uses default config) |
| `gptase_agent_demo.py` | None (uses default config) |
| `gptase_file_explorer_demo.py` | None (uses default config) |
| `vision_image_analyzer.py` | Image file path(s) |
| `reaction_extractor.py` | Input markdown file |
| `claude_agent_sdk_demo.py` | Standalone terminal (not in Claude Code) |
| `gemini_demo.py` | `GEMINI_API_KEY` environment variable |

---

## Usage Tips

### Running Examples

Most examples require the environment to be properly set up:

```bash
# Activate conda environment
conda activate llm

# Install in development mode
pip install -e .

# Run example
python examples/chat_demo.py
```

### Common Options

Many examples support command-line arguments:

```bash
# Get help
python examples/reaction_extractor.py --help

# Enable debug logging
python examples/gptase_file_explorer_demo.py --debug
```

---

## Learning Path

Recommended order for exploring examples:

1. **Start simple**: `chat_demo.py` - Basic chat interface
2. **Agent basics**: `gptase_agent_demo.py` - Unified Agent interface
3. **File operations**: `gptase_file_explorer_demo.py` - Workspace and tools
4. **Vision**: `vision_image_analyzer.py` - Image analysis
5. **Harness workflows**: `reaction_extractor.py` - Pipeline execution from a draft plan
6. **Harness Planning**: Use `AgentOrchestrator.execute_task(...)` with `auto_execute=False` to review a draft plan before execution
7. **Provider demos**: `gemini_demo.py`, `claude_agent_sdk_demo.py` - Specific providers

---

## Troubleshooting

### Import Errors

```
ImportError: No module named 'gptase'
```

**Solution**: Install the package:
```bash
pip install -e .
```

### API Key Issues

```
Error: API key not found
```

**Solution**: Set the appropriate environment variable or configure in `config/llm_config.template.json`.

### Claude Agent SDK Nested Session Error

```
Error: Claude Code cannot be launched inside another Claude Code session.
```

**Solution**: Run `claude_agent_sdk_demo.py` in a standalone terminal, not inside Claude Code.

### Missing Dependencies

```
ModuleNotFoundError: No module named 'xxx'
```

**Solution**: Install missing dependencies:
```bash
pip install -e .  # Reinstall to ensure all dependencies
```

---

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Project overview and development guidelines
- [docs/architecture.md](../docs/architecture.md) - Architecture documentation

---

## Contributing

When adding new examples:

1. **Follow naming convention**: Use descriptive names with `_demo.py` suffix for demos
2. **Add docstrings**: Explain what the example does at the top of the file
3. **Include usage comments**: Show how to run and customize
4. **Update this README**: Add description of the new example
5. **Test the example**: Ensure it runs without errors
