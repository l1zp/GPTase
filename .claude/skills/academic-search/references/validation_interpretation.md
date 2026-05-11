# Reading the cold-start validation output

`validate_recall.py` prints, per year:

```
Year 2017: +direct=10 +ref=0 | recovered=46/73 (seeds=51 ref-cache=1512)
    [direct] 10.1021/acscatal.7b03151
    [direct] 10.1021/jacs.6b12265
    ...
```

And at the end:

```
=== FINAL ===
Recovered: 72/73 (98.6%)
Missed:    1

Missed DOIs:
  10.1016/j.compbiolchem.2016.09.007

Via direct search:     72
Via reference pool:    0
```

## What the numbers mean

| Field | Meaning |
|---|---|
| `+direct` | New CSV entries recovered this year via keyword search |
| `+ref` | New CSV entries recovered via reference-pool expansion (seeds' outgoing refs) |
| `recovered/total` | Cumulative CSV recovery up to this year |
| `seeds` | Total seeds accumulated (recovered + Kemp-relevant non-CSV) |
| `ref-cache` | Total cached reference metadata (input to ref-pool path) |
| `Via direct search` | Final tally of CSV DOIs first reached via keyword |
| `Via reference pool` | Final tally first reached via citation expansion |

## Acceptance threshold

| Recall | Verdict |
|---|---|
| ≥ 95% | Corpus is defensibly comprehensive. Stop. |
| 90-95% | Tune topic spec (see below). |
| < 90% | Spec is significantly incomplete. Read the missed DOIs carefully. |

## Diagnosing misses

For each missed DOI, fetch its OpenAlex record and ask:

1. **Does its title contain any positive_title_term?**
   - If yes: bug in your title regex (case mismatch? Unicode dash?)
   - If no: add a more specific positive term (e.g., a variant identifier the paper uses)

2. **Is the DOI in any seed's `referenced_works`?**
   - If yes: the multi-seed-overlap threshold (≥3) was too strict, OR the abstract didn't have a positive term — relax one of those for this paper class.
   - If no: nothing in the seeds cites it. The paper is either an orphan or a bridge to another sub-area. Add a query that would catch it.

3. **Is the DOI in a different paper's citing set?**
   - If yes (someone cites it but no seed cites them): you need a 2-hop expansion, OR add a more specific query.

The single Kemp eliminase miss (`10.1016/j.compbiolchem.2016.09.007`, "Side-chain dynamics analysis of KE07 series") fell into category (1): the title only said "KE07" without "Kemp". Adding `KE07` as its own search query (`queries`) recovered it — the corpus reached 100% (73/73) after that one-line spec update. This is the canonical example of the iteration loop below.

## When `Via reference pool > 0`

If reference-pool recovery is non-zero, you know that *some* CSV papers are unreachable by keyword alone — they only entered via citation expansion. This is the case where the citation-graph step earns its keep. For Kemp eliminase, this number was 0; for broader topics with weaker keyword discriminability, it's typically 5-15% of the corpus.

## Iterating

After each validation run:

1. Pick the largest remaining miss class
2. Add the term/query that would have caught it
3. Re-run validation
4. Repeat until recall ≥ 95% or you accept the residual

Don't try to recover the last 1-2 papers if doing so requires brittle one-off rules — just note them in a `manual_additions.txt` and add them by hand. Some papers are genuinely orphan-like.
