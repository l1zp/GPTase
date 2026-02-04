# Enzyme Reaction Extraction

Extract enzyme reaction data from scientific literature using specialized agents.

## Overview

The framework provides a two-phase architecture that optimizes token usage while maintaining comprehensive data extraction from scientific literature.

## Available Agents

| Agent | Type | Purpose |
|-------|------|---------|
| `enzyme_kinetics_extractor` | Markdown-based | Extracts kinetic parameters (Km, kcat, Tm, Vmax, etc.) |

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
# Extract from default file (data/listov2025.md)
python examples/reaction_extractor.py

# Extract from specific file
python examples/reaction_extractor.py -i data/my_paper.md

# Specify custom output path
python examples/reaction_extractor.py -i data/paper.md -o data/results/output.json
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
Agent (enzyme_kinetics_extractor)
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

Edit the `Output Format` section in `config/agents/enzyme_kinetics_extractor.md`.

**Update the extraction instructions:**

Edit the `System Prompt` or `Task Processing` sections in `config/agents/enzyme_kinetics_extractor.md`.

### Batch Processing

```bash
for file in data/papers/*.md; do
    python examples/reaction_extractor.py -i "$file"
done
```

### Integration with Other Tools

```python
from src.agents.markdown_agent import MarkdownAgentFactory

factory = MarkdownAgentFactory()
agent = factory.create_agent(
    "enzyme_kinetics_extractor",
    memory_manager,
    tool_registry,
    model_manager=manager
)

result = await agent.process_task({
    "text": open("data/paper.md").read(),
    "description": "Extract kinetics from paper"
})
```

## Session Tracking

### Database Schema

| Table | Purpose |
|-------|---------|
| `extraction_sessions` | One entry per document processed |
| `extraction_session_steps` | structure_analysis + main_extraction steps |
| `conversations` | Full LLM prompts and responses |
| `messages` | Individual message history |
| `responses` | Metadata (tokens, latency, thinking process) |

### Querying Sessions

```python
from src.conversations.storage import ConversationStorage

storage = ConversationStorage(db_path="data/conversations.db", enabled=True)

# Get recent sessions
sessions = await storage.get_recent_sessions(limit=10)

# Get session details
session = await storage.get_session_details(session_id)

# Get step details
step = await storage.get_step_details(step_id)
```

## Best Practices

1. **Run Structure Analysis First**: Phase 1 reduces token usage significantly
2. **Check Classification Confidence**: Tables with confidence < 0.6 may need review
3. **Validate Output**: Review extracted data for complex tables
4. **Use Session Tracking**: Leverage Web UI to debug extraction issues
5. **Handle Special Values**: "n.c." (not calculable) and "n.d." (not detected)

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
- [docs/architecture/delegation_pattern.md](../architecture/delegation_pattern.md) - Architecture pattern
- [docs/testing.md](../testing.md) - Testing guidelines
