# OpenAlex API Reference

## Endpoints

- Works: `https://api.openalex.org/works`
- Authors: `https://api.openalex.org/authors`
- Sources: `https://api.openalex.org/sources`

Use `works` for most tasks. Query `authors` or `sources` first only when you need a stable ID for downstream filtering.

## Common Query Templates

### Search works by topic

```text
https://api.openalex.org/works?search={QUERY}&per-page={N}
```

Example:

```text
https://api.openalex.org/works?search=enzyme+kinetics&per-page=10
```

### Sort newest first

```text
https://api.openalex.org/works?search={QUERY}&per-page={N}&sort=publication_date:desc
```

### Sort most cited first

```text
https://api.openalex.org/works?search={QUERY}&per-page={N}&sort=cited_by_count:desc
```

### DOI lookup

```text
https://api.openalex.org/works?filter=doi:{DOI}
```

### Filter by year or date range

```text
https://api.openalex.org/works?search={QUERY}&filter=publication_year:2024
https://api.openalex.org/works?search={QUERY}&filter=from_publication_date:2023-01-01,to_publication_date:2024-12-31
```

### Filter review articles

```text
https://api.openalex.org/works?search={QUERY}&filter=type:review
```

### Filter open access or abstract availability

```text
https://api.openalex.org/works?search={QUERY}&filter=is_oa:true
https://api.openalex.org/works?search={QUERY}&filter=has_abstract:true
```

### Filter by author ID

First resolve the author:

```text
https://api.openalex.org/authors?search=David+Baker&per-page=5
```

Then filter works:

```text
https://api.openalex.org/works?filter=author.id:{AUTHOR_ID}&sort=cited_by_count:desc&per-page=10
```

### Filter by source or publisher family

Resolve the source if needed:

```text
https://api.openalex.org/sources?search=Nature+Methods&per-page=5
```

Then filter works by source:

```text
https://api.openalex.org/works?search={QUERY}&filter=primary_location.source.id:{SOURCE_ID}
```

Filter by publisher family with known host organization IDs:

```text
https://api.openalex.org/works?search={QUERY}&filter=primary_location.source.host_organization:{PUBLISHER_ID}
```

## Known Publisher IDs

| Publisher | OpenAlex ID |
| --- | --- |
| Elsevier | `P4310320990` |
| Springer Nature | `P4310319965` |
| Wiley | `P4310320503` |
| ACS | `P4310319787` |
| RSC | `P4310320022` |

## Important Response Fields

- `title`
- `doi`
- `publication_year`
- `publication_date`
- `cited_by_count`
- `type`
- `authorships[].author.display_name`
- `primary_location.source.display_name`
- `open_access.oa_url`
- `abstract_inverted_index`

## Abstract Reconstruction

`abstract_inverted_index` is not human-readable. Rebuild it before quoting or summarizing the abstract.

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

## Practical Notes

- Combine multiple filters in a single `filter=` parameter separated by commas.
- Keep `per-page` reasonably small unless the user explicitly asks for a larger batch.
- Surface exact dates when the request is about recent or latest papers.
- If an author search is ambiguous, say which matched identity you used.
