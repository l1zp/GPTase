# Naming convention

Output CSV row format:

```
<lastname>_<year>_<2-3_keywords>,<doi>
```

All snake_case, all ASCII. The name is **identifier-style**: it serves as a primary key in the CSV and may be used as a directory name in downstream pipelines. Stability matters more than prettiness.

## Lastname rules

| Source author | Name segment |
|---|---|
| `Olga Khersonsky` | `khersonsky` |
| `Vaissier-Welborn` (hyphenated) | `vaissier_welborn` |
| `Świderek` (diacritics) | `swiderek` |
| `Genre-Grandpierre` | `genre_grandpierre` |
| `Acosta-Silva` | `acosta_silva` |
| Single Chinese name (`Cao`) | `cao` |
| Compound Chinese (`Aitao Li`) | `li` (pick last word) |

ASCII-only. Strip diacritics via Unicode NFKD decomposition + non-ASCII filter. Hyphens become underscores. Apostrophes are dropped.

## Year

Four-digit integer from `publication_year`. For preprints, use the preprint year, not the eventual journal year (you may have both DOIs in the CSV — the preprint will deduplicate later if you replace it).

## Keywords (the 2-3 word slug)

Pick the 2-3 most distinctive **content** words from the title. Heuristics:
- Skip stopwords: `the`, `a`, `of`, `for`, `in`, `on`, `with`, `and`, `to`, `by`, `an`
- Prefer technical / chemical / variant terms over generic words like "study", "analysis", "investigation"
- Drop article words like "computational", "molecular", "structural" only if the slug becomes too generic without them
- Keep variant identifiers (`ke07`, `hg317`, `alleycat`) when they appear in the title

## Examples (real CSV entries)

| Title | Slug |
|---|---|
| "Kemp elimination catalysts by computational enzyme design" | `kemp_elimination_catalysts` |
| "Precision is essential for efficient catalysis in an evolved Kemp eliminase" | `precision_kemp_eliminase` |
| "Bridging the gaps in design methodologies by evolutionary optimization of the stability and proficiency of designed Kemp eliminase KE59" | `bridging_gaps_kemp_ke59` |
| "Computational Optimization of Electric Fields for Improving Catalysis of a Designed Kemp Eliminase" | `electric_field_optimization_kemp` |

Maximum slug length: keep the full name under 80 characters. If the title gives you no good 2-3 words, expand to 4. If still nothing, fall back to `paper`.

## Disambiguating same-author-same-year

If `khersonsky_2009` already exists in the CSV and you encounter another Khersonsky 2009 paper, differentiate **by adding a more specific keyword**, not by suffix:

- ✅ `khersonsky_2009_evolutionary_optimization_ke07`
- ✅ `khersonsky_2009_kemp_eliminase_design_review`
- ❌ `khersonsky_2009`, `khersonsky_2009_b`

This way the name remains independently meaningful — readers can tell which paper it points to without checking the DOI.

## Programmatic generation

The bundled `backward_sweep.py` generates names automatically via `name_from_work()`. Output may need manual touch-ups when:
- The author has many one-syllable names (auto-pick is correct but ambiguous)
- The title's first 3 content words are all generic
- Two different DOIs hash to the same slug

After running the sweep, scan for collisions:

```bash
awk -F',' 'NR>1{print $1}' papers_doi.csv | sort | uniq -d
```

Empty output = unique. Manually fix any duplicates by editing the slug.
