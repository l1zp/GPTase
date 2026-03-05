---
name: academic-pdf-reader
description: |
  Read and analyze academic PDF papers, patents, or technical documents.
  Use this skill whenever the user provides a PDF file path or asks to extract content from papers, patents, or technical documents.
  Triggers on: "read this PDF", "extract from paper", "analyze this paper", "parse PDF", "read academic PDF", "extract from document", "paper analysis", "PDF to markdown", "extract methods from paper", "get data from PDF".
---

# Academic PDF Reader

Read and analyze academic PDF papers, patents, or technical documents. Extract structured content including metadata, experimental methods, key data, and figure descriptions.

## Overview

Provides systematic methods for extracting and analyzing structured content from academic PDFs. Supports papers, patents, technical reports, etc.

## When to Use

- User provided a PDF file path
- Need to extract experimental data, methods, or conclusions from a paper
- Need to analyze document structure (sections, figures, references)

## Workflow

### Step 1: PDF -> Markdown Extraction

Use MinerU for high-quality PDF conversion (preserves table and formula structure):

```bash
# Basic extraction
mineru -p /path/to/paper.pdf -o /tmp/mineru_output/

# If MinerU is unavailable, fallback to markitdown
markitdown /path/to/paper.pdf > /tmp/paper_output.md
```

### Step 2: Read and Analyze

Open the extracted Markdown file with text_editor, sequentially identify:

1. **Metadata**: Title, authors, journal/conference, year, DOI
2. **Abstract and keywords**
3. **Section structure**: Document outline by heading levels
4. **Methods section**: Experimental conditions, materials, procedures
5. **Results section**: Key data, tables, figure descriptions
6. **References**: Extract citation list

### Step 3: Figure Processing

If document contains important figures:
- Check the `images/` folder in MinerU output directory
- Describe each figure's content and key findings
- Structurally extract table data

### Step 4: Structured Output

Organize final output in the following format:

```json
{
  "metadata": {
    "title": "...",
    "authors": ["..."],
    "journal": "...",
    "year": 2024,
    "doi": "..."
  },
  "abstract": "...",
  "sections": ["Introduction", "Methods", "Results", "Discussion"],
  "key_findings": ["..."],
  "methods": {
    "materials": ["..."],
    "procedures": ["..."]
  },
  "data": {
    "tables": [...],
    "figures": [...]
  }
}
```

## Tips

- For table-dense papers, prefer MinerU (better structure preservation)
- For text-only papers, markitdown is sufficient
- If PDF is a scan, MinerU supports OCR mode
- Multi-column PDFs need attention to text extraction order
