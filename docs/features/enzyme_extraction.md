# Enzyme Reaction Extraction

Detailed documentation for extracting enzyme reaction data from scientific literature using specialized agents.

## Overview

The framework provides specialized agents for extracting enzyme reaction data from scientific literature with a two-phase architecture that optimizes token usage while maintaining comprehensive data extraction.

## Available Agents

- **`enzyme_kinetics_extractor`** - Extracts kinetic parameters (Km, kcat, Tm, Vmax, etc.) from tables
- **`enzyme_design_parser`** - Extracts enzyme design workflows and methodology

## Extraction Pipeline Architecture

The extraction process uses a **two-phase architecture** with session tracking:

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT: Scientific Literature (Markdown/HTML/Text)              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: Document Structure Analysis                          │
│  ────────────────────────────────────────────────────────────  │
│  Tool: DocumentStructureAnalyzer                                │
│  Step: structure_analysis (phase1_structure)                    │
│  ────────────────────────────────────────────────────────────  │
│  ✓ Identify document sections and hierarchy                     │
│  ✓ Extract ALL tables (Markdown & HTML formats)                 │
│  ✓ Classify tables using LLM (confidence > 0.6)                 │
│    - Kinetics tables, mutation tables, etc.                    │
│  ✓ Locate key paragraphs with kinetic keywords                 │
│  ✓ Save analysis to data/analysis/{doc}_analysis.json          │
│  ────────────────────────────────────────────────────────────  │
│  Output: Structured tables + relevant paragraphs               │
│  Tokens: ~60-80% reduction vs. full document                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: Targeted LLM Extraction                              │
│  ────────────────────────────────────────────────────────────  │
│  Agent: LLMEnzymeExtractorAgent                                 │
│  Step: main_extraction (phase2_extraction)                      │
│  ────────────────────────────────────────────────────────────  │
│  ✓ Process ONLY relevant content from Phase 1                   │
│  ✓ Extract structured reaction data:                           │
│    - Enzyme variants (ALL rows from tables)                     │
│    - Substrates & products                                      │
│    - Kinetics: kcat, KM, kcat/KM, Tm, Vmax                     │
│    - Experimental conditions (temp, pH, buffer)                │
│    - PDB IDs, citations, yields                                 │
│  ✓ Validate against Pydantic schema                             │
│  ✓ Output to data/extraction/{doc}_extraction.json              │
│  ────────────────────────────────────────────────────────────  │
│  Output: Structured JSON with EnzymeReaction[]                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Session Tracking (SQLite Database)                             │
│  ────────────────────────────────────────────────────────────  │
│  Database: data/conversations.db                                 │
│  ✓ extraction_sessions: One entry per document processed        │
│  ✓ extraction_session_steps: structure_analysis + main_extraction│
│  ✓ conversations: Full LLM prompts & responses                 │
│  ✓ messages: Individual message history                         │
│  ✓ responses: Metadata (tokens, latency, thinking process)      │
│  ────────────────────────────────────────────────────────────  │
│  View in Web UI: Agent Sessions page                             │
│  → See prompts, thinking, responses for each step              │
└─────────────────────────────────────────────────────────────────┘
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
# Start Web UI
streamlit run src/webui/app.py

# Navigate to: Agent Sessions
# View: Agent → Task → Job → LLM Call Details
```

## Key Features

### 1. Comprehensive Extraction

Extracts **ALL enzyme variants** from tables:
- Not just "important" or "main" variants
- Each table row = separate reaction entry
- Handles uncertainties (±), "n.c." (not calculable), "n.d." (not detected)

**Example:**
```
Table with 10 variants → 10 separate reaction entries in output
```

### 2. Smart Content Selection (Phase 1)

- **LLM-based table classification** (kinetics, mutations, methods)
- **Identifies paragraphs** with experimental details
- **Reduces token usage** by 60-80% vs. full document

**Benefits:**
- Faster processing (less content to analyze)
- More accurate extraction (focused on relevant data)
- Cost-effective (fewer tokens consumed)

### 3. Structured Output (Phase 2)

Extracted data includes:

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
- Temperature (°C)
- pH value
- Buffer composition and concentration
- Reaction time

**Additional Data:**
- PDB IDs (Protein Data Bank structures)
- Citations and references
- Reaction yields (%)
- Source file tracking

All validated against Pydantic schema for consistency.

### 4. Full Traceability (Session Tracking)

**Hierarchical Display:**
```
Agent (reaction_extractor)
├── Task 1: listov2025.md (COMPLETED, 2 jobs, 45.2s)
│   ├── Job 01: structure_analysis (COMPLETED)
│   │   └── LLM Call Details: tables identified, paragraphs located
│   └── Job 02: main_extraction (COMPLETED)
│       └── LLM Call Details: prompts, thinking, extracted reactions
└── Task 2: another_doc.md (IN_PROGRESS, 1 job, 12.1s)
    └── Job 01: main_extraction (IN_PROGRESS)
        └── LLM Call Details: prompts, thinking, response
```

**View Job Details:**
- **Prompt Messages**: Collapsible sections for each role (User/Assistant/System)
- **Thinking Process**: LLM reasoning (when thinking mode enabled)
- **Response**: Extracted reaction data
- **Metrics**: Tokens, latency, throughput

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

Modify the extraction schema in `src/tools/markdown_enzyme_parser.py` to add new fields:

```python
class EnzymeReaction(BaseModel):
    # Existing fields...
    custom_field: Optional[str] = None  # Add new field
```

Update the system prompt in `config/agents/enzyme_kinetics_extractor.md` to include extraction rules for the new field.

### Batch Processing

```bash
# Process multiple documents
for file in data/papers/*.md; do
    python examples/reaction_extractor.py -i "$file" -o "data/results/$(basename "$file" .md)_extraction.json"
done
```

### Integration with Other Tools

```python
from src.agents.specialized.llm_enzyme_extractor_orchestrator import \
    LLMEnzymeExtractorAgent

agent = LLMEnzymeExtractorAgent(
    "reaction_extractor",
    memory_manager,
    tool_registry,
    model_manager=manager
)

result = await agent.process_task({
    "text": open("data/paper.md").read()
})
```

## Session Tracking in Detail

### Database Schema

**Tables:**
- `extraction_sessions` - One entry per document processed
- `extraction_session_steps` - structure_analysis + main_extraction steps
- `conversations` - Full LLM prompts & responses
- `messages` - Individual message history
- `responses` - Metadata (tokens, latency, thinking process)

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

1. **Run Structure Analysis First**: Always let Phase 1 complete to reduce token usage
2. **Check Classification Confidence**: Table classifications with confidence < 0.6 may need review
3. **Validate Output**: Review extracted data, especially for complex tables
4. **Use Session Tracking**: Leverage Web UI to debug extraction issues
5. **Handle Special Values**: Be aware of "n.c." (not calculable) and "n.d." (not detected)

## Troubleshooting

### Issue: Missing kinetic data

**Cause**: Table not classified as kinetics table in Phase 1

**Solution**:
1. Check `data/analysis/{doc}_analysis.json`
2. Review table classification confidence scores
3. Adjust classification threshold if needed

### Issue: Incorrect extraction

**Cause**: Ambiguous table structure or formatting

**Solution**:
1. Review session in Web UI
2. Check LLM prompts and responses
3. Modify system prompt to handle specific table format

### Issue: High token usage

**Cause**: Phase 1 not filtering content effectively

**Solution**:
1. Verify structure analysis ran successfully
2. Check for unclassified tables being included
3. Review table classification in analysis output

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - Main project documentation
- [docs/architecture/delegation_pattern.md](../architecture/delegation_pattern.md) - Architecture pattern
- [docs/testing.md](../testing.md) - Testing guidelines
