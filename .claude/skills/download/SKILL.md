---
name: download
description: |
  Download academic paper PDFs to disk given one or more DOIs. Use when the user provides DOIs and wants to save papers locally, download PDFs, fetch full text, or save papers to a directory. Trigger for requests like "download this paper", "save the PDF for DOI ...", "download these DOIs to ./papers", "fetch the full text for these papers", or any request that combines DOIs with local file saving. Do not use for searching or finding papers (use academic-search for that); do not use for extracting content from already-downloaded PDFs (use pdf-extractor for that).
---

# Download

Given one or more DOIs, resolve the best available PDF and download to `./papers/` (or a user-specified directory).

## Workflow

1. Normalize DOIs: strip any leading `https://doi.org/` prefix.
2. Query Unpaywall to get `oa_status`, `host_type`, and `url_for_pdf`.
3. Choose download path using the Source Routing table.
4. Ensure output directory exists (`mkdir -p ./papers`).
5. Download with `curl`, then immediately verify magic bytes (`%PDF` = `25 50 44 46`).
6. If verification fails, delete the bad file and try the next source in the fallback chain.
7. Report result for each DOI.

## Source Routing

Work through this table top to bottom and stop at the first matching row:

| Condition | Download path |
|-----------|---------------|
| `url_for_pdf` non-null AND `host_type` is **repository/preprint** (arXiv, OSTI, institutional repo) — **except bioRxiv** | Direct curl — these always work |
| `url_for_pdf` is a **bioRxiv URL** | Try direct curl; if 403 → **Europe PMC preprint fallback** (see execution ref) |
| `url_for_pdf` non-null AND host is **Nature Communications** or other fully gold-OA publisher | Direct curl — gold OA links work |
| `url_for_pdf` points to **nature.com** AND year ≥ 2024 (Nature mandatory OA policy for funded research) | Try direct curl first — Nature mandatory OA papers download without session cookie |
| `url_for_pdf` is a **PMC link** (`pmc.ncbi.nlm.nih.gov`) | Use **PMC OA API** — PMC direct links return 1.8 KB access page, not PDF; API may return tar.gz instead of PDF (see execution ref) |
| `url_for_pdf` non-null AND `oa_status` is **bronze** OR `host_type` is **publisher** (Springer, ACS, RSC, Elsevier, Wiley…) | Skip direct download; go to **Sci-Hub** — publisher blocks curl without session cookie |
| `url_for_pdf` is null, `is_oa` is true | Try **Sci-Hub** |
| `is_oa` is false | Try **Sci-Hub**; if not found report `metadata_only` |

## Rules

- Default output directory: `./papers/` relative to current working directory.
- Always verify `%PDF` magic bytes after every download; delete and fall back if the check fails.
- Use `--max-time 180` for files that may exceed 10 MB (e.g. recent Nature papers can be 16–17 MB).
- Do not use `scidownl` or `papers-dl` — both are broken as of 2026 (outdated selectors/domain lists).
- Deduplicate DOIs before processing a batch.
- Process batches sequentially and emit a summary table only after all DOIs are handled.

## Output Labels

- `downloaded`: PDF saved to disk, magic-bytes verified; show local path.
- `landing_page_only`: OA page exists but no confirmed direct PDF; show URL.
- `metadata_only`: no OA path found anywhere; show DOI and `https://doi.org/{DOI}`.

## Load References

- Read [references/unpaywall_api.md](./references/unpaywall_api.md) for Unpaywall query syntax, JSON parsing gotchas, and resolution logic.
- Read [references/download_execution.md](./references/download_execution.md) for curl commands, file naming, magic-bytes check, Sci-Hub extraction, PMC OA API, and error handling.

## Output Shape

For a single DOI, report inline. For multiple DOIs, use a summary table:

| DOI | Status | Path / URL |
|-----|--------|-----------|
| 10.1038/... | downloaded | ./papers/smith_2021_title_slug.pdf |
| 10.1016/... | metadata_only | https://doi.org/10.1016/... |
