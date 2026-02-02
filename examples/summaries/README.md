# Summary Generation Examples

This directory contains examples for generating summaries from extraction results.

## Available Examples

### 1. Enzyme Extraction Summary (`enzyme_summary_demo.py`)
**Purpose**: Generate comprehensive summaries of enzyme extraction results

**Features**:
- Process enzyme extraction JSON files
- Generate markdown summaries
- Create statistical overviews
- Format results for presentation

**Run**:
```bash
python examples/summaries/enzyme_summary_demo.py
```

**Input**: Enzyme extraction JSON files (from `reaction_extractor.py`)
**Output**: Formatted summary documents (Markdown, HTML, JSON)

---

### 2. Generic Summary Generation (`generate_summary.py`)
**Purpose**: Generate summaries from various data sources

**Features**:
- Flexible input formats
- Customizable summary templates
- Export to multiple formats (Markdown, HTML, JSON)
- Statistical analysis

**Run**:
```bash
python examples/summaries/generate_summary.py -i data/extraction/results.json
```

**Options**:
- `-i`: Input file path
- `-o`: Output directory (default: `data/summaries`)
- `-f`: Output format (markdown, html, json)

---

## 📊 Summary Formats

### Markdown Summary
```markdown
# Enzyme Extraction Summary

## Statistics
- Total reactions: 25
- Unique EC numbers: 12
- Enzymes with kinetic data: 18

## Reactions
### 1. Alcohol Dehydrogenase (EC 1.1.1.1)
- **Substrates**: Ethanol, NAD+
- **Products**: Acetaldehyde, NADH
- **kcat**: 3.2 s^-1
- **KM**: 0.5 mM
```

### HTML Summary
Interactive HTML with:
- Navigation menu
- Expandable sections
- Color-coded status indicators
- Download buttons

### JSON Summary
Machine-readable format with:
- Complete data structures
- Metadata and statistics
- API-friendly format

---

## 🔗 Integration with Pipeline

These summary tools work best with outputs from:

1. **Reaction Extractor** (`../reaction_extractor.py`)
   - Input: Extraction JSON files
   - Output: Formatted summaries

2. **Vision Image Analyzer** (`../vision_image_analyzer.py`)
   - Input: Image analysis results
   - Output: Statistical summaries

---

## 💡 Usage Tips

### Batch Processing

Generate summaries for multiple files:

```python
import asyncio
from pathlib import Path

async def batch_summarize(directory):
    """Generate summaries for all JSON files in directory."""
    for json_file in Path(directory).glob("*.json"):
        await generate_summary(json_file)
```

### Custom Templates

Create custom summary templates:

```python
template = """
# Custom Summary for {enzyme_name}

## Kinetics
- kcat: {kcat} s^-1
- KM: {km} mM

## Conditions
- Temperature: {temp} °C
- pH: {ph}
"""
```

---

## 📚 Related Documentation

- [Reaction Extractor](../reaction_extractor.py) - Generate extraction data
- [Vision Analyzer](../vision_image_analyzer.py) - Analyze figures
- [Data Structure](../../CLAUDE.md) - Understanding output formats
