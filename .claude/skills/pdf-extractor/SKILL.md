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

3. **Local `mineru` CLI (local fallback)** — Use only when `MINERU_TOKEN` is not available and `flash-extract` is not suitable.
   - This means scanned PDFs, table-heavy PDFs, formula-heavy PDFs, or any case where no-token quick mode is too weak.
   - Requires local model downloads and may have platform-specific issues (especially on Apple Silicon with transformers 5.x).
   - Read [references/mineru_cli.md](./references/mineru_cli.md) for command syntax and troubleshooting.

## Rules

- Treat this as a document-extraction workflow, not a PDF editing workflow.
- Prefer extraction correctness over speed when the PDF is complex.
- Quote file paths with spaces or shell-special characters.
- Read the generated Markdown (`full.md`) only after extraction succeeds.
- Report the output path clearly.
- For batch jobs, upload all files in a single API request and poll once for the shared `batch_id`.

## Post-Extraction: Tables → Image References

After MinerU extraction completes (cloud or CLI path), MinerU emits each detected table BOTH as inline `<table>...</table>` HTML in `full.md` AND as a separately cropped JPG under `images/`. The HTML form has two failure modes for downstream LLM extraction:

- **Single-line giants** — large tables (e.g., 21-row kinetics tables) collapse onto one 40-90 KB markdown line, blowing past tool-result truncation limits and triggering API gateway timeouts.
- **Hallucination magnet** — when a model is asked to "copy the table verbatim", it tends to summarize and emit `[... additional rows truncated]` placeholders, fabricating plausible variant names.

**Always run the rewriter after MinerU finishes**:

```bash
python .claude/skills/pdf-extractor/scripts/rewrite_tables_as_images.py <paper_dir>
```

Or for a whole tree of MinerU outputs (recursive, includes SI subdirs):

```bash
python .claude/skills/pdf-extractor/scripts/batch_rewrite_tables.py <root_dir>
```

What the rewriter does, per paper directory:
1. Reads `*_content_list.json` to get the canonical `(table_body, img_path)` pairs.
2. Replaces each `<table>...</table>` block in `main.md` with `![Table N](images/<hash>.jpg)`.
3. Writes a sidecar `tables_index.json` mapping `table_<N>` to stable physical identifiers (`page_idx`, `bbox`, `caption`, `img_path`). Downstream consumers should read this rather than re-parsing `content_list.json`.
4. Backs up the original `main.md` to `main.md.pre_rewrite` (idempotent — never overwrites an existing backup).

The rewriter is byte-deterministic and idempotent. Re-running on an already-rewritten directory is safe — `<table>` blocks not found are ignored, sidecar still regenerates.

## Recovering broken tables: PDF text layer fallback

When MinerU's `csv_preview` is obviously broken (rows scrambled across cells, scientific notation flattened to `1.5x104`, sequences split mid-string), the source PDF's **text layer** often holds the data cleanly — no OCR, no vision, just direct extraction via PyMuPDF. Use this for one-off ground-truth fixes that downstream agents will treat as canonical.

See [references/pdf_text_layer_fallback.md](./references/pdf_text_layer_fallback.md) for the full pattern: when to reach for it, how to anchor on row markers, the `fix_superscript` heuristic for `\d+x10\d+` → `<mantissa>×10^<exponent>` recovery, and two real corpus examples (broom_2020 sequence tables, khersonsky_2012 kinetics).

## Load References

- Read [references/cloud_api.md](./references/cloud_api.md) for the cloud API flow (preferred method).
- Read [references/mineru_cli.md](./references/mineru_cli.md) for CLI fallback syntax, limits, and error handling.
- Read [references/output_paths.md](./references/output_paths.md) when the user did not specify an output path.
- Read [references/pdf_text_layer_fallback.md](./references/pdf_text_layer_fallback.md) when MinerU's table extraction is corrupt and you need a recovery path.
