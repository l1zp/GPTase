# Enzyme Extraction Summary Agent

## Agent Description

This agent generates comprehensive summaries of enzyme kinetics extraction results from scientific literature. It analyzes extracted reaction data and produces structured reports in multiple formats.

## Capabilities

- **Statistical Analysis**: Calculates key metrics (coverage rates, ranges, outliers)
- **Top Performers**: Identifies best enzyme variants based on kcat/KM and Tm
- **Data Quality**: Assesses completeness and identifies missing data
- **Structured Reports**: Generates Markdown, JSON, and HTML summaries
- **Comparative Analysis**: Highlights improvements over wild-type/reference enzymes

## Input

The agent accepts a task with the following structure:

```json
{
  "extraction_path": "path/to/extraction.json",
  "output_formats": ["markdown", "json", "html"],
  "output_dir": "path/to/output",
  "document_name": "document_name"
}
```

### Input Fields

- `extraction_path` (required): Path to extraction.json file from enzyme kinetics extractor
- `output_formats` (optional): List of desired output formats. Default: ["markdown"]
  - Supported: "markdown", "json", "html"
- `output_dir` (optional): Directory for output files. Default: "data/output/{doc}/summary"
- `document_name` (optional): Name of the document for report title

## Output

The agent returns a structured summary with the following components:

### 1. Overview Statistics
- Total enzyme variants extracted
- Data completeness for each kinetic parameter (Km, kcat, kcat/KM, Tm)
- Experimental conditions summary

### 2. Top Performers
- Highest kcat/KM variants (catalytic efficiency)
- Highest Tm variants (thermal stability)
- Most improved variants vs wild-type

### 3. Data Quality Assessment
- Coverage statistics for each field
- List of variants with missing critical data
- Data consistency checks

### 4. Detailed Tables
- Complete enzyme variant table with all parameters
- Mutations summary (if applicable)
- PDB structures mapping

### 5. Key Findings
- Significant improvements (e.g., ">10x increase in kcat/KM")
- Notable patterns (e.g., "all F113L mutations improve activity")
- Recommendations for further analysis

## Output Format

### Markdown Report

```markdown
# Enzyme Kinetics Extraction Summary: {Document Name}

## Overview
- **Document**: {source_file}
- **Total Variants**: {count}
- **Extraction Date**: {timestamp}

## Statistics
...

## Top Performers
...

## Detailed Data
...
```

### JSON Report

```json
{
  "document_name": "...",
  "overview": {...},
  "statistics": {...},
  "top_performers": {...},
  "detailed_data": [...]
}
```

### HTML Report

Interactive HTML with tables, charts, and collapsible sections.

## Examples

### Basic Usage

```python
task = {
    "extraction_path": "data/output/listov2025/extraction/extraction.json",
    "output_formats": ["markdown"],
    "document_name": "listov2025"
}

result = await agent.process_task(task)
```

### Multiple Output Formats

```python
task = {
    "extraction_path": "data/output/listov2025/extraction/extraction.json",
    "output_formats": ["markdown", "json", "html"],
    "document_name": "listov2025",
    "output_dir": "data/output/listov2025/summary"
}
```

## Implementation Notes

- Uses pandas for data manipulation and analysis
- Supports comparison against wild-type/reference enzyme (first variant assumed as reference)
- Handles missing data gracefully (reports coverage rates)
- Generates file outputs in specified directory
- Maintains JSON schema compatibility with extraction format

## Dependencies

- pandas: Data analysis
- jinja2: HTML template rendering (optional)
- pathlib: File path handling

## Error Handling

- Invalid extraction path: Returns error with suggested path
- Missing required fields: Reports in data quality section
- Empty extraction: Returns summary with zero counts
- File write errors: Returns error with file path details
