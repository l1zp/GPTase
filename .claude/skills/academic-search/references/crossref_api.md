# Crossref API Reference

Use Crossref for DOI-first workflows and publisher-grade metadata lookup.

## Base Endpoint

```text
https://api.crossref.org/works
```

## Common Patterns

### Search by query

```text
https://api.crossref.org/works?query=protein%20design&rows=5
```

### Get a specific DOI

```text
https://api.crossref.org/works/10.1038/s41586-024-07487-w
```

### Search by title

```text
https://api.crossref.org/works?query.title=Attention%20is%20all%20you%20need&rows=3
```

### Filter by publication date

```text
https://api.crossref.org/works?query=enzyme&filter=from-pub-date:2023-01-01,until-pub-date:2024-12-31
```

## Good Uses

- Validate or repair DOI metadata
- Fetch publisher, journal, license, and funder metadata
- Confirm canonical title or publication record when another source is ambiguous

## Useful Fields

- `DOI`
- `title`
- `author`
- `container-title`
- `published-print`
- `published-online`
- `URL`
- `is-referenced-by-count`
- `license`
- `funder`

## Practical Notes

- Prefer Crossref when the task starts from a DOI.
- Use it as a metadata backstop when OpenAlex or Semantic Scholar lacks DOI detail.
- Return human-readable fields; do not dump the raw Crossref message object.
