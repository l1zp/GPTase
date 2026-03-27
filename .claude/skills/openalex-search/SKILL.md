---
name: openalex-search
description: |
  Search academic papers and publication metadata via the OpenAlex API. Use when the user wants papers, articles, literature, DOI lookup, citation counts, author-based paper search, journal/source filtering, recent or highly cited publications, or bibliography/literature-review style retrieval. Trigger for requests about papers, publications, articles, literature reviews, citations, DOI, authors, journals, OpenAlex, "most cited papers", "recent papers", or "find articles". Do not use for biochemical database lookups about reactions, proteins, compounds, or pathways; use biochem_databases for those.
---

# OpenAlex Academic Paper Search

Use this skill to query OpenAlex directly for scholarly works and related metadata.

## Workflow

1. Classify the request:
   - Use `works` for paper search, DOI lookup, citations, abstracts, recent papers, and most literature tasks.
   - Resolve `authors` only when the user is clearly searching by person and you need a stable OpenAlex author ID.
   - Resolve `sources` only when the user wants a specific journal, publisher family, or venue filter.
2. Build the narrowest query that matches the user request.
3. Prefer explicit filters for year/date, type, citation ranking, and open access.
4. Reconstruct `abstract_inverted_index` into readable text before presenting abstracts.
5. Return compact, human-readable results with the fields the user asked for; do not dump raw JSON unless asked.

## Response Rules

- Treat `abstract_inverted_index` as an encoded structure, not readable text.
- Include caveats when a field is missing, for example DOI, abstract, or OA URL.
- If the user asks for "latest" or "recent", sort by `publication_date:desc` and surface exact dates.
- If the request mixes literature search with biochemical entities, follow the user's intent:
  - "Find papers about EC 1.1.1.1" -> use OpenAlex.
  - "What reaction does EC 1.1.1.1 catalyze?" -> use `biochem_databases`, not this skill.

## Query Patterns

- Topic search: `works?search=...`
- DOI lookup: `works?filter=doi:...`
- Year/date filter: `filter=publication_year:YYYY` or `from_publication_date/to_publication_date`
- Highly cited: `sort=cited_by_count:desc`
- Recent: `sort=publication_date:desc`
- Review articles: `filter=type:review`
- Author-constrained search: resolve the author first if needed, then filter by `author.id`
- Journal/publisher constrained search: resolve source/publisher IDs before filtering

Read [references/openalex_api.md](./references/openalex_api.md) when you need exact endpoint patterns, filter syntax, publisher IDs, or the abstract reconstruction helper.

## Output Shape

- Default to a short table or bullet list.
- Include title plus only the requested metadata such as authors, year, journal, DOI, citations, and abstract.
- For ranked requests, preserve the requested ordering and state the ranking basis.
