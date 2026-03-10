---
name: openalex_search
description: |
  ESSENTIAL for searching academic papers via OpenAlex API. CONSULT THIS SKILL whenever the user mentions papers, articles, publications, literature, DOI, citations, authors, journals, or research - even indirectly. OpenAlex has specific query syntax, publisher IDs, and response formats (inverted index abstracts) that require this skill's guidance to use correctly.

  ALWAYS trigger when user asks to: find/search/look up papers, articles, publications, or literature; get paper metadata (DOI, abstract, citations); search by author, journal, topic, or keyword; filter by date, publisher, or citation count; do a literature review or bibliography search.

  Do NOT trigger for: biochemical database queries (use biochem_databases instead), reading PDF files, or general web searches unrelated to academic publications.

  Triggers on: papers, articles, publications, literature, DOI, citations, authors, journals, OpenAlex, "search for papers", "find articles", "research papers", "academic", "publications", "bibliography", "literature review", "cited by", "most cited".
---

# OpenAlex Academic Paper Search

This skill provides guidance for searching academic papers and literature using the OpenAlex API. Use Claude's built-in WebFetch tool to query OpenAlex directly.

## OpenAlex API

**Base URL:** `https://api.openalex.org/works`

### Query Types

| Operation | URL Pattern | Example |
|-----------|-------------|---------|
| Search papers | `?search={query}&per-page={n}` | `?search=enzyme+kinetics&per-page=10` |
| Filter by date | `?filter=from_created_date:{YYYY-MM-DD}` | `?filter=from_created_date:2024-01-01` |
| Filter by DOI | `?filter=doi:{doi}` | `?filter=doi:10.1038/s41586-024-07487-w` |
| By publisher | `?filter=primary_location.source.host_organization:{id}` | See publisher IDs below |
| Sort results | `&sort={field}:{direction}` | `&sort=publication_date:desc` |
| Pagination | `&page={n}` | `&page=2` |

### Common Publisher IDs

| Publisher | OpenAlex ID |
|-----------|-------------|
| Elsevier | P4310320990 |
| Springer Nature | P4310319965 |
| Wiley | P4310320503 |
| ACS | P4310319787 |
| RSC | P4310320022 |

### Response Format

Returns JSON with `results` array. Each work contains:
- `title`: Paper title
- `doi`: Digital Object Identifier
- `publication_date`: Publication date (YYYY-MM-DD)
- `authorships[].author.display_name`: Author names
- `abstract_inverted_index`: Abstract text (needs reconstruction from inverted index)
- `open_access.oa_url`: PDF link if available
- `primary_location.source.display_name`: Journal/conference name
- `cited_by_count`: Citation count
- `type`: Work type (article, preprint, etc.)

### Reconstructing Abstracts

The `abstract_inverted_index` field contains word positions. To reconstruct:

```python
def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return None
    positions = []
    for word, indices in inverted_index.items():
        for idx in indices:
            positions.append((idx, word))
    positions.sort()
    return " ".join(word for _, word in positions)
```

### Example Queries

```
# Search for recent CRISPR papers
WebFetch("https://api.openalex.org/works?search=CRISPR+enzyme+engineering&per-page=10&sort=publication_date:desc")

# Find papers by DOI
WebFetch("https://api.openalex.org/works?filter=doi:10.1038/s41586-024-07487-w")

# Search Nature papers from 2024
WebFetch("https://api.openalex.org/works?search=protein+design&filter=primary_location.source.host_organization:P4310319965,from_publication_date:2024-01-01&per-page=20")
```

## Advanced Filters

| Filter | Example |
|--------|---------|
| Publication year | `&filter=publication_year:2024` |
| Year range | `&filter=from_publication_date:2023-01-01,to_publication_date:2024-12-31` |
| Open access only | `&filter=is_oa:true` |
| Work type | `&filter=type:article` (article, preprint, dissertation, etc.) |
| Has abstract | `&filter=has_abstract:true` |

## Best Practices

1. **Use specific queries**: Narrow searches with multiple filters to get relevant results
2. **Sort by recency**: Add `&sort=publication_date:desc` for newest papers first
3. **Limit results**: Use `per-page` to control response size (default 25, max 200)
4. **Check open access**: Look for `open_access.oa_url` for free PDF links
5. **Rate limiting**: OpenAlex allows generous limits, but avoid rapid bulk requests

## Common Workflows

### Find recent papers on a topic
```
WebFetch("https://api.openalex.org/works?search={TOPIC}&per-page=10&sort=publication_date:desc")
```

### Search by author
```
WebFetch("https://api.openalex.org/works?filter=author.id:{AUTHOR_ID}&sort=publication_date:desc")
```

### Find highly cited papers
```
WebFetch("https://api.openalex.org/works?search={TOPIC}&sort=cited_by_count:desc&per-page=10")
```
