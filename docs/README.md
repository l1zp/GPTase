# GPTase Documentation

This directory contains detailed documentation for the GPTase project.

## Quick Links

### Core Documentation
- **[Main README](../README.md)** - Project overview, features, and getting started
- **[CLAUDE.md](../CLAUDE.md)** - Project instructions and architecture guide
- **[Enzyme Extraction Workflow](./ENZYME_EXTRACTION_WORKFLOW.md)** - Comprehensive guide for enzyme reaction extraction pipeline

### Feature-Specific Documentation
- **[PDB Features](./pdb_features.md)** - PDB ID extraction, novelty classification, and EC number lookup
- **[Document Structure Analyzer](./DOCUMENT_STRUCTURE_ANALYZER_FLOWCHART.md)** - Two-phase extraction architecture flowchart
- **[Vision Image Analyzer](./VISION_IMAGE_ANALYZER_GUIDE.md)** - Guide for vision-based scientific figure analysis

### Technical Guides
- **[Thinking Mode](./THINKING_MODE.md)** - Extended thinking configuration for Claude models
- **[Tracking Mixin Usage](./tracking_mixin_usage.md)** - Session tracking and monitoring
- **[WebUI Lab Theme](./webui_redesign_lab_theme.md)** - Scientific laboratory UI design
- **[CSV Export Guide](./CSV_EXPORT_GUIDE.md)** - CSV export guide for extraction results
- **[Development Guide](./DEVELOPMENT_GUIDE.md)** - Code style, formatting tools, and pre-commit setup

## Documentation Index

### Overview Documents

| Document | Description | Size |
|----------|-------------|------|
| [ENZYME_EXTRACTION_WORKFLOW.md](./ENZYME_EXTRACTION_WORKFLOW.md) | Complete guide to enzyme reaction extraction from literature | 57KB |
| [pdb_features.md](./pdb_features.md) | PDB ID extraction, novelty classification, and EC lookup | 12KB |
| [VISION_IMAGE_ANALYZER_GUIDE.md](./VISION_IMAGE_ANALYZER_GUIDE.md) | Vision-based figure analysis and data extraction | ~10KB |
| [CSV_EXPORT_GUIDE.md](./CSV_EXPORT_GUIDE.md) | CSV export pipeline guide | ~8KB |

### Architecture & Design

| Document | Description | Size |
|----------|-------------|------|
| [DOCUMENT_STRUCTURE_ANALYZER_FLOWCHART.md](./DOCUMENT_STRUCTURE_ANALYZER_FLOWCHART.md) | Two-phase extraction architecture (Phase 1: structure analysis, Phase 2: LLM extraction) | 11KB |
| [THINKING_MODE.md](./THINKING_MODE.md) | Extended thinking mode for improved LLM reasoning | 6.6KB |
| [TECHNICAL_FEATURES.md](./TECHNICAL_FEATURES.md) | Thinking mode and LLM call tracking (TrackingMixin) | ~6KB |

### Implementation Details

| Document | Description | Size |
|----------|-------------|------|
| [tracking_mixin_usage.md](./tracking_mixin_usage.md) | Session tracking for extraction workflows | 6.5KB |
| [webui_redesign_lab_theme.md](./webui_redesign_lab_theme.md) | Scientific laboratory theme design for WebUI | 5.1KB |
| [DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md) | Code style & pre-commit setup | ~4KB |

## Quick Reference

### For Users

**Getting Started**:
1. Read the [Main README](../README.md) for project overview
2. Follow [ENZYME_EXTRACTION_WORKFLOW.md](./ENZYME_EXTRACTION_WORKFLOW.md) to extract enzyme data
3. Check [pdb_features.md](./pdb_features.md) for PDB-specific functionality

**Common Tasks**:
- Extract enzyme reactions: `python examples/reaction_extractor.py -i data/paper.md`
- Generate CSV files: `python pipelines/json_to_csv.py`
- View sessions: `streamlit run src/webui/app.py`

### For Developers

**Architecture**:
- Two-phase extraction: Document structure analysis → LLM extraction
- PDB handling: Normalized database structure with separate CSV files
- Session tracking: SQLite-based conversation and extraction tracking
- Vision analysis: Multi-modal figure understanding with LLM

**Key Files**:
- `config/agents/` - Markdown-based agent configurations
- `pipelines/` - Data processing pipeline scripts
- `src/tools/` - Tool implementations
- `tests/` - Comprehensive test coverage

### For Contributors

**Code Style**:
- Import sorting: `isort --profile=google`
- Formatting: `yapf` (config: `.style.yapf`)
- Type checking: `mypy --ignore-missing-imports`
- Pre-commit: Automatic formatting on commit

**Testing**:
```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_pdb_novelty.py -v
pytest tests/test_csv_handling.py -v
```

## Documentation by Category

### Data & Extraction

| Document | Description |
|----------|-------------|
| [CSV_EXPORT_GUIDE.md](CSV_EXPORT_GUIDE.md) | CSV export guide for extraction results |
| [ENZYME_EXTRACTION_WORKFLOW.md](ENZYME_EXTRACTION_WORKFLOW.md) | Comprehensive enzyme reaction extraction pipeline guide |
| [VISION_IMAGE_ANALYZER_GUIDE.md](VISION_IMAGE_ANALYZER_GUIDE.md) | Guide for vision-based scientific figure analysis and data extraction |

### Development

| Document | Description |
|----------|-------------|
| [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) | Code style, formatting tools, and pre-commit setup |

### Technical Features

| Document | Description |
|----------|-------------|
| [TECHNICAL_FEATURES.md](TECHNICAL_FEATURES.md) | Thinking mode and LLM call tracking (TrackingMixin) |

### UI/UX

| Document | Description |
|----------|-------------|
| [webui_redesign_lab_theme.md](webui_redesign_lab_theme.md) | Scientific Laboratory theme design reference |

## File Structure

```
docs/
├── README.md                              # This file - documentation navigation
├── CSV_EXPORT_GUIDE.md                    # CSV export guide
├── ENZYME_EXTRACTION_WORKFLOW.md          # Enzyme extraction pipeline (includes structure analyzer)
├── VISION_IMAGE_ANALYZER_GUIDE.md         # Vision analyzer guide
├── DEVELOPMENT_GUIDE.md                   # Code style & pre-commit setup
├── TECHNICAL_FEATURES.md                  # Thinking mode & tracking features
├── pdb_features.md                        # PDB features (consolidated)
├── DOCUMENT_STRUCTURE_ANALYZER_FLOWCHART.md
├── THINKING_MODE.md
├── tracking_mixin_usage.md
└── webui_redesign_lab_theme.md            # Web UI design reference
```

## Deprecated Documentation

The following documents have been consolidated into [pdb_features.md](./pdb_features.md):

- ~~pdb_data_structure.md~~ (merged into pdb_features.md)
- ~~pdb_novelty_feature.md~~ (merged into pdb_features.md)
- ~~pdb_novelty_implementation.md~~ (merged into pdb_features.md)
- ~~pdb_novelty_summary.md~~ (merged into pdb_features.md)
- ~~pdb_source_classification.md~~ (outdated - now using boolean classification)
- ~~pdb_separation_summary.md~~ (merged into pdb_features.md)

## Contributing to Documentation

When adding new documentation:

1. **Use clear, descriptive filenames**
   - Good: `pdb_features.md`, `thinking_mode.md`
   - Bad: `doc1.md`, `notes.md`

2. **Include table of contents** for longer documents
3. **Add examples** and code snippets
4. **Update this README** to maintain the index

5. **Keep documentation focused**:
   - User guides → Main README or ENZYME_EXTRACTION_WORKFLOW.md
   - Feature specs → Separate feature documents
   - Implementation details → Inline code comments or technical docs

## External Resources

- **Anthropic Claude API**: https://docs.anthropic.com/
- **RCSB PDB Data API**: https://data.rcsb.org/
- **Pydantic Documentation**: https://docs.pydantic.dev/
- **Streamlit Documentation**: https://docs.streamlit.io/

---

**Last Updated**: 2025-01-24
**Maintainer**: GPTase Development Team
