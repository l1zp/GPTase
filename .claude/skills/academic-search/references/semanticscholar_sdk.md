# Semantic Scholar SDK Reference

Use the local Python SDK when `from semanticscholar import SemanticScholar` works in the current environment and the task is a straightforward paper lookup or paper-detail fetch.

## Basic Pattern

```python
from semanticscholar import SemanticScholar

sch = SemanticScholar()
results = sch.search_paper("Attention is all you need", limit=3)

top = results[0]
paper = sch.get_paper(top.paperId)
```

This mirrors [examples/test_semanticscholar.py](../../../../examples/test_semanticscholar.py).

## Good Uses

- Known paper by title
- Small top-N paper lookup
- Fetch details for one selected paper after a small search

## Common Fields

From `search_paper(...)` results or `get_paper(...)` detail objects, prefer:

- `title`
- `year`
- `citationCount`
- `paperId`
- `url`
- `abstract`
- `authors`

Do not dump raw SDK objects. Convert them into a short human-readable summary.

## Rate-Limit Guidance

- Semantic Scholar public API access may return `429 Too Many Requests` without an API key.
- If the SDK call fails due to rate limiting or network access, switch to OpenAlex for the same search intent.
- Do not keep retrying aggressively. Prefer a single fallback explanation plus an OpenAlex result.

## Practical Pattern

1. Run a small `search_paper(query, limit=3)` search.
2. Compare the top few hits by title similarity, year, and authors.
3. Fetch `get_paper(paperId)` only for the best hit when richer detail is needed.
4. If the SDK path fails or rate-limits, say so briefly and continue with OpenAlex.
