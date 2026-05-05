# Download Execution Reference

## File Naming Convention

Format: `{first_author_lastname}_{year}_{title_slug}.pdf`

Rules:
- `first_author_lastname`: lowercase last name from Unpaywall `z_authors[0].family`; often null — fall back to known first author from search metadata, or use `unknown`
- `year`: 4-digit publication year
- `title_slug`: first 4–5 meaningful words from title, joined by underscores, lowercase, non-alphanumeric removed
- Truncate total filename to 80 characters before `.pdf`

Examples:
- Author Röthlisberger, year 2008, title "Kemp elimination catalysts by computational enzyme design"
  → `rothlisberger_2008_kemp_elimination_catalysts.pdf`
- No author resolved, year 2021, title "Fast distributed training for large models"
  → `unknown_2021_fast_distributed_training.pdf`

## Directory Setup

```bash
mkdir -p ./papers
```

## Standard curl Download

Use for direct OA sources (arXiv, OSTI, Nature Comm gold OA, recent Nature mandatory OA):

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

curl -L \
  -A "$UA" \
  --max-time 90 \
  -o "./papers/{filename}.pdf" \
  "{pdf_url}" \
  -w "HTTP:%{http_code} SIZE:%{size_download}\n"
```

For files that may exceed 10 MB (e.g. recent Nature papers with extended data can reach 16–17 MB), use `--max-time 180`.

## Magic-Bytes Verification

Always run immediately after curl:

```bash
head -c 4 ./papers/{filename}.pdf | xxd
```

Valid PDF: `25 50 44 46` (ASCII `%PDF`).
Failure signatures:
- `3c 21 44 4f` = `<!DO` → HTML paywall page (publisher blocked download)
- `0a 0a 0a 0a` = null bytes → PMC access gate (~1.8 KB)
- 0 bytes → network failure

On failure: delete the file and proceed to next source in the fallback chain.

## Error Handling

| Situation | Action |
|---|---|
| curl exits non-zero | Report download failed; show curl error |
| Magic bytes are HTML | Delete file; try Sci-Hub |
| Magic bytes are null / 0 bytes | Delete file; try PMC OA API or Sci-Hub |
| Sci-Hub PDF_PATH empty | Paper not in Sci-Hub; report `metadata_only` |

---

## Source 1: Direct curl (repository / gold OA)

Works for: arXiv, OSTI (`osti.gov`), Nature Communications, Nature (≥2024 mandatory OA), institutional repositories. Note: bioRxiv now returns 403 — use **Source 3** instead.

```bash
curl -L -A "$UA" --max-time 90 -o "./papers/{filename}.pdf" "{url_for_pdf}" \
  -w "HTTP:%{http_code} SIZE:%{size_download}\n"
```

Then verify magic bytes.

---

## Source 2: PMC OA API (for PMC-deposited papers)

Use when Unpaywall returns a PMC URL or when `pmcid` is known. Do NOT use the PMC web URL directly — it returns a 1.8 KB access page.

**Step 1 — Get PMCID** (if not already known):

```bash
curl -s "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:{DOI}&format=json" \
  | jq -r '.resultList.result[0].pmcid'
```

**Step 2 — Get real PDF path from PMC OA API**:

```bash
RAW_XML=$(curl -s "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={PMCID}")
PDF_URL=$(echo "$RAW_XML" | grep -oiE 'href="ftp://[^"]*\.pdf"' | sed 's/href="ftp:/https:/;s/"$//')
TGZ_URL=$(echo "$RAW_XML" | grep -oiE 'href="ftp://[^"]*\.tar\.gz"' | sed 's/href="ftp:/https:/;s/"$//')
echo "PDF URL: $PDF_URL"
echo "TGZ URL: $TGZ_URL"
```

The API may return either a direct `.pdf` link OR a `.tar.gz` package — check both.

**Step 3a — Direct PDF**:

If `PDF_URL` is non-empty:

```bash
curl -L -A "$UA" --max-time 90 -o "./papers/{filename}.pdf" "$PDF_URL" \
  -w "HTTP:%{http_code} SIZE:%{size_download}\n"
```

**Step 3b — tar.gz package** (fallback when no direct PDF):

If only `TGZ_URL` is available:

```bash
curl -L -A "$UA" --max-time 90 -o "/tmp/{pmcid}.tar.gz" "$TGZ_URL" \
  -w "HTTP:%{http_code} SIZE:%{size_download}\n"
mkdir -p /tmp/{pmcid}_extract
tar -xzf /tmp/{pmcid}.tar.gz -C /tmp/{pmcid}_extract
MAIN_PDF=$(find /tmp/{pmcid}_extract -name "*.pdf" | grep -v "si_" | grep -v "_si" | head -1)
cp "$MAIN_PDF" "./papers/{filename}.pdf"
rm -rf /tmp/{pmcid}_extract /tmp/{pmcid}.tar.gz
```

Skip supplementary files: they typically contain `_si` or `si_` in the filename.

Then verify magic bytes.

---

## Source 3: Europe PMC (preprint fallback for bioRxiv 403)

bioRxiv direct PDF downloads now return **HTTP 403** due to Cloudflare challenges. Europe PMC mirrors most bioRxiv preprints and serves them without restriction.

**Step 1 — Find PPR ID via Europe PMC search**:

```bash
curl -s "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:{PREPRINT_DOI}&format=json&resultType=core" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d.get('resultList', {}).get('result', [])[:1]:
    ftl = r.get('fullTextUrlList', {}).get('fullTextUrl', [])
    for ft in ftl:
        if ft.get('documentStyle') == 'pdf':
            print(ft.get('url'))
"
```

**Step 2 — Download from Europe PMC**:

```bash
curl -L -A "$UA" --max-time 90 \
  -o "./papers/{filename}.pdf" \
  "{europe_pmc_pdf_url}" \
  -w "HTTP:%{http_code} SIZE:%{size_download}\n"
```

The Europe PMC PDF URL pattern for preprints looks like:
`https://europepmc.org/api/fulltextRepo?pprId={PPR_ID}&type=FILE&fileName={EMS_ID}-pdf.pdf&mimeType=application/pdf`

Then verify magic bytes.

---

## Source 4: Sci-Hub (publisher-paywalled papers)

Use when: publisher host_type, bronze OA, or all other sources failed.

**Do not use `scidownl` or `papers-dl`** — both are broken as of 2026:
- `scidownl` uses CSS selector `#pdf` which no longer exists in Sci-Hub's HTML
- `papers-dl` has a stale domain list; most domains are DNS-unreachable

Use direct curl extraction instead.

### Step 1 — Extract PDF path from Sci-Hub page

Sci-Hub embeds the PDF link as `href = "/storage/..."` in the page HTML:

```bash
SCIHUB_BASE="https://sci-hub.sg"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

PDF_PATH=$(curl -s --max-time 20 -A "$UA" "${SCIHUB_BASE}/{DOI}" \
  | grep -oiE 'href = "/storage/[^"]*\.pdf"' \
  | sed 's/href = "//;s/"$//')
echo "PDF_PATH: $PDF_PATH"
```

If `PDF_PATH` is empty: paper is not in Sci-Hub → report `metadata_only`.

### Step 2 — Download

```bash
curl -L --max-time 90 -A "$UA" \
  "${SCIHUB_BASE}${PDF_PATH}" \
  -o "./papers/{filename}.pdf" \
  -w "HTTP:%{http_code} SIZE:%{size_download}\n"
```

Then verify magic bytes.

### Known working Sci-Hub domains (2026-04)

| Domain | Notes |
|--------|-------|
| `https://sci-hub.sg` | Primary — `sci-hub.ru` redirects here |
| `https://sci-hub.ru` | Redirects to sci-hub.sg |
| `https://sci-hub.st` | Secondary fallback |

Dead domains (DNS unreachable): `sci-hub.se`, `sci-hub.vk`, `sci-hub.ga`, `sci-hub.si`, `sci-hub.ooo`

**Domain freshness note:** Sci-Hub domains rotate every few months. If all listed domains return DNS failure or a non-PDF HTML page, check the current active domain at https://sci-hub.now.sh/ (redirector maintained by the community). Verify any new domain with a known DOI before using it in a batch run. Do NOT add `.se`, `.vk`, `.ga`, `.si`, or `.ooo` variants — these have been dead since 2023.

---

## Source 5: Supplementary Information

Run after the main paper download completes. SI download failure is non-blocking.

### Decision tree

```
DOI prefix
 ├─ 10.1038 (Nature/Springer) ─→ bash curl + scrape `static-content.springer.com/esm/...`
 ├─ 10.1039 (RSC)             ─→ bash curl + probe `/suppdata/{ab}/{j}/{base}/{base}{N}.pdf`
 ├─ 10.1101 (bioRxiv)         ─→ bash curl + scrape `.../v1.supplementary-material`
 └─ 10.1021 (ACS), 10.1073 (PNAS)
                              ─→ Python `scripts/si_download.py` (curl_cffi + PMC PoW)
```

For the bash-friendly publishers (Nature/RSC/bioRxiv) the legacy steps below
are still the right tool. For ACS/PNAS/PMC, hand off to the Python helper —
plain `curl` will hit Cloudflare 403 or PMC's JS proof-of-work page.

### Step 1 — HTML scraping (Nature/Springer/bioRxiv/Elsevier)

```bash
PAGE_HTML=$(curl -s --max-time 30 -A "$UA" "https://doi.org/{DOI}")

# Nature/Springer: look for static-content.springer.com/esm/ links
SI_URLS=$(echo "$PAGE_HTML" \
  | grep -oiE 'https://static-content\.springer\.com/esm/[^"'\''> ]+\.(pdf|zip|docx|xlsx)' \
  | sort -u)

# Elsevier: look for mmc*.pdf / mmc*.zip supplementary links
if [ -z "$SI_URLS" ]; then
  SI_URLS=$(echo "$PAGE_HTML" \
    | grep -oiE 'https://[^"'\''> ]+mmc[0-9]+\.(pdf|zip)' \
    | sort -u)
fi
```

### Step 2 — URL pattern probing (fallback for Nature/Springer)

```bash
ENCODED_DOI=$(python3 -c "import urllib.parse; print(urllib.parse.quote('{DOI}', safe=''))")
SI_BASE="https://static-content.springer.com/esm/art%3A${ENCODED_DOI}/MediaObjects"

for N in 1 2 3; do
  for EXT in pdf zip xlsx docx; do
    PROBE_URL="${SI_BASE}/_MOESM${N}_ESM.${EXT}"
    HTTP_CODE=$(curl -s --max-time 15 -A "$UA" -o /dev/null -w "%{http_code}" "$PROBE_URL")
    if [ "$HTTP_CODE" = "200" ]; then
      SI_URLS="$SI_URLS $PROBE_URL"
    fi
  done
done
```

### Step 3 — RSC pattern (10.1039)

RSC's SI files live at a deterministic path. Loop until the first 404:

```bash
BASE=$(echo "{DOI}" | cut -d/ -f2 | tr 'A-Z' 'a-z')   # e.g. d0sc01935f
AB=${BASE:0:2}
JOURNAL=$(echo "$BASE" | sed -E 's/^[a-z][0-9]*([a-z]+)[0-9].*/\1/')
for N in 1 2 3 4 5; do
  URL="https://www.rsc.org/suppdata/${AB}/${JOURNAL}/${BASE}/${BASE}${N}.pdf"
  HTTP_CODE=$(curl -s --max-time 15 -A "$UA" -o /dev/null -w "%{http_code}" "$URL")
  [ "$HTTP_CODE" = "200" ] && SI_URLS="$SI_URLS $URL" || break
done
```

### Step 4 — bioRxiv pattern (10.1101)

```bash
SUFFIX=$(echo "{DOI}" | cut -d/ -f2-)
LANDING="https://www.biorxiv.org/content/10.1101/${SUFFIX}v1.supplementary-material"
SI_URLS=$(curl -sL --compressed -A "$UA" -H "Referer: https://www.biorxiv.org/" "$LANDING" \
  | grep -oiE 'https://www\.biorxiv\.org/content/biorxiv/early/[^"]*/DC1/embed/[^"]+\.(pdf|zip|xlsx)')
```

### Step 5 — ACS/PNAS/PMC via Python helper

```bash
python /Users/ryanxu/CodeBase/GPTase/.claude/skills/download/scripts/si_download.py \
    "{DOI}" "{out_dir}"
```

The helper:
1. Tries direct ACS scrape (`/doi/suppl/{DOI}/suppl_file/...`) — works for most ACS papers; the SI files are not paywalled even though the article is.
2. Falls back to NCBI ID converter + PMC OA tarball (`deprecated/oa_package/<ab>/<cd>/PMCxxx.tar.gz`).
3. Falls back to PMC `/articles/instance/<num>/bin/<file>` with PoW solver for non-OA NIH author manuscripts.

Output to stdout: one local path per saved SI file. Exit code 2 if no SI found.

### Step 6 — Download each scraped/probed URL (bash path)

```bash
for SI_URL in $SI_URLS; do
  FNAME=$(basename "${SI_URL%%\?*}")
  OUT="${OUT_DIR}/SI_${FNAME}"
  curl -L --max-time 180 -A "$UA" -o "$OUT" "$SI_URL" \
    -w "HTTP:%{http_code} SIZE:%{size_download}\n"

  # Magic-bytes verification
  HEAD=$(head -c 4 "$OUT" | xxd -p)
  case "$HEAD" in
    25504446*) echo "  [OK] PDF $OUT" ;;       # %PDF
    504b0304*) echo "  [OK] ZIP $OUT" ;;       # PK\x03\x04
    *) echo "  [FAIL] bad magic for $OUT"; rm -f "$OUT" ;;
  esac
done
```

### Step 7 — Report

- Label `si_downloaded` and list paths if at least one file passes magic-bytes.
- Label `si_not_found` if discovery returned no URLs OR all downloads failed.
- For ACS landing page with no `/doi/suppl/` link AND a 302 redirect on direct probe → conclude SI was never published; report `si_not_found` with a note "no SI published".

---

## Complete Fallback Chain

```
DOI
 └─> Unpaywall (strip control chars with tr -d '\000-\031' before jq)
      ├─> host = repository/arXiv/OSTI/gold-OA publisher (NOT bioRxiv)
      │    └─> Direct curl → verify → DONE
      ├─> host = bioRxiv
      │    └─> Direct curl → verify → DONE
      │         └─> 403 → Europe PMC PPR search → Europe PMC PDF → verify → DONE
      │                    └─> not found → Sci-Hub → verify → DONE
      ├─> host = nature.com AND year 2024-2025+ (mandatory OA)
      │    └─> Direct curl → verify → DONE
      │         └─> 403/HTML → Sci-Hub → verify → DONE
      ├─> host = PMC URL
      │    └─> PMC OA API → direct PDF URL → curl → verify → DONE
      │         └─> only tar.gz → download tar.gz → extract main PDF → verify → DONE
      ├─> host = publisher (bronze/hybrid, non-Nature) OR url_for_pdf null
      │    └─> Sci-Hub: fetch page → grep href="/storage/..." → curl → verify
      │         └─> PDF_PATH empty → metadata_only
      └─> is_oa false
           └─> Sci-Hub → same as above
```

## Batch Processing

Process DOIs sequentially. Do not use bash associative arrays with dots in keys (e.g. `10.1038/...`) — bash silently drops them. Use positional arrays or pipe-delimited strings instead:

```bash
for ENTRY in "10.1038/doi1|author_year_title" "10.1021/doi2|author_year_title2"; do
  DOI="${ENTRY%|*}"
  FNAME="${ENTRY#*|}"
  # ... download logic
done
```

Collect results, then emit the summary table after all DOIs finish.
