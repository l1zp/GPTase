# SI Download Reference: Bypassing Publisher Anti-Bot Stacks

When direct `curl` cannot fetch a Supporting Information file, identify
which anti-bot stack is in front of the file and pick the right tool.
This page is the operational complement to Source 5 in
`download_execution.md`.

## Per-publisher mechanism table

| Publisher / host | Anti-bot stack (2026) | Defeat with |
|---|---|---|
| `pubs.acs.org` (ACS) | Cloudflare Bot Management — TLS JA3/JA4 + HTTP/2 SETTINGS + UA client-hints challenge (`cf-mitigated: challenge`) | `curl_cffi` with `impersonate="chrome"`. **The SI file URL itself is NOT paywalled** — only the article body is. Once Cloudflare passes you, `_si_001.pdf` returns directly. |
| `www.pnas.org` (PNAS, pre-2014 layout) | Same Cloudflare stack as ACS | `curl_cffi` plus a PMC fallback for SI: older PNAS papers expose SI under `/articles/instance/<num>/bin/<file>` on PMC |
| `onlinelibrary.wiley.com` (Wiley) | Cloudflare Bot Management — **TLS fingerprint blocklist explicitly rejects Chrome variants**, accepts Firefox | `curl_cffi` with `impersonate="firefox"` returns 200 + 327 KB landing; `impersonate="chrome"` / `chrome120` / `chrome116` / `edge` / `safari` all return 403 + ~6 KB. SI URL pattern: `/action/downloadSupplement?doi={ENCODED_DOI}&file={NAME}-sup-NNNN-suppl-data.pdf`. Filename only on the landing — must scrape. **Even Playwright + non-headless real Chrome + `--disable-blink-features=AutomationControlled` + stealth init script (mask `navigator.webdriver`, `plugins`, `languages`) gets the persistent "Just a moment..." challenge page — Wiley sits on Cloudflare's enterprise Bot Management tier, which requires paid stealth services (`patchright`, `botasaurus`, residential proxies) to defeat reliably.** |
| `www.sciencedirect.com` (Elsevier) | Cloudflare Bot Management — even stricter than Wiley | `linkinghub.elsevier.com` is a 2.7 KB gateway that JS-redirects to ScienceDirect. ScienceDirect returns HTTP 403 with an ~835 KB **fake-content block page** to `curl_cffi` (all profiles incl. Firefox). Playwright + real Chrome gets past the initial gate, **but the "Supplementary data" section is rendered asynchronously via XHR after a DOM click** — SI URLs are NOT in the initial HTML. Recovering Elsevier SI automation-only requires: Playwright navigate → wait for hydration → `page.click('button:has-text("Supplementary data")')` → intercept XHR responses for `ars.els-cdn.com` URLs → fetch each. Substantial engineering; consider falling back to manual download via institutional access. |
| `www.mdpi.com` (MDPI) | Cloudflare standard (no Bot Management) | `curl_cffi` with `impersonate="chrome"` retrieves landing on most networks; some flagged IPs still get 403. MDPI SI is usually packaged as a single ZIP at `/{journal}/{vol}/{issue}/{art}/s1`. |
| `pmc.ncbi.nlm.nih.gov` (PMC web UI binaries) | NCBI in-house JS proof-of-work — SHA-256 hashcash, difficulty 4, cookie name `cloudpmc-viewer-pow` | `scripts/pmc_pow.py` — solves in milliseconds, sets `<challenge>,<nonce>` cookie, retries the request |
| `pmc.ncbi.nlm.nih.gov/articles/PMC.../pdf/nihms-*.pdf` (NIH author manuscript) | OA API returns `<error code="idIsNotOpenAccess"/>`; PoW won't help for NIHMS deposits | Generally unrecoverable through automation — these are deposited author manuscripts behind PMC's web gate. Manual download via PMC viewer is the practical path. |
| `europepmc.org/.../ptpmcrender.fcgi` | TLS-fingerprint filter — kills HTTP/2 stream mid-handshake on non-browser clients | Avoid; use Europe PMC REST API or NCBI tarball instead. `curl_cffi` *may* work but the tarball path is more reliable. |
| `www.biorxiv.org` (lax Cloudflare) | Cloudflare scoring with permissive thresholds | Real Chrome User-Agent + `Referer: https://www.biorxiv.org/` is enough; no fingerprint forgery needed |

## Cloudflare Bot Management ceiling

`curl_cffi` defeats *standard* Cloudflare TLS fingerprint scoring (the
free tier most publishers use). It does **not** defeat the **enterprise
Bot Management** tier, which adds behavioural fingerprinting on top:

- Wiley and Elsevier are on this tier (verified 2026-05).
- Symptom: Playwright + headless Chrome → persistent "Just a moment..."
  challenge that never auto-solves; non-headless Chrome with stealth
  init scripts gets the same result.
- This means any automation attempt against `onlinelibrary.wiley.com`
  or `www.sciencedirect.com` from a flagged IP is effectively capped at
  the gateway. When this happens, label the SI as `si_not_found` rather
  than burning time iterating — the realistic recovery path is manual
  browser download through an institutional proxy.

## TLS profile selection cheat-sheet

| Target host | Best `impersonate=` value |
|---|---|
| ACS `pubs.acs.org` | `chrome` |
| Wiley `onlinelibrary.wiley.com` | **`firefox`** (chrome variants 403) |
| Elsevier `www.sciencedirect.com` | `firefox` likely; expect static HTML to still be a CF block page |
| MDPI `www.mdpi.com` | `chrome` |
| Sci-Hub `.box` / `.red` mirrors | `chrome` |
| PMC `pmc.ncbi.nlm.nih.gov` | `chrome` + PoW solver |

## Distinguish "no SI" from "blocked"

Before assuming SI is blocked, confirm SI actually exists:

| Probe | Meaning |
|---|---|
| Article landing page contains `/doi/suppl/...` link → 200 PDF on direct fetch | SI exists, accessible — happy path |
| Article landing page contains `/doi/suppl/...` link → 403 / HTML on direct fetch | SI exists, blocked by Cloudflare → use `curl_cffi` |
| Article landing page contains `/doi/suppl/...` link → 302 to `/doi/abs/...` redirect | **Article SI not published** (e.g. `10.1021/ja804040s` — alexandrova_2008) |
| Article landing page has no `/doi/suppl/` mention | SI was not published with this article (many Perspectives, Editorials) |

`curl_cffi` follows redirects by default; pass `allow_redirects=False` when
probing so you can see the 302 vs 200 vs 403 verdict.

## Tooling: when to use each

**Plain bash `curl`** — works for:
- Nature/Springer (`static-content.springer.com/esm/...`)
- RSC suppdata
- bioRxiv (with Chrome UA + Referer)
- Direct Europe PMC supplementary REST endpoint

**Python with `curl_cffi`** — required for:
- ACS (`pubs.acs.org`)
- PNAS legacy URLs
- PMC OA tarball download (the `deprecated/oa_package/` HTTPS path works with curl too, but Python is convenient for tar extraction)

**`curl_cffi` + PMC PoW solver** — required for:
- `pmc.ncbi.nlm.nih.gov/articles/instance/<num>/bin/<file>` paths (NIH author manuscripts, paywalled-original PNAS papers)

Install once:
```bash
pip install curl_cffi
```

## Unified Python entry point

`scripts/si_download.py` dispatches by DOI prefix and tries the right path
in order. Use it when more than one or two SI files need to be retrieved
or when the publisher is uncertain:

```bash
python .claude/skills/download/scripts/si_download.py \
    10.1021/jacs.6b12265 \
    papers/bhowmick_2017_scaffold_de_novo_kemp/
```

Output is one local path per saved SI file (or `(no SI files found)` on stderr).

## PMC OA package path migration (gotcha)

`oa.fcgi` still returns the legacy URL:

```
ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/<ab>/<cd>/<PMCID>.tar.gz
```

But the directory has been **moved** to `/deprecated/oa_package/`. The
HTTPS rewrite needed:

```
https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/oa_package/<ab>/<cd>/<PMCID>.tar.gz
```

`scripts/si_download.py::is_pmc_oa()` performs this substitution. Without
it the FTP path returns 550 and the HTTPS path returns 404.

## When even PMC says "not OA"

`oa.fcgi?id=PMCxxxxx` returns `<error code="idIsNotOpenAccess"/>` for many
NIH author manuscripts and pre-2014 PNAS papers. The article HTML may
still link to SI under `/articles/instance/<num>/bin/<file>`, but only the
PoW-protected PMC web UI will serve it. Use the PoW solver path in that
case.

## ACS-specific notes

1. The article landing at `https://pubs.acs.org/doi/{DOI}` is the
   authoritative source of SI URLs — scrape it rather than guessing
   filenames.
2. SI URL pattern: `https://pubs.acs.org/doi/suppl/{DOI}/suppl_file/{NAME}_si_{NN}.pdf`
   where `{NAME}` is the journal+article suffix (e.g. `ja6b12265`,
   `cs501904w`, `ja4c09428`).
3. ACS papers without SI (e.g. older articles, Communications, Letters)
   simply don't have a `<a href="/doi/suppl/...">` block on the landing.
   Don't waste cycles guessing — if the landing has no SI link, the SI
   doesn't exist.

## Cookie warm-up

For all `curl_cffi` paths, fetch the article landing page first so
Cloudflare's `__cf_bm` cookie (and ACS's `JSESSIONID`/`MAID` cookies) are
populated before you request the SI. The Python helper does this.

## Verification (always)

After download, check magic bytes:
- `%PDF` (`25 50 44 46`) for PDFs
- `PK\x03\x04` (`50 4B 03 04`) for ZIPs
- `\x1f\x8b\x08\x00` (gzip) for `.tar.gz` packages

Anything starting with `<!DOCTYPE`, `<html`, or `\x00\x00\x00\x00` is an
error page and should be deleted before falling back.
