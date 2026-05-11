---
name: academic-search
description: |
  Search and collect academic papers via OpenAlex, Semantic Scholar, Crossref, and Europe PMC. Two modes — pick by user intent:

  (1) SINGLE-PAPER / METADATA: known-paper lookup, DOI metadata, citation counts, author search, journal/source filtering, recent or highly cited publications, biomedical (PMID/PMCID) retrieval, "find this one paper", "look up this DOI".

  (2) CORPUS BUILDING: grow or audit a deduplicated DOI list around a narrow topic via multi-engine keyword harvest + 1-hop citation graph expansion (referenced_works AND incoming citations) + year-by-year backward sweep, with cold-start recall validation.

  ALWAYS trigger when the user wants ANY of: papers, articles, literature, DOI lookup, citation counts, "find all papers about X", "expand my paper list", "augment this CSV with related papers", "literature collection / harvest / sweep / coverage audit", "build a paper bibliography", "verify CSV is complete", "穷举某个领域的论文", "尽可能多搜索...的文献", "扩充文献库", "补全 DOI 列表", "审查文献覆盖". Trigger even when the user only mentions DOIs, Crossref, OpenAlex, citation graph, "find related work", or wants to know if a corpus is comprehensive — those are usually downstream of corpus-building.

  Do NOT use for: biochemical database lookups about reactions, proteins, compounds, pathways (use biochem_databases); reading PDF content (use pdf-extractor); narrative literature-review *writing* where the user wants prose, not a list.
---

# Academic Search

This skill operates in **two modes**. Decide which mode applies *before* calling any API.

| Signal | Mode |
|---|---|
| User asks for ONE paper, a DOI lookup, "find me X paper", citation count, author search, recent papers, "papers in journal Y", PMID lookup | **Mode 1 — Single-paper / metadata** |
| User asks to "find all papers about X", expand/augment a CSV, audit a corpus, sweep a topic, build a paper list, verify coverage | **Mode 2 — Corpus building** |
| Ambiguous (e.g. "find papers about Kemp eliminase") | Ask: "Do you want a few top hits or to harvest the topic?" |

The two modes share API endpoints (OpenAlex / Crossref / Europe PMC / Semantic Scholar) but use them very differently. Mode 1 is *narrow → small results → polish output*. Mode 2 is *broad → many results → filter, dedupe, validate*.

---

# Mode 1 — Single-paper / metadata lookup

Use this mode whenever the user is identifying ONE paper, doing DOI metadata work, or running a standard literature query that produces a small ranked list (≤25 hits).

## Routing

1. Classify the request:
   - DOI metadata, publisher metadata, license, funder → **Crossref**
   - Biomedical or PMID/PMCID-centric literature → **Europe PMC**
   - Citation-ranked general literature or journal/source filtering → **OpenAlex**
   - Quick known-paper lookup or one-paper detail → **Semantic Scholar SDK** first, then OpenAlex
2. Two-step workflow for one specific paper:
   - Search small first, typically 3–10 hits.
   - Inspect only the best hit in detail.
3. Fall back in this order:
   - Semantic Scholar rate-limited or unavailable → OpenAlex
   - Missing or inconsistent DOI metadata → Crossref
4. Keep the first request narrow. Add only the filters and fields the user actually needs.
5. Optimize for search coverage and result correctness first, not downloadability.
6. After selecting the correct result set, enrich with download or full-text links when available.
7. Return compact, human-readable results instead of raw API payloads.
8. For known-paper lookup, compare top hits by title similarity, year plausibility, venue, and DOI before accepting the first result.

## Response rules

- Treat `abstract_inverted_index` as an encoded structure, not readable text.
- Request only the fields you need first; expand to richer metadata only after you have the correct paper or narrowed result set.
- Include caveats when a field is missing (DOI, abstract, OA URL).
- If the user wants downloads or full text, treat that as a second-pass enrichment step after identifying the right papers.
- If the user asks for "latest" or "recent", sort by `publication_date:desc` and surface exact dates.
- For biomedical searches, prefer Europe PMC over generic engines unless asked otherwise.
- For "recent biomedical papers with citation counts", state the tradeoff: the newest papers may legitimately have zero citations.
- For DOI validation or publication metadata cleanup, prefer Crossref.
- If the request mixes literature search with biochemical entities, follow user intent:
  - "Find papers about EC 1.1.1.1" → use this skill.
  - "What reaction does EC 1.1.1.1 catalyze?" → use `biochem_databases`, not this skill.
- When identifying one known paper, include stable identifiers: OpenAlex work ID, DOI, landing page URL.
- Handle Semantic Scholar `429 Too Many Requests` by falling back to OpenAlex, not retry-spamming.
- Reject obviously implausible variants of canonical papers (e.g., a much newer preprint when title/venue/year suggest an older publication).
- Label download availability explicitly: `direct_pdf`, `oa_fulltext`, `landing_page_only`, `metadata_only`.

## Output shape (Mode 1)

- Default to a short table or bullet list.
- Include title plus only the requested metadata: authors, year, journal, DOI, citations, abstract.
- For ranked requests, preserve the requested ordering and state the ranking basis.
- For single-paper identification, prefer:
  - title, year, top authors, citation count, DOI or work URL, short abstract snippet (only if asked).

## Mode 1 references

- [references/router.md](./references/router.md) — backend selection when the choice isn't obvious
- [references/openalex_api.md](./references/openalex_api.md) — OpenAlex filters, source routing, abstract reconstruction
- [references/semanticscholar_sdk.md](./references/semanticscholar_sdk.md) — Semantic Scholar SDK + rate-limit behavior
- [references/crossref_api.md](./references/crossref_api.md) — DOI / publisher metadata workflows
- [references/europe_pmc_api.md](./references/europe_pmc_api.md) — biomedical patterns, PMID/PMCID
- [references/download_enrichment.md](./references/download_enrichment.md) — full-text / PDF / download links

---

# Mode 2 — Corpus building

Use this mode whenever the user wants to **build, grow, or audit a corpus** — a deduplicated DOI list around a narrow scientific topic. Output is an updated CSV that includes at minimum a `name` column and a `doi` column, where `name` follows `firstauthor_year_keywords` (snake_case ASCII). Extra tracking columns (e.g. `main_downloaded`, `si_downloaded`, `notes`) are preserved on read and ignored for matching — the scripts use `csv.DictReader` and only look at the `doi` field.

## Why this mode exists

Naïve one-shot searches reliably miss two classes of papers:

- Papers whose **title doesn't contain** your topic keyword (e.g., "Designer enzyme" papers about Kemp eliminase)
- Papers whose **citation pattern** reveals topic membership even when wording differs

Mode 2 addresses both by combining keyword-first and graph-first techniques, then *measures* coverage via cold-start recovery. On a real corpus of 73 Kemp eliminase papers, recall reached 100% (73/73) with keyword search alone once the topic spec covered variant identifiers as their own queries (e.g., `KE07`, `HG3.17`, `AlleyCat`) — citation graph is *insurance*, not the main signal. For broader or less keyword-uniform topics, expect the citation-pool path to contribute 5-15% of recall.

## The 4-stage pipeline

### Stage 1 — Multi-engine keyword harvest (always run)

Run 5-8 parallel queries on OpenAlex (and Europe PMC for biomedical topics) covering different *facets* of the topic — reaction name, substrate name, common variant identifiers, technique-specific phrases.

```bash
bash scripts/search_year.sh <topic_spec.json> [year]
```

Without a year, runs unrestricted. With a year, restricts via `from_publication_date`/`to_publication_date`. Each engine + each query writes to a separate JSON for downstream merging.

**Why multi-engine:** OpenAlex misses some encyclopedia/preprint variants; Europe PMC misses chemistry-only journals; Crossref misses preprints. Multi-engine OR raises recall by ~10-15%.

### Stage 2 — 1-hop citation graph expansion (when seeds ≥ 5)

```bash
python scripts/expand_citations.py \
  --csv <seed_csv> \
  --topic <topic_spec.json> \
  --out <new_candidates.tsv>
```

Both directions:
- **Outgoing** — fetch each seed's `referenced_works[]`, filter by topic
- **Incoming** — `cites:W1|W2|...&search=<topic>` against OpenAlex; the `search=` clause is **mandatory** because high-impact seeds (foundational papers with 1000+ citations) would otherwise return thousands of unrelated papers

Score each candidate by:
- **Title regex match** (positive terms in topic spec) → keep
- **Multi-seed overlap ≥ 3** AND **abstract contains a positive term** → keep

Multi-seed overlap is the magic number. A paper citing one seed might cite it for unrelated reasons; a paper citing three seeds is almost certainly on-topic.

### Stage 3 — Year-by-year backward sweep (when going deep)

```bash
python scripts/backward_sweep.py \
  --csv <seed_csv> \
  --topic <topic_spec.json> \
  --start-year <latest> \
  --end-year <earliest> \
  --out <updated_csv> \
  [--dry-run]
```

Each year Y:
1. Direct keyword search restricted to year Y
2. From all current seeds' `referenced_works`, filter to `publication_year == Y`
3. Apply topic filter, dedupe vs current CSV, append; new entries become seeds for year Y-1

**Why year-by-year:** as new seeds enter, they unlock citation paths to *older* papers. Iterating in monotone year order makes the seed set complete-for-its-time at each step.

Always run with `--dry-run` first when the user has a CSV you'd be modifying.

### Stage 4 — Cold-start recall validation (recommended)

```bash
python scripts/validate_recall.py \
  --csv <final_csv> \
  --topic <topic_spec.json> \
  --start-year <latest> [--end-year 1997]
```

Empties the seed set, then runs Stages 1+3 from the latest year backward, tracking how many CSV DOIs are *recovered*. Outputs:
- Per-year breakdown of additions
- Final recall % (e.g., 73/73 = 100% on the Kemp eliminase reference corpus)
- Missed DOIs with diagnosis (no keyword hit / no citing seed)

Acceptance: ≥95% recall = corpus is defensibly comprehensive.

## Topic spec format (Mode 2 input)

A JSON file describing what counts as on-topic. Drives every filter decision. See [references/topic_spec.md](./references/topic_spec.md) for the full schema and a worked Kemp eliminase example. A ready-to-copy template lives at [evals/kemp_topic.json](./evals/kemp_topic.json).

```json
{
  "topic": "Kemp eliminase enzymes",
  "queries": ["Kemp+eliminase", "Kemp+elimination", "5-nitrobenzisoxazole", ...],
  "positive_title_terms": ["kemp elimin", "ke07", "ke59", "hg3.17", "alleycat", ...],
  "exclude_title_terms": ["pillararene", "cyclodextrin", "coordination cage", ...],
  "exclude_doi_prefixes": ["10.2210/pdb", "10.5281/zenodo", "10.3410/f.", ...]
}
```

## Decision tree for incoming candidates (Mode 2)

```
Candidate DOI in exclude_doi_prefixes?      → DROP
Candidate title matches exclude_title_terms? → DROP
Candidate title matches positive_title_terms? → KEEP
Candidate cites ≥3 seeds AND abstract has any positive term? → KEEP
Otherwise → FLAG FOR USER (do not silently drop ambiguous ones)
```

## When to stop the sweep

Three-signal stop:
1. **Two consecutive years with 0 new additions** AND
2. **Cold-start recall ≥ 95%** AND
3. **User agrees the corpus is defensibly comprehensive**

If (1) holds but (2) doesn't, the keyword spec is incomplete — read missed DOIs, identify the common pattern, update the spec, re-run.

## Common gotchas (Mode 2)

- **OpenAlex returns duplicate records for the same DOI** (preprint + journal). Dedupe by DOI lowercased + stripped of `https://doi.org/`.
- **`abstract_inverted_index` is a `{word: [positions]}` map**, not text. Reconstruct via `" ".join(idx.keys())` for cheap keyword detection.
- **Citation expansion against high-impact seeds**: a single foundational paper can have 1000+ citations; always combine `cites:` with `search=<topic>` to keep the result set tractable.
- **Awk on macOS is BSD awk**: no `IGNORECASE`, no Perl `/regex/i` flag. Use `tolower($field) ~ /lowercase-pattern/`.
- **Reassigning `$1` in awk** rebuilds `$0` with `OFS`. Set `BEGIN { FS="\t"; OFS="\t" }` whenever you process tab-separated streams.
- **Non-ASCII dashes** in titles (`U+2010`, `U+2013`) break ASCII regex. Normalize with `gsub(/[‐–—]/, "-", title)` before matching.

## Mode 2 references

- [references/topic_spec.md](./references/topic_spec.md) — full topic JSON schema with worked examples
- [references/filter_design.md](./references/filter_design.md) — how to discover and tune positive/negative regex terms
- [references/naming_convention.md](./references/naming_convention.md) — `firstauthor_year_keywords` rules and edge cases
- [references/validation_interpretation.md](./references/validation_interpretation.md) — reading the cold-start recall output

## Mode 2 scripts

All scripts are idempotent — safe to rerun on the same CSV.

- [scripts/search_year.sh](./scripts/search_year.sh) — Stage 1 multi-engine year-restricted harvest
- [scripts/expand_citations.py](./scripts/expand_citations.py) — Stage 2 1-hop citation expansion + overlap scoring
- [scripts/backward_sweep.py](./scripts/backward_sweep.py) — Stage 3 year-by-year iteration (supports `--dry-run`)
- [scripts/validate_recall.py](./scripts/validate_recall.py) — Stage 4 cold-start recall validation
