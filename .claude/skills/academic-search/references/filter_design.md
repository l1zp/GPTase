# Filter design

Two failure modes to design against:

- **False positives** (off-topic papers slip in) → add `exclude_title_terms`
- **False negatives** (on-topic papers missed) → add `positive_title_terms` or `queries`

## How OpenAlex tokenizes the search field

OpenAlex's `search=` parameter does word-level matching against title + abstract + keywords. Two practical gotchas:

1. **Hyphens behave unpredictably.** Searching `5-nitrobenzisoxazole` matches papers using "5-nitrobenzisoxazole" but may miss "5‐nitrobenzisoxazole" (Unicode hyphen U+2010). For substrate names, add both ASCII and Unicode-hyphen variants OR strip the hyphen entirely (`nitrobenzisoxazole`).
2. **Token boundaries don't respect chemistry.** `KE07` is one token; `KE-07` may be tokenized as `KE` + `07`, neither of which alone is meaningful. Spell variants out: `"KE07"`, `"KE 07"`, `"KE-07"`.

## Multi-seed overlap is your friend

For a candidate paper that has no positive title term but cites multiple seeds, the **multi-seed overlap count** is a strong signal:

| Overlap | Interpretation |
|---|---|
| 0-2 | Could be coincidence (Rosetta cited by everyone, etc.) |
| 3-5 | Likely on-topic; check abstract for positive terms |
| ≥6 | Almost certainly on-topic; flag for keep |

Combined with "abstract contains a positive term", overlap ≥ 3 has been validated as a precise filter on Kemp eliminase: zero off-topic false positives across 660 citing-paper candidates.

The intuition: a single Kemp paper might be cited by an unrelated MD-methods paper that happens to use Kemp as one of many test systems. But if a paper cites three different Kemp papers, those three citations are unlikely to be incidental — the paper is engaging with the Kemp literature.

## Patterns that won't work

- **Author-name match**: too loose. "Khersonsky" and "Hilvert" are good signals but they also work in other enzyme topics.
- **Journal-name match**: too loose. *Nature*, *PNAS*, *JACS* publish Kemp papers but also millions of unrelated papers.
- **Citation count thresholds**: too noisy. New Kemp papers have 0 citations; old foundational ones have 1000+.

## Patterns that work for negative terms

Build the exclude list from titles, not abstracts. Title length is bounded (~10-20 words) so any term you add has high precision. Abstract terms tend to over-trigger (e.g., a Kemp eliminase paper might say "compared to ionic liquids" in its abstract — you'd wrongly exclude it).

## When to expand the query list vs the positive title terms

- **More queries**: lets OpenAlex find papers your positive_title_terms don't cover (because the term is only in the abstract).
- **More positive_title_terms**: tightens the precision filter on candidates that came in via search (so you don't include random "Kemp" name papers).

Rule of thumb: if validation says "missed because no keyword hit", expand `queries`. If validation says "off-topic but slipped through", expand `exclude_title_terms`.

## Cycling: how the spec gets refined

```
write spec v1 → search → look at top 50 results
  ↓                                ↓
  add exclude terms             add missing variants to positives + queries
  ↓                                ↓
  re-search → re-validate → cold-start recall
  ↓
  if recall < 95%: read missed DOIs, identify common pattern
  ↓
  update spec → loop
```

Most topics converge in 2-3 iterations once you have ≥10 confirmed seeds.
