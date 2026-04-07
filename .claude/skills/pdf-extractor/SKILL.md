---
name: pdf-extractor
description: |
  Extract content from PDF documents with MinerU. Use when the user provides a PDF path or PDF URL and wants to read, parse, extract, OCR, convert to Markdown, recover tables or formulas, or analyze the document content. Trigger for requests like "read this PDF", "parse this paper", "extract text from this PDF", "OCR this scanned PDF", "convert PDF to markdown", or "extract tables from this PDF". Do not use for creating PDFs, editing PDFs, merging or splitting PDFs, signing PDFs, compressing PDFs, or general file operations unrelated to content extraction.
---

# PDF Extractor

Use MinerU to turn PDFs into Markdown and structured content.

## Routing

**Check `MINERU_TOKEN` first, then decide:**

1. **Cloud API (preferred)** — Use when `MINERU_TOKEN` is set.
   - Best quality, no local GPU or model downloads required.
   - Use for single files, batches, scanned PDFs, formula-heavy papers, or any case where correctness matters.
   - Write a short Python script using the cloud API flow and run it with `python`.
   - Read [references/cloud_api.md](./references/cloud_api.md) for the exact 3-step flow and batch processing pattern.

2. **`flash-extract` (no-token fallback)** — Use only when `MINERU_TOKEN` is not available AND the PDF is small and simple (no tables, no formulas, no OCR needed).
   - Rate-limited and size-limited; switch to cloud API if it hits limits.

3. **`extract` CLI (local fallback)** — Use only when both cloud API and flash-extract are unavailable.
   - Requires local model downloads and may have platform-specific issues (especially on Apple Silicon with transformers 5.x).
   - Read [references/mineru_cli.md](./references/mineru_cli.md) for command syntax and troubleshooting.

## Rules

- Treat this as a document-extraction workflow, not a PDF editing workflow.
- Prefer extraction correctness over speed when the PDF is complex.
- Quote file paths with spaces or shell-special characters.
- Read the generated Markdown (`full.md`) only after extraction succeeds.
- Report the output path clearly.
- For batch jobs, upload all files in a single API request and poll once for the shared `batch_id`.

## Load References

- Read [references/cloud_api.md](./references/cloud_api.md) for the cloud API flow (preferred method).
- Read [references/mineru_cli.md](./references/mineru_cli.md) for CLI fallback syntax, limits, and error handling.
- Read [references/output_paths.md](./references/output_paths.md) when the user did not specify an output path.
