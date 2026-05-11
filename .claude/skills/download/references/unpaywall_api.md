# Unpaywall API Reference

Unpaywall resolves DOIs to open-access PDF URLs. It is the primary resolver for this skill.

## Endpoint

```text
https://api.unpaywall.org/v2/{DOI}?email=YOUR_EMAIL
```

Replace `{DOI}` with the raw DOI (no `https://doi.org/` prefix).
Replace `YOUR_EMAIL` with a real contact address — Unpaywall's terms require a valid email and returns HTTP 422 for reserved domains like `example.com`. Using a shared/hardcoded address exhausts a single rate-limit quota for all users.

## Example

```text
https://api.unpaywall.org/v2/10.1038/s41586-021-03819-2?email=you@example.org
```

## JSON Parsing Gotcha

Unpaywall responses embed abstract text that often contains control characters (U+0000–U+001F),
which break both Python `json.load` and `jq`. Always strip them before parsing:

```bash
curl -s "https://api.unpaywall.org/v2/{DOI}?email=gptase@proton.me" \
  | tr -d '\000-\031' \
  | jq '{is_oa, oa_status, oa_locations: [.oa_locations[]? | {url_for_pdf, url, host_type}]}'
```

## Key Response Fields

| Field | Description |
|---|---|
| `is_oa` | Boolean — true if any OA version exists |
| `oa_status` | `gold`, `green`, `hybrid`, `bronze`, `closed` |
| `best_oa_location.url_for_pdf` | Best candidate PDF URL (may still require magic-bytes verification) |
| `best_oa_location.url` | OA landing page URL |
| `best_oa_location.host_type` | `publisher`, `repository`, `preprint` |
| `oa_locations` | Array of all OA locations; inspect when `best_oa_location` fails |
| `z_authors[0].family` | First author last name — often null; fall back to known metadata for file naming |
| `year` | Publication year |

## Resolution Logic

1. Strip control characters, parse with `jq`.
2. Check `is_oa`: if `false`, skip Unpaywall — no OA PDF registered.
3. Check `best_oa_location.url_for_pdf` and apply **Source Routing** from SKILL.md.
4. If `best_oa_location` fails, inspect `oa_locations` array for alternative entries.

## Known Behaviors (empirically validated 2026-04, refreshed 2026-05)

| Situation | What Unpaywall returns | What actually works |
|-----------|------------------------|---------------------|
| Nature / Springer (bronze OA, pre-2024) | `url_for_pdf` points to publisher PDF | Publisher returns HTML paywall; use **Sci-Hub** |
| Nature papers with mandatory OA (2024–2025, `oa_status: hybrid`) | `url_for_pdf` = `nature.com/articles/....pdf`, `host_type: publisher` | Downloads directly despite `hybrid` status; may be 16–17 MB, use `--max-time 180` |
| Nature Communications (gold OA) | `url_for_pdf` = `nature.com/articles/....pdf` | Downloads directly |
| ACS gold OA papers (JCTC, J Phys Chem, etc. — when individual articles are open) | `url_for_pdf` = `pubs.acs.org/doi/pdf/...` | Plain `curl` returns 403; `curl_cffi impersonate="chrome"` returns the real PDF |
| MDPI (`10.3390/...`) | `url_for_pdf` = `www.mdpi.com/.../pdf?version=...` | Plain `curl` returns 403; `curl_cffi impersonate="chrome"` returns the PDF |
| PMC-deposited biomedical papers | `url_for_pdf` = `pmc.ncbi.nlm.nih.gov/...` | Returns 1.8 KB access gate; use **PMC OA API** |
| **PMC NIH author manuscript** (`url_for_pdf` ends in `/pdf/nihms-NNNNNN.pdf`) | Looks like a direct PDF | **Returns access page, NOT a PDF**. OA API also responds `idIsNotOpenAccess`. Generally unrecoverable via automation. |
| PMC OA API — new or large papers | API XML contains `.tar.gz` link only, no direct PDF | Download tar.gz, extract main PDF (skip `si_` / `_si` supplementary files) |
| OSTI (U.S. DOE papers) | `url_for_pdf` = `osti.gov/servlets/purl/...` | Downloads directly, no auth needed |
| bioRxiv preprints | `url_for_pdf` = `biorxiv.org/content/....full.pdf` | Returns **HTTP 403** (Cloudflare); use **Europe PMC PPR fulltext API** instead |
| ACS / RSC / Elsevier / Wiley journals (paywalled) | `url_for_pdf` null or publisher URL | Use **Sci-Hub** (try `.box/.red` first, then `.ru/.sg/.st`) |
| **Unpaywall data-quality bug: image URL as "PDF"** | `url_for_pdf` = `ars.els-cdn.com/.../fx1_lrg.jpg` (an article figure) | Magic-bytes verification (`%PDF` = `25 50 44 46`) rejects it. Always verify; do not trust the `url_for_pdf` field alone. |
| `is_oa: true` but `url_for_pdf` null | Only landing page registered | Try **Sci-Hub** |
| Very recent papers (2023–2025, not yet in Sci-Hub) | — | Sci-Hub `no pdf link in body` (37-38 KB landing) means database miss; fall back to PMC deposit, Europe PMC preprint, or institutional access |

## Email requirement — hard fail mode

Unpaywall **rejects placeholder emails with HTTP 422 Unprocessable Entity**.
Verified rejected: `research@example.com`, `you@example.com`,
`test@example.org`. A real email is required to get *any* response — there
is no rate-limit pre-stage; the API simply refuses to answer. Use a real
address you own; if running on shared infrastructure, set it via
environment variable rather than hardcoding so one user's quota isn't
shared with everyone.
