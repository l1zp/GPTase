---
name: pdf-extractor
description: |
  Extract content from PDF documents with MinerU. Use when the user provides a PDF path or PDF URL and wants to read, parse, extract, OCR, convert to Markdown, recover tables or formulas, or analyze the document content. Trigger for requests like "read this PDF", "parse this paper", "extract text from this PDF", "OCR this scanned PDF", "convert PDF to markdown", or "extract tables from this PDF". Do not use for creating PDFs, editing PDFs, merging or splitting PDFs, signing PDFs, compressing PDFs, or general file operations unrelated to content extraction.
---

# PDF Extractor

Use MinerU to turn PDFs into Markdown and structured content.

## Routing

1. Use `flash-extract` for quick Markdown extraction from a normal PDF when the user did not ask for tables, formulas, OCR, or non-Markdown output.
2. Use `extract` when the PDF is scanned, table-heavy, formula-heavy, large, batch-oriented, or the user asked for OCR or richer output.
3. If `flash-extract` hits limits or rate limits, explain the limit and switch the user toward `extract` with a token.
4. If the user did not provide an output path, choose a deterministic output directory instead of writing into an unclear location.

## Rules

- Treat this as a document-extraction workflow, not a PDF editing workflow.
- Prefer extraction correctness over speed when the PDF is complex.
- Quote file paths with spaces or shell-special characters.
- Read the generated Markdown only after extraction succeeds.
- Report the output path clearly.

## Load References

- Read [references/mineru_cli.md](./references/mineru_cli.md) for command syntax, limits, flags, and error handling.
- Read [references/output_paths.md](./references/output_paths.md) when the user did not specify `-o` and you need a safe default directory.
