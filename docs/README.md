# GPTase Documentation

This directory contains detailed documentation for the GPTase project.

## Quick Links

### Core Documentation
- **[Main README](../README.md)** — Project overview, features, and getting started
- **[CLAUDE.md](../CLAUDE.md)** — Project instructions and architecture guide

### Architecture & Design
- **[Architecture Overview](./architecture.md)** — Delegation pattern, Planner workflow, SOP system

### Feature Documentation
- **[Enzyme Extraction](./features/enzyme_extraction.md)** — Enzyme reaction extraction pipeline
- **[CSV Export](./features/csv_export_guide.md)** — CSV export guide for extraction results

### Tool Documentation
- **[Vision Image Analyzer](./tools/vision_image_analyzer.md)** — Vision-based scientific figure analysis
- **[PDB Features](./tools/pdb_features.md)** — PDB ID extraction, novelty classification, and EC lookup

### Development & Deployment
- **[Testing Guide](./testing.md)** — Testing strategies and requirements
- **[Development Guide](./DEVELOPMENT_GUIDE.md)** — Code style, formatting, pre-commit setup
- **[Remote MCP Guide](./remote_mcp_guide.md)** — Remote MCP tool server deployment

## Documentation Structure

```
docs/
├── README.md                    # This file
├── architecture.md              # Architecture overview
├── testing.md                   # Testing guide
├── DEVELOPMENT_GUIDE.md         # Code style & workflow
├── remote_mcp_guide.md          # Remote MCP deployment
├── features/
│   ├── enzyme_extraction.md     # Enzyme extraction pipeline
│   └── csv_export_guide.md      # CSV export pipeline
└── tools/
    ├── vision_image_analyzer.md # Vision figure analysis
    └── pdb_features.md          # PDB handling & EC lookup
```

## Quick Reference

### For Users

```bash
# Extract enzyme reactions
python examples/reaction_extractor.py -i data/paper.md

# Generate CSV files
python pipelines/json_to_csv.py -i data/extraction/output.json

# View sessions
streamlit run src/webui/app.py
```

### For Developers

```bash
# Run tests
pytest tests/ -v

# Format code
pre-commit run --all-files

# Type check
mypy src/ --ignore-missing-imports
```

---

**Last Updated**: 2026-03-01
**Maintainer**: GPTase Development Team
