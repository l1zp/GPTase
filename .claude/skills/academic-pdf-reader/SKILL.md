---
name: academic-pdf-reader
description: |
  Convert academic PDF papers to Markdown using MinerU. Use this skill whenever the user provides a PDF file path and wants to read, extract, or analyze the document content.

  Triggers on: PDF file path, "read this PDF", "convert PDF", "extract from PDF", "parse PDF", "PDF to markdown", "analyze this paper".

  Do NOT trigger for: creating PDFs, editing PDFs, or general file operations unrelated to document content extraction.
---

# Academic PDF Reader

Convert academic PDF papers, patents, or technical documents to Markdown format using MinerU.

## Usage

```bash
mineru -p /path/to/paper.pdf -o /output/directory/
```

**Parameters:**
- `-p`: Input PDF file path
- `-o`: Output directory (will be created if not exists)

## Output

MinerU outputs:
- Markdown file with preserved structure (tables, formulas, headings)
- `images/` folder containing extracted figures

## Workflow

1. Run `mineru` with the provided PDF path and output directory
2. Report the output file location to the user
3. If needed, read the generated Markdown for further analysis

## Notes

- MinerU preserves table structure and mathematical formulas
- For scanned PDFs, MinerU automatically applies OCR
- Multi-column layouts are handled automatically
