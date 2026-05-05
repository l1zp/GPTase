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

## Supplementary Information Download

After downloading the main paper PDF, always attempt to fetch SI files.
SI download failure is **non-blocking** — never let it affect main paper status.

### Tool selection by publisher

Plain `curl` works for the easy half; the rest require `curl_cffi` (Cloudflare TLS-fingerprint bypass) and/or PMC's PoW solver.

| DOI prefix / host | Tool | Notes |
|---|---|---|
| `10.1038/...` (Nature/Springer) | bash + `curl` | Scrape landing for `static-content.springer.com/esm/...`; or probe `_MOESM{N}_ESM.{pdf,zip}` |
| `10.1039/...` (RSC) | bash + `curl` | Pattern: `https://www.rsc.org/suppdata/{ab}/{journal}/{base}/{base}{N}.pdf`, N=1.. until 404 |
| `10.1101/...` (bioRxiv) | bash + `curl` | UA + Referer headers required; landing at `.../v1.supplementary-material` lists `/DC1/embed/media-*` |
| `10.1021/...` (ACS) | `scripts/si_download.py` (curl_cffi) | **SI files are NOT paywalled** — only the article body. `curl_cffi impersonate="chrome"` defeats Cloudflare and the SI PDFs return directly. |
| `10.1073/...` (PNAS pre-2014) | `scripts/si_download.py` (curl_cffi + PMC PoW) | Older PNAS papers gated; PMC has them under `/articles/instance/<num>/bin/` behind a SHA-256 hashcash |
| Any DOI with PMC entry | `scripts/si_download.py` (PMC OA tarball) | Sanctioned path: `oa.fcgi` → `https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/oa_package/...tar.gz` (note `deprecated/` — NCBI moved it) |

### Quick decision flow

1. Run bash discovery (HTML scrape) on the article landing page. If `/doi/suppl/`, `static-content.springer.com/esm/`, or `mmc[0-9]+` links appear, try direct `curl` first.
2. If direct curl returns 403, HTML, or the magic bytes are wrong → switch to `python .claude/skills/download/scripts/si_download.py <DOI> <out_dir>` which handles every publisher in one call.
3. If the article landing has **no** SI links and direct SI URL returns 302 to `/doi/abs/...` → conclude SI was not published (don't keep retrying).

### File naming

`SI_{original_filename}` (preserve publisher's filename so PMC/ACS files keep their `_si_001.pdf`, `_MOESM2_ESM.xlsx`, etc. suffix). For sequential probes use `SI_{base}{N}.pdf`.

### Magic-bytes

Verify `%PDF` (25 50 44 46) for PDFs, `PK` (50 4B) for ZIPs, `\x1f\x8b\x08` (gzip) for `.tar.gz`. Anything starting with `<!DOCTYPE`, `<html`, `\n\n\n`, or null bytes is an error page — delete and try the next path.

See [references/si_anti_bot.md](./references/si_anti_bot.md) for the publisher-mechanism table, the PMC OA-package path migration gotcha, and how to distinguish "no SI" from "blocked".

## Output Labels

- `downloaded`: PDF saved to disk, magic-bytes verified; show local path.
- `landing_page_only`: OA page exists but no confirmed direct PDF; show URL.
- `metadata_only`: no OA path found anywhere; show DOI and `https://doi.org/{DOI}`.
- `si_downloaded`: SI file(s) saved and verified; show local path(s).
- `si_not_found`: SI discovery attempted but no SI files found or all downloads failed.

## Load References

- Read [references/unpaywall_api.md](./references/unpaywall_api.md) for Unpaywall query syntax, JSON parsing gotchas, and resolution logic.
- Read [references/download_execution.md](./references/download_execution.md) for curl commands, file naming, magic-bytes check, Sci-Hub extraction, PMC OA API, and error handling.
- Read [references/si_anti_bot.md](./references/si_anti_bot.md) for SI download under publisher anti-bot stacks (ACS Cloudflare, PMC PoW, etc.) and how to use `scripts/si_download.py`.

## Output Shape

For a single DOI, report inline. For multiple DOIs, use a summary table:

| DOI | Status | Path / URL |
|-----|--------|-----------|
| 10.1038/... | downloaded | ./papers/smith_2021_title_slug.pdf |
| 10.1016/... | metadata_only | https://doi.org/10.1016/... |
