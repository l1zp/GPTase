# MinerU CLI Reference

Use this file for local CLI extraction — the fallback when `MINERU_TOKEN` is not set.
**Prefer the cloud API ([cloud_api.md](./cloud_api.md)) when a token is available.**

## Mode Choice

- `mineru-open-api flash-extract`
  - No token required
  - Markdown only
  - Best for quick reads of small/simple PDFs
  - Rate-limited and size-limited

- `mineru-open-api extract`
  - Token required
  - Better for tables, formulas, OCR, larger files, batch mode, and non-Markdown output

- `mineru` (local pipeline, highest local precision)
  - Requires local model downloads (`mineru-models-download -s modelscope -m all`)
  - Use `hybrid-auto-engine` mode for best quality
  - On Apple Silicon with transformers 5.x: requires 5 source patches (see `mineru_transformers5x_patches.md`)
  - MFR formula recognition may hallucinate on Apple Silicon — add `-f False` to disable

## Common Commands

### Quick extraction

```bash
mineru-open-api flash-extract "paper.pdf" -o "./out/"
```

### Precision extraction (token required)

```bash
mineru-open-api extract "paper.pdf" -o "./out/"
```

### OCR or higher-quality extraction

```bash
mineru-open-api extract "paper.pdf" -o "./out/" --ocr --model vlm
```

### Local pipeline (Apple Silicon)

```bash
MINERU_MODEL_SOURCE=modelscope MINERU_VIRTUAL_VRAM_SIZE=8 \
  mineru -p "paper.pdf" -o "./output/" -l en
```

Set `MINERU_VIRTUAL_VRAM_SIZE` to actual unified memory size (8, 16, 32) because
mineru's `get_vram()` has no MPS branch and defaults to 1 GB otherwise.

## When To Skip `flash-extract`

Go straight to cloud API or `extract` when the user asks for:

- table extraction
- formula recognition
- OCR for scanned PDFs
- non-Markdown formats
- large PDFs or many pages
- batch extraction

## Common Failures

- `429` or flash rate-limit:
  - explain that quick mode is rate-limited
  - suggest cloud API or `extract` with a token
- file too large or too many pages:
  - explain the quick-mode limit
  - suggest cloud API or `extract`
- missing token on `extract`:
  - tell the user to run `mineru-open-api auth` or set `MINERU_TOKEN`
- poor extraction quality (local):
  - suggest cloud API for best results
  - or try `--model vlm` / `--ocr` with local extract
- Apple Silicon local issues:
  - transformers 5.x breaks mineru 3.0.8 in 5 places; see `mineru_transformers5x_patches.md`
  - MFR hallucination on Apple Silicon is a known limitation; add `-f False` to disable formulas

## Practical Notes

- Prefer saving to a directory so Markdown and extracted images stay together.
- If the user asks how to install or update MinerU, answer with setup guidance instead of pretending extraction can proceed.
- Only inspect the generated Markdown after the CLI run succeeds.
