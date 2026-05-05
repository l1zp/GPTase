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
| `pmc.ncbi.nlm.nih.gov` (PMC web UI binaries) | NCBI in-house JS proof-of-work — SHA-256 hashcash, difficulty 4, cookie name `cloudpmc-viewer-pow` | `scripts/pmc_pow.py` — solves in milliseconds, sets `<challenge>,<nonce>` cookie, retries the request |
| `europepmc.org/.../ptpmcrender.fcgi` | TLS-fingerprint filter — kills HTTP/2 stream mid-handshake on non-browser clients | Avoid; use Europe PMC REST API or NCBI tarball instead. `curl_cffi` *may* work but the tarball path is more reliable. |
| `www.biorxiv.org` (lax Cloudflare) | Cloudflare scoring with permissive thresholds | Real Chrome User-Agent + `Referer: https://www.biorxiv.org/` is enough; no fingerprint forgery needed |

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
