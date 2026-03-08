# GPTase Documentation

This directory contains detailed documentation for the GPTase project.

## Quick Links

### Core Documentation
- **[Main README](../README.md)** — Project overview, features, and getting started
- **[CLAUDE.md](../CLAUDE.md)** — Project instructions and architecture guide

### Architecture & Design
- **[Architecture Overview](./architecture.md)** — Delegation pattern, multimodal support, Planner workflow, SOP system

### Feature Documentation
- **[Enzyme Extraction](./features/enzyme_extraction.md)** — Enzyme reaction extraction pipeline

### Tool Documentation
- **[Vision Image Analyzer](./tools/vision-image-analyzer.md)** — Multimodal scientific figure analysis with vision models

### Setup & Development
- **[Environment Setup](./environment_setup.md)** — Complete environment configuration guide
- **[Development Guide](./DEVELOPMENT_GUIDE.md)** — Code style, formatting, pre-commit setup

## Documentation Structure

```
docs/
├── README.md                    # This file
├── architecture.md              # Architecture overview (including multimodal support)
├── environment_setup.md         # Environment configuration guide
├── DEVELOPMENT_GUIDE.md         # Code style & workflow
├── features/
│   └── enzyme_extraction.md     # Enzyme extraction pipeline
└── tools/
    └── vision-image-analyzer.md # Multimodal vision analysis
```

## Quick Reference

### For Users

```bash
# List available agents
gptase list

# Run a task
gptase run -d "Analyze this document"

# SOP workflow execution
gptase sop --list                           # List available SOPs
gptase sop -p enzyme_extraction_pipeline -i data/paper.md -o output/

# Extract enzyme reactions (example script)
python examples/reaction_extractor.py -i data/paper.md

# Analyze images with vision model
python examples/vision_image_analyzer.py path/to/image.jpg

# Analyze multiple images
python examples/vision_image_analyzer.py fig1.png fig2.png --agent vision-image-analyzer
```

### For Developers

```bash
# Run tests
pytest tests/ -v

# Format code
isort --profile=google gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/

# Type check
mypy gptase/ --ignore-missing-imports
```

### Multimodal Agent Usage

```python
from gptase.agents.agent import Agent

# Create multimodal agent
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

---

**Last Updated**: 2026-03-05
**Maintainer**: GPTase Development Team
