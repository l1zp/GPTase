---
name: academic-search
description: |
  Search academic papers and publication metadata via OpenAlex, Semantic Scholar, Crossref, and Europe PMC. Use when the user wants papers, articles, literature, DOI lookup, citation counts, author-based paper search, journal/source filtering, recent or highly cited publications, known-paper title lookup, biomedical literature retrieval, or bibliography/literature-review style retrieval. Trigger for requests about papers, publications, articles, literature reviews, citations, DOI, authors, journals, Semantic Scholar, OpenAlex, Crossref, Europe PMC, PubMed-style literature discovery, "most cited papers", "recent papers", or "find articles". Do not use for biochemical database lookups about reactions, proteins, compounds, or pathways; use biochem_databases for those.
---

# Academic Search

Use this skill to query scholarly literature with OpenAlex, Crossref, Europe PMC, and, when available, the local `semanticscholar` Python SDK.

## Routing

1. Classify the request:
   - DOI metadata, publisher metadata, license, funder -> Crossref
   - Biomedical or PMID/PMCID-centric literature -> Europe PMC
   - Citation-ranked general literature or journal/source filtering -> OpenAlex
   - Quick known-paper lookup or one-paper detail -> Semantic Scholar SDK first, then OpenAlex
2. Use a two-step workflow for one specific paper:
   - Search small first, typically `3` to `10` hits.
   - Inspect only the best hit in detail.
3. Fall back in this order:
   - Semantic Scholar rate-limited or unavailable -> OpenAlex
   - Missing or inconsistent DOI metadata -> Crossref
4. Keep the first request narrow. Add only the filters and fields the user actually needs.
5. Optimize for search coverage and result correctness first, not downloadability.
6. After selecting the correct result set, enrich with download or full-text links when available.
7. Return compact, human-readable results instead of raw API payloads.
8. For known-paper lookup, compare top hits by title similarity, year plausibility, venue, and DOI before accepting the first result.

## Response Rules

- Treat `abstract_inverted_index` as an encoded structure, not readable text.
- Request or inspect only the fields needed for the task first; expand to richer metadata only after you have the correct paper or narrowed result set.
- Include caveats when a field is missing, for example DOI, abstract, or OA URL.
- If the user wants downloads or full text, treat that as a second-pass enrichment step after identifying the right papers.
- If the user asks for "latest" or "recent", sort by `publication_date:desc` and surface exact dates.
- For biomedical searches, prefer Europe PMC over generic scholarly search engines unless the user specifically asks for another source.
- For "recent biomedical papers with citation counts", state the tradeoff: the newest papers may legitimately have zero citations; if citation signal matters, bias toward a slightly older window or cross-check counts in OpenAlex.
- For DOI validation or publication metadata cleanup, prefer Crossref.
- If the request mixes literature search with biochemical entities, follow the user's intent:
  - "Find papers about EC 1.1.1.1" -> use this skill.
  - "What reaction does EC 1.1.1.1 catalyze?" -> use `biochem_databases`, not this skill.
- When the user is clearly trying to identify one known paper, include stable identifiers where available, such as OpenAlex work ID, DOI, and landing page URL.
- When using Semantic Scholar, handle `429 Too Many Requests` by falling back to OpenAlex instead of repeatedly retrying.
- For famous or canonical papers, reject obviously implausible variants such as much newer preprint records when title, venue, year, and DOI suggest an older canonical publication.
- If download links are requested, label availability explicitly, for example `direct_pdf`, `oa_fulltext`, `landing_page_only`, or `metadata_only`.

## Load References

- Read [references/router.md](./references/router.md) first when backend choice is not obvious.
- Read [references/openalex_api.md](./references/openalex_api.md) for OpenAlex filters, source routing, and abstract reconstruction.
- Read [references/semanticscholar_sdk.md](./references/semanticscholar_sdk.md) for Semantic Scholar SDK usage and rate-limit behavior.
- Read [references/crossref_api.md](./references/crossref_api.md) for DOI and publisher metadata workflows.
- Read [references/europe_pmc_api.md](./references/europe_pmc_api.md) for biomedical search patterns and Europe PMC identifiers.
- Read [references/download_enrichment.md](./references/download_enrichment.md) when the user wants full text, PDFs, or download links.

## Output Shape

- Default to a short table or bullet list.
- Include title plus only the requested metadata such as authors, year, journal, DOI, citations, and abstract.
- For ranked requests, preserve the requested ordering and state the ranking basis.
- For single-paper identification, prefer:
  - title
  - year
  - top authors
  - citation count
  - DOI or work URL
  - short abstract snippet only if the user asked for abstract/detail
