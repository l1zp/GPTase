# Enzyme Reaction Extraction

Extract enzyme reaction data from scientific literature using specialized agents.

## Overview

The framework provides a two-phase architecture that optimizes token usage while maintaining comprehensive data extraction from scientific literature.

## Available Agents

| Agent | Type | Purpose |
|-------|------|---------|
| `enzyme-kinetics-extractor` | Markdown-based | Extracts kinetic parameters (Km, kcat, Tm, Vmax, etc.) |
| `vision-image-analyzer` | Multimodal | Analyzes scientific figures, extracts tabular data |
| `vision-image-analyzer-react` | Multimodal (ReAct) | Iterative figure analysis with reasoning chain |

## Extraction Pipeline

The extraction process uses a **two-phase architecture** with session tracking:

```
INPUT: Scientific Literature (Markdown/HTML/Text)
                │
                ▼
    ┌───────────────────────────────────────┐
    │ Phase 1: Document Structure Analysis  │
    │   - Extract tables (Markdown + HTML)  │
    │   - Classify tables using LLM         │
    │   - Locate key paragraphs              │
    │   - Save to data/analysis/             │
    │   Tokens: ~60-80% reduction            │
    └───────────────┬───────────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────────┐
    │ Phase 2: Targeted LLM Extraction      │
    │   - Extract enzyme variants            │
    │   - Kinetic parameters (kcat, KM, Tm) │
    │   - Experimental conditions            │
    │   - PDB IDs, citations, yields         │
    │   - Save to data/extraction/           │
    └───────────────┬───────────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────────┐
    │ Session Tracking (SQLite Database)    │
    │   - extraction_sessions table          │
    │   - extraction_session_steps table     │
    │   - Full LLM prompts & responses       │
    │   View: Agent Sessions page in Web UI  │
    └───────────────────────────────────────┘
```

## Quick Start

### Basic Usage

```bash
# Via CLI (recommended)
gptase sop -p enzyme_extraction_pipeline -i data/paper.md -o output/

# List available SOPs
gptase sop --list

# Via Python script
python examples/reaction_extractor.py -i data/paper.md

# Specify custom output path
python examples/reaction_extractor.py -i data/paper.md -o data/results/
```

### Multimodal Figure Analysis

```bash
# Analyze scientific figure
python examples/vision_image_analyzer.py figure.png

# Multiple figures
python examples/vision_image_analyzer.py fig1.png fig2.png

# Use ReAct agent for complex figures
python examples/vision_image_analyzer.py figure.png --agent vision-image-analyzer-react
```

### View Extraction Sessions

```bash
streamlit run src/webui/app.py
# Navigate to: Agent Sessions
# View: Agent -> Task -> Job -> LLM Call Details
```

## Key Features

### Comprehensive Extraction

Extracts **ALL enzyme variants** from tables:
- Each table row becomes a separate reaction entry
- Handles uncertainties (±), "n.c." (not calculable), "n.d." (not detected)

### Smart Content Selection

- **LLM-based table classification** (kinetics, mutations, methods)
- **Identifies paragraphs** with experimental details
- **Reduces token usage** by 60-80% vs. full document

### Multimodal Support

- **Vision Agent**: Extract data from scientific figures (tables, plots, diagrams)
- **Automatic image encoding**: Base64 encoding for vision models
- **Multiple images**: Analyze multiple figures in one request

### Structured Output

**Enzyme Information:**
- Enzyme names and variants
- Substrates and products
- Mutations and modifications

**Kinetic Parameters:**
- `kcat` - Turnover number (s⁻¹)
- `KM` - Michaelis constant (mM)
- `kcat/KM` - Catalytic efficiency (M⁻¹s⁻¹)
- `Tm` - Melting temperature (°C)
- `Vmax` - Maximum velocity

**Experimental Conditions:**
- Temperature, pH, buffer, reaction time

**Additional Data:**
- PDB IDs, citations, yields (%), source file

### Session Tracking

Hierarchical display in Web UI:

```
Agent (enzyme-kinetics-extractor)
├── Task 1: listov2025.md (COMPLETED, 2 jobs, 45.2s)
│   ├── Job 01: structure_analysis (COMPLETED)
│   └── Job 02: main_extraction (COMPLETED)
└── Task 2: another_doc.md (IN_PROGRESS, 1 job, 12.1s)
    └── Job 01: main_extraction (IN_PROGRESS)
```

## Output Format

### JSON Structure

```json
{
  "reactions": [
    {
      "source_file": "inline_text.md",
      "enzyme_name": "Des27",
      "substrates": ["5-nitrobenzisoxazole"],
      "products": ["2-nitrophenol"],
      "conditions": {
        "temperature": "25 °C",
        "pH": "7.3",
        "buffer": "20 mM HEPES",
        "time": null,
        "notes": null
      },
      "kinetics": {
        "Km": null,
        "Km_unit": "mM",
        "Vmax": null,
        "Vmax_unit": null,
        "kcat": null,
        "kcat_unit": "s^-1",
        "kcat_over_KM": 130,
        "kcat_over_KM_unit": "M^-1s^-1",
        "Tm": null,
        "Tm_unit": "°C"
      },
      "yield_percent": null,
      "citations": [],
      "pdb_ids": []
    }
  ]
}
```

### Vision Agent Output

```json
{
  "image_paths": ["figure.png"],
  "agent": "vision-image-analyzer",
  "content": {
    "analysis_results": [
      {"image_number": 1, "content": "Table of enzyme variants..."}
    ],
    "extracted_tables": [
      {"image_number": 1, "csv_data": "Variant,kcat/KM,Asp162_vdW\nDes27.2,21,-4.9\n..."}
    ],
    "key_findings": ["Catalytic efficiency increases..."]
  }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `source_file` | str | Original document filename |
| `enzyme_name` | str | Enzyme variant name |
| `substrates` | List[str] | Input substrates |
| `products` | List[str] | Output products |
| `conditions` | object | Experimental conditions |
| `kinetics` | object | Kinetic parameters with units |
| `yield_percent` | float/null | Reaction yield |
| `citations` | List[str] | Reference citations |
| `pdb_ids` | List[str] | PDB structure IDs |

## Advanced Usage

### Custom Extraction Rules

**Update the extraction output format:**

Edit the `Output Guidance` section in `.claude/agents/enzyme-kinetics-extractor.md`.

**Update the extraction instructions:**

Edit the system prompt or workflow sections in `.claude/agents/enzyme-kinetics-extractor.md`.

### Multimodal Agent Integration

```python
from gptase.agents.markdown_agent import MarkdownAgentFactory
from gptase.models.model import Model

model = Model()
factory = MarkdownAgentFactory()

# Create vision agent
agent = factory.create_agent(
    "vision-image-analyzer",
    memory_manager,
    model_manager=model,
)

# Process with images (automatic multimodal handling)
result = await agent.process_task({
    "description": "Extract kinetic data from this figure",
    "image_paths": ["figure.png"],
})
```

### Batch Processing

```bash
for file in data/papers/*.md; do
    python examples/reaction_extractor.py -i "$file"
done
```

### Integration with Other Tools

```python
from gptase.agents.markdown_agent import MarkdownAgentFactory

factory = MarkdownAgentFactory()
agent = factory.create_agent(
    "enzyme-kinetics-extractor",
    memory_manager,
    model_manager=model
)

result = await agent.process_task({
    "text": open("data/paper.md").read(),
    "description": "Extract kinetics from paper"
})
```

## Best Practices

1. **Run Structure Analysis First**: Phase 1 reduces token usage significantly
2. **Check Classification Confidence**: Tables with confidence < 0.6 may need review
3. **Use Vision Agent for Figures**: Extract data from scientific figures with multimodal agent
4. **Validate Output**: Review extracted data for complex tables
5. **Use Session Tracking**: Leverage Web UI to debug extraction issues
6. **Handle Special Values**: "n.c." (not calculable) and "n.d." (not detected)

## Troubleshooting

### Missing kinetic data

**Cause**: Table not classified as kinetics table in Phase 1

**Solution**:
1. Check `data/analysis/{doc}_analysis.json`
2. Review table classification confidence scores
3. Adjust classification threshold if needed

### Incorrect extraction

**Cause**: Ambiguous table structure or formatting

**Solution**:
1. Review session in Web UI
2. Check LLM prompts and responses
3. Modify system prompt to handle specific table format

### High token usage

**Cause**: Phase 1 not filtering content effectively

**Solution**:
1. Verify structure analysis ran successfully
2. Check for unclassified tables being included
3. Review table classification in analysis output

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - Main project documentation
- [Architecture Overview](../architecture.md) - Delegation pattern and multimodal support
- [Vision Image Analyzer](../tools/vision-image-analyzer.md) - Multimodal figure analysis
- [Testing Guide](../testing.md) - Testing guidelines
