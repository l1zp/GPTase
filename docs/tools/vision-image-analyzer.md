# Vision Image Analyzer

Multimodal image analysis tool for scientific figures using vision models.

## Overview

The Vision Image Analyzer uses the `MarkdownAgent` framework with multimodal support to analyze scientific figures and extract tabular data. It leverages agent configurations (system prompts, model settings) from markdown files and automatically handles image encoding for vision models.

## Quick Start

```bash
# Analyze default image
python examples/vision_image_analyzer.py

# Analyze specific image
python examples/vision_image_analyzer.py path/to/image.jpg

# Analyze multiple images
python examples/vision_image_analyzer.py image1.jpg image2.png

# Use ReAct agent for iterative analysis
python examples/vision_image_analyzer.py --agent vision-image-analyzer-react

# Custom configuration
python examples/vision_image_analyzer.py --config config/llm_config.custom.json
```

## Architecture

### Multimodal Agent Support

The agent system supports multimodal messages through two approaches:

```
Task with image_paths
    ↓
MarkdownAgent.process_task()
    ↓ detects images
Agent.run_with_images()
    ↓ builds multimodal message
Model.generate() with image content
```

**Key Components:**

| Component | Role |
|-----------|------|
| `MarkdownAgent` | Detects `image_path`/`image_paths` in task, routes to multimodal handler |
| `Agent.run_with_images()` | Builds multimodal message content with base64-encoded images |
| `Model.generate()` | Sends multimodal messages to vision-capable LLMs |

### Agent Configuration

Agents are defined in `.claude/agents/`:

- **vision-image-analyzer.md** - Standard analysis agent
- **vision-image-analyzer-react.md** - ReAct-style iterative analysis

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `image_path` | One or more image paths to analyze | Default sample image |
| `--agent`, `-a` | Agent to use (`vision-image-analyzer` or `vision-image-analyzer-react`) | `vision-image-analyzer` |
| `--config`, `-c` | Custom LLM config file | Uses template config |

## Usage Examples

### Basic Analysis

```bash
python examples/vision_image_analyzer.py data/listov2025/images/figure.png
```

### Multiple Images

```bash
python examples/vision_image_analyzer.py fig1.png fig2.png fig3.png
```

### Using ReAct Agent

The ReAct agent performs iterative reasoning for complex figures:

```bash
python examples/vision_image_analyzer.py complex_figure.png --agent vision-image-analyzer-react
```

### Programmatic Usage

```python
from gptase.agents.markdown_agent import MarkdownAgentFactory
from gptase.models.model import Model
from gptase.memory.manager import MemoryManager

# Initialize
model = Model()
memory = MemoryManager()
factory = MarkdownAgentFactory()

# Create agent
agent = factory.create_agent("vision-image-analyzer", memory, model_manager=model)

# Build task with images
task = {
    "description": "Extract kinetic parameters from this figure",
    "image_paths": ["path/to/figure.png"],
}

# Execute (automatically uses multimodal messages)
result = await agent.process_task(task)
```

### Direct Agent Usage

For more control, use the `Agent` class directly:

```python
from gptase.agents.agent import Agent

agent = Agent(
    system_prompt="You are a scientific figure analyst.",
    model_config=model_config,
)

# Multimodal analysis
result = await agent.run_with_images(
    task="Extract all tabular data into CSV format",
    image_paths=["figure1.png", "figure2.png"],
)
```

## Output Format

### JSON Output

Saved to `data/output/{image_name}/{timestamp}/analysis.json`:

```json
{
  "image_paths": ["path/to/image.jpg"],
  "agent": "vision_image_analyzer",
  "content": {
    "analysis_results": [
      {
        "image_number": 1,
        "content": "Description of the figure..."
      }
    ],
    "extracted_tables": [
      {
        "image_number": 1,
        "csv_data": "Variant,k_cat/K_M,Asp162_vdW\nDes27.2,21,-4.9\n..."
      }
    ],
    "key_findings": [
      "Catalytic efficiency increases across variants...",
      "Correlation between vdW and activity..."
    ]
  }
}
```

### CSV Output

Extracted tables saved to `data/output/{image_name}/{timestamp}/extracted_tables.csv`:

```csv
# Image: path/to/image.jpg
# Agent: vision-image-analyzer

# Table 1
Variant,k_cat/K_M,Asp162_vdW
Des27.2,21,-4.9
Des27.5,54,-4.9
Des27.7,12696,-5.4
```

## Configuration

### Agent-Specific Model Config

Configure vision models in `config/llm_config.template.json`:

```json
{
  "agent_models": {
    "vision-image-analyzer": {
      "model_name": "Qwen3-VL-30B-A3B-Thinking",
      "api_key": "your-api-key",
      "base_url": "https://api.example.com/v1/",
      "temperature": 0.1,
      "max_tokens": 4096
    },
    "vision-image-analyzer-react": {
      "model_name": "Qwen3-VL-30B-A3B-Thinking",
      "temperature": 0.3,
      "max_tokens": 8192
    }
  }
}
```

### Agent Definition

Example from `.claude/agents/vision-image-analyzer.md`:

```markdown
---
name: vision-image-analyzer
description: Analyzes scientific figures to extract tabular data and key findings
tools: Read
model: sonnet
---

You are the world-class Vision Analysis Expert. Your goal is to extract
every piece of data from the provided scientific figures.

## Strategy
1. Multi-modal Analysis: Use vision capability to interpret images.
2. Data Extraction: Prioritize extracting tabular data into CSV format.
3. Relevance: Focus on enzyme variants and kinetic parameters.

## Output Guidance
Return JSON with analysis_results, extracted_tables, and key_findings.
```

## Supported Image Formats

| Format | MIME Type | Notes |
|--------|-----------|-------|
| JPEG | `image/jpeg` | Recommended for photos |
| PNG | `image/png` | Recommended for diagrams |
| GIF | `image/gif` | First frame only |
| WebP | `image/webp` | Modern format support |

## Performance

### Processing Time

| Figure Type | Typical Time |
|-------------|--------------|
| Simple table | 30-60 seconds |
| Complex multi-panel | 2-3 minutes |
| ReAct iterative | 3-5 minutes |

### Token Usage

Vision models consume tokens for:
- Image encoding (~1000 tokens base)
- System prompt
- Response generation

## Troubleshooting

### Image Not Found

```bash
[ERROR] Image file not found: path/to/image.jpg
```

**Solution**: Verify the image path exists and is accessible.

### Model Not Configured

```bash
[ERROR] Analysis failed: No model config for agent
```

**Solution**: Add agent-specific config in `config/llm_config.template.json` under `agent_models`.

### Poor Extraction Quality

**Solutions**:
1. Use higher resolution images (1024x1024 minimum)
2. Try the ReAct agent for complex figures
3. Customize the agent's system prompt

## Related Documentation

- [Architecture Overview](../architecture.md) - Agent system architecture
- [CLAUDE.md](../../CLAUDE.md) - Project documentation
- [examples/vision_image_analyzer.py](../../examples/vision_image_analyzer.py) - Implementation
