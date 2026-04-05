# Unpaywall API Reference

Unpaywall resolves DOIs to open-access PDF URLs. It is the primary resolver for this skill.

## Endpoint

```text
https://api.unpaywall.org/v2/{DOI}?email=gptase@proton.me
```

Replace `{DOI}` with the raw DOI (no `https://doi.org/` prefix).
Do NOT use `example.com` email — Unpaywall returns HTTP 422 for reserved domains.

## Example

```text
https://api.unpaywall.org/v2/10.1038/s41586-021-03819-2?email=gptase@proton.me
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

## Known Behaviors (empirically validated 2026-04)

| Situation | What Unpaywall returns | What actually works |
|-----------|------------------------|---------------------|
| Nature / Springer (bronze OA, pre-2024) | `url_for_pdf` points to publisher PDF | Publisher returns HTML paywall; use **Sci-Hub** |
| Nature papers with mandatory OA (2024–2025, `oa_status: hybrid`) | `url_for_pdf` = `nature.com/articles/....pdf`, `host_type: publisher` | Downloads directly despite `hybrid` status; may be 16–17 MB, use `--max-time 180` |
| Nature Communications (gold OA) | `url_for_pdf` = `nature.com/articles/....pdf` | Downloads directly |
| PMC-deposited biomedical papers | `url_for_pdf` = `pmc.ncbi.nlm.nih.gov/...` | Returns 1.8 KB access gate; use **PMC OA API** |
| PMC OA API — new or large papers | API XML contains `.tar.gz` link only, no direct PDF | Download tar.gz, extract main PDF (skip `si_` / `_si` supplementary files) |
| OSTI (U.S. DOE papers) | `url_for_pdf` = `osti.gov/servlets/purl/...` | Downloads directly, no auth needed |
| bioRxiv preprints | `url_for_pdf` = `biorxiv.org/content/....full.pdf` | Returns **HTTP 403** (Cloudflare); use **Europe PMC PPR fulltext API** instead |
| ACS / RSC / Elsevier / Wiley journals | `url_for_pdf` null or publisher URL | Use **Sci-Hub** |
| `is_oa: true` but `url_for_pdf` null | Only landing page registered | Try **Sci-Hub** |
| Very recent papers (2025, not yet in Sci-Hub) | — | Check PMC deposit or Europe PMC preprint mirror |
