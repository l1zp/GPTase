# GPTase Documentation

This directory contains detailed documentation for the GPTase project.

## Quick Links

### Core Documentation
- **[Main README](../README.md)** - Project overview, features, and getting started
- **[CLAUDE.md](../CLAUDE.md)** - Project instructions and architecture guide

### Feature Documentation
- **[Enzyme Extraction](./features/enzyme_extraction.md)** - Comprehensive guide for enzyme reaction extraction pipeline
- **[Streaming & Thinking Mode](./features/streaming_thinking_mode.md)** - Real-time streaming with LLM reasoning mode
- **[CSV Export](./features/csv_export_guide.md)** - CSV export guide for extraction results

### Tool Documentation
- **[Vision Image Analyzer](./tools/vision_image_analyzer.md)** - Guide for vision-based scientific figure analysis
- **[PDB Features](./tools/pdb_features.md)** - PDB ID extraction, novelty classification, and EC number lookup

### Architecture & Design
- **[Delegation Pattern](./architecture/delegation_pattern.md)** - Agent-Tool delegation architecture pattern

### Development Guides
- **[Testing Guide](./testing.md)** - Comprehensive testing strategies and requirements
- **[Development Guide](./DEVELOPMENT_GUIDE.md)** - Code style, formatting tools, and pre-commit setup

### Web UI
- **[Theme Guide](./webui/theme_guide.md)** - Scientific Laboratory theme design reference

## Documentation Structure

```
docs/
├── README.md                    # This file - documentation navigation
├── testing.md                   # Comprehensive testing guide
├── DEVELOPMENT_GUIDE.md         # Code style & development workflow
│
├── features/                    # Feature-specific documentation
│   ├── enzyme_extraction.md     # Enzyme reaction extraction pipeline
│   ├── streaming_thinking_mode.md  # Streaming with thinking mode
│   └── csv_export_guide.md      # CSV export pipeline
│
├── tools/                       # Tool-specific documentation
│   ├── vision_image_analyzer.md # Vision-based figure analysis
│   └── pdb_features.md          # PDB handling and EC number lookup
│
├── architecture/                # Architecture and design patterns
│   └── delegation_pattern.md    # Agent-Tool delegation pattern
│
└── webui/                       # Web UI documentation
    └── theme_guide.md           # Scientific Laboratory theme
```

## Quick Reference

### For Users

**Getting Started**:
1. Read the [Main README](../README.md) for project overview
2. Follow [Enzyme Extraction](./features/enzyme_extraction.md) to extract enzyme data
3. Check [PDB Features](./tools/pdb_features.md) for PDB-specific functionality

**Common Tasks**:
- Extract enzyme reactions: `python examples/reaction_extractor.py -i data/paper.md`
- Generate CSV files: See [CSV Export Guide](./features/csv_export_guide.md)
- View sessions: `streamlit run src/webui/app.py`

### For Developers

**Architecture**:
- Two-phase extraction: Document structure analysis → LLM extraction
- PDB handling: Normalized database structure with separate CSV files
- Session tracking: SQLite-based conversation and extraction tracking
- Vision analysis: Multi-modal figure understanding with LLM

**Key Files**:
- `config/agents/` - Markdown-based agent configurations
- `src/tools/` - Tool implementations
- `src/agents/` - Agent implementations
- `tests/` - Comprehensive test coverage

**Testing**:
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# See [Testing Guide](./testing.md) for more details
```

### For Contributors

**Code Style**:
- Import sorting: `isort --profile=google`
- Formatting: `yapf` (config: `.style.yapf`)
- Type checking: `mypy --ignore-missing-imports`
- Pre-commit: Automatic formatting on commit

See [Development Guide](./DEVELOPMENT_GUIDE.md) for details.

## Documentation by Category

### Data Extraction & Analysis

| Document | Description |
|----------|-------------|
| [Enzyme Extraction](features/enzyme_extraction.md) | Comprehensive enzyme reaction extraction pipeline |
| [CSV Export Guide](features/csv_export_guide.md) | CSV export pipeline for extraction results |
| [Vision Image Analyzer](tools/vision_image_analyzer.md) | Vision-based scientific figure analysis |

### Technical Features

| Document | Description |
|----------|-------------|
| [Streaming & Thinking Mode](features/streaming_thinking_mode.md) | Real-time streaming with LLM reasoning |
| [PDB Features](tools/pdb_features.md) | PDB ID extraction, novelty classification, and EC lookup |
| [Delegation Pattern](architecture/delegation_pattern.md) | Agent-Tool delegation architecture |

### Development & Testing

| Document | Description |
|----------|-------------|
| [Testing Guide](testing.md) | Testing strategies, requirements, and best practices |
| [Development Guide](DEVELOPMENT_GUIDE.md) | Code style, formatting tools, and pre-commit setup |

### UI/UX

| Document | Description |
|----------|-------------|
| [Theme Guide](webui/theme_guide.md) | Scientific Laboratory theme design reference |

## Contributing to Documentation

When adding new documentation:

1. **Use clear, descriptive filenames**
   - Good: `pdb_features.md`, `enzyme_extraction.md`
   - Bad: `doc1.md`, `notes.md`

2. **Organize by category**:
   - Features → `features/`
   - Tools → `tools/`
   - Architecture → `architecture/`
   - Web UI → `webui/`

3. **Include table of contents** for longer documents
4. **Add examples** and code snippets
5. **Update this README** to maintain the index

6. **Keep documentation focused**:
   - User guides → Main README or feature documents
   - Feature specs → `features/` directory
   - Implementation details → Inline code comments or `architecture/` directory

## External Resources

- **Anthropic Claude API**: https://docs.anthropic.com/
- **KEGG Database**: https://www.genome.jp/kegg/
- **KEGG API**: https://www.kegg.jp/kegg/rest/keggapi.html
- **Rhea Database**: https://www.rhea-db.org/
- **RCSB PDB Data API**: https://data.rcsb.org/
- **Pydantic Documentation**: https://docs.pydantic.dev/
- **Streamlit Documentation**: https://docs.streamlit.io/

---

**Last Updated**: 2025-02-02
**Maintainer**: GPTase Development Team
