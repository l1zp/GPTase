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
- **[CSV Export](./features/csv_export_guide.md)** — CSV export guide for extraction results

### Tool Documentation
- **[Vision Image Analyzer](./tools/vision_image_analyzer.md)** — Multimodal scientific figure analysis with vision models
- **[PDB Features](./tools/pdb_features.md)** — PDB ID extraction, novelty classification, and EC lookup

### Development & Deployment
- **[Testing Guide](./testing.md)** — Testing strategies and requirements
- **[Development Guide](./DEVELOPMENT_GUIDE.md)** — Code style, formatting, pre-commit setup
- **[Remote MCP Guide](./remote_mcp_guide.md)** — Remote MCP tool server deployment

## Documentation Structure

```
docs/
├── README.md                    # This file
├── architecture.md              # Architecture overview (including multimodal support)
├── testing.md                   # Testing guide
├── DEVELOPMENT_GUIDE.md         # Code style & workflow
├── remote_mcp_guide.md          # Remote MCP deployment
├── features/
│   ├── enzyme_extraction.md     # Enzyme extraction pipeline
│   └── csv_export_guide.md      # CSV export pipeline
└── tools/
    ├── vision_image_analyzer.md # Multimodal vision analysis
    └── pdb_features.md          # PDB handling & EC lookup
```

## Quick Reference

### For Users

```bash
# Extract enzyme reactions
python examples/reaction_extractor.py -i data/paper.md

# Analyze images with vision model
python examples/vision_image_analyzer.py path/to/image.jpg

# Analyze multiple images
python examples/vision_image_analyzer.py fig1.png fig2.png --agent vision_image_analyzer
```

### For Developers

```bash
# Run tests
pytest tests/ -v

# Format code
isort gptase/ tests/ examples/ && yapf --in-place --parallel --recursive gptase/ tests/ examples/

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
result = await agent.run_with_images(
    task="Extract tabular data from this figure",
    image_paths=["figure.png"],
)
```

---

**Last Updated**: 2026-03-02
**Maintainer**: GPTase Development Team
