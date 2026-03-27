# MinerU CLI Reference

Use this file for exact command patterns, limit handling, and troubleshooting.

## Mode Choice

- `mineru-open-api flash-extract`
  - No token required
  - Markdown only
  - Best for quick reads of small/simple PDFs
  - Rate-limited and size-limited
- `mineru-open-api extract`
  - Token required
  - Better for tables, formulas, OCR, larger files, batch mode, and non-Markdown output

## Common Commands

### Quick extraction

```bash
mineru-open-api flash-extract "paper.pdf" -o "./out/"
```

### Precision extraction

```bash
mineru-open-api extract "paper.pdf" -o "./out/"
```

### OCR or higher-quality extraction

```bash
mineru-open-api extract "paper.pdf" -o "./out/" --ocr --model vlm
```

## When To Skip `flash-extract`

Go straight to `extract` when the user asks for:

- table extraction
- formula recognition
- OCR for scanned PDFs
- non-Markdown formats
- large PDFs or many pages
- batch extraction

## Common Failures

- `429` or flash rate-limit:
  - explain that quick mode is rate-limited
  - suggest `extract` with a token
- file too large or too many pages:
  - explain the quick-mode limit
  - suggest `extract`
- missing token on `extract`:
  - tell the user to run `mineru-open-api auth` or set `MINERU_TOKEN`
- poor extraction quality:
  - suggest `--model vlm`
  - suggest `--ocr` for scanned PDFs

## Practical Notes

- Prefer saving to a directory so Markdown and extracted images stay together.
- If the user asks how to install or update MinerU, answer with setup guidance instead of pretending extraction can proceed.
- Only inspect the generated Markdown after the CLI run succeeds.
