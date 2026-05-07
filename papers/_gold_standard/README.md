# Gold Standard Extraction Results

Per-paper "best of all runs" snapshot, used as the baseline for future
v9 pipeline comparisons.

## How was this picked?

`/tmp/consolidate_results.py` scans every result file under
`papers/_test_runs/*/` for each of the 18 papers, scores each by:

1. **Real variant count** — variants whose name passes a noise filter
   (excludes pH values like `6.0`, `pH 7`, descriptive labels like
   `Top variants (average)`, `Pareto front`, generic stubs like
   `Core`/`Shell`/`Evolved` without scaffold prefix, `gel filtration`,
   `α-set variants`, `Variant code`).
2. **Kinetics completeness** — number of variants with ≥2 of (kcat, Km,
   kcat/Km) populated.
3. **Recency** — newer mtime breaks ties.

The winner per paper is copied to `<paper>/result.json`, with a
`<paper>/source.json` recording which run won and why.

## Layout

```
_gold_standard/
├── README.md                           ← this file
├── index.json                          ← per-paper winner summary
├── audit.json                          ← variant names + counts per paper
└── <paper>/
    ├── result.json                     ← winning extraction (copied)
    └── source.json                     ← winner_run + score breakdown
```

## Headline numbers

- **18/18 papers** have a chosen winner
- **285 real variants** across the corpus
- **216 (76%)** carry at least one kinetic parameter
- **105 (37%)** carry ≥2 kinetic parameters (kcat, Km, kcat/Km)

## Run mix (which version produced each winner)

| Run | Papers won |
|---|---:|
| v8_norm_only_20260507_202232 (latest, paper_data.json sidecar) | 14 |
| v8_norm_only_20260507_182117 (prior v8) | 3 |
| failed_2_rerun_20260506_224628 (v1 rerun for rothlisberger) | 1 |
| rows_6_19_20260506_174714 (v1 baseline for privett) | 1 |

→ **17/18 winners are v8 (HTML-aware) extraction**. v1 wins only on 2
papers where v1's pre-collapsing left more raw variant rows.

## Known caveats per paper

| paper | real | caveat |
|---|---:|---|
| bhattacharya_2022 | 21 | 14 noise items dropped by filter (large narrative leakage) |
| gutierrez_2025 | 28 | pH values 6.0–8.5 leaked through as variants (transposed table issue) |
| khersonsky_2012 | 24 | substrate names + footnote text leaked (`5-fluorobenzisoxazole`, `* Approximate kcat/KM...`) |
| listov_2025 | 50 | aliases like `Des27.7 F113L` and `Des27.7 F113L mutant` are duplicated; 2 noise hidden |
| zarifi_2025 | 17 | `1A53 series` / `HG3 series` / `KE70 series` are aggregate labels, not variants |

These are the limits of the current normalizer's de-duplication logic
on top of MinerU-extracted tables. v9 work should aim to clean these
without losing the raw recall.

## Per-paper headline counts

(See `index.json` for machine-readable; `audit.json` for full names.)

| paper | real | kin≥1 | winner |
|---|---:|---:|---|
| alexandrova_2008 | 6 | 3 | v8 latest |
| bhattacharya_2022 | 21 | 17 | v8 latest |
| bhowmick_2017 | 12 | 6 | v8 latest |
| blomberg_2013 | 11 | 10 | v8 latest |
| broom_2020 | 9 | 9 | v8 latest |
| bunzel_2021 | 3 | 0 | v8 latest |
| gutierrez_2025 | 28 | 34 | v8 prior |
| khersonsky_2012 | 24 | 16 | v8 latest |
| listov_2025 | 50 | 37 | v8 prior |
| merlicek_2025 | 4 | 0 | v8 prior |
| mondal_2020 | 10 | 0 | v8 latest |
| privett_2012 | 19 | 13 | v1 baseline |
| risso_2020 | 39 | 39 | v8 latest |
| rothlisberger_2008 | 27 | 26 | v1 rerun |
| swiderek_2015 | 1 | 0 | v8 latest |
| vaissier_welborn_2018 | 3 | 3 | v8 latest |
| xie_2022 | 1 | 0 | v8 latest |
| zarifi_2025 | 17 | 3 | v8 latest |

## Use as v9 baseline

When iterating on v9, compare new results against `_gold_standard/`:
- per-paper `real` count should not drop below the gold standard
- kinetics completeness should improve
- noise items should decrease (esp. bhattacharya/gutierrez/khersonsky)

This file + `index.json` + `audit.json` form the regression baseline.
