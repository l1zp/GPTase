# Image-Reading Benchmark

Initial benchmark for the v9 vision pipeline: every reaction-related
table and figure across the 18-paper Kemp-elimination corpus,
classified by whether MinerU already produced a structured CSV (ground
truth) or whether vision OCR / interpretation is still required.

## How was this built?

`/tmp/build_image_benchmark.py` walks every `paper_data.json` under
`papers/markdowns/`, scores each table/figure caption against three
keyword groups:

- **HARD** kinetic terms (3 pts): kcat, Km, Michaelis, turnover,
  specificity, catalytic param, kinetic param, vmax, eliminase,
  steady-state, …
- **SOFT** activity terms (2 pts): activity, rate, efficiency, evolved,
  variant, hydrolysis, reaction, …
- **STRUCTURAL** (1 pt): crystal, structure, active site, scaffold,
  mutation, residue, hydrogen bond, …

Score thresholds → category:

| score | category |
|---|---|
| ≥3 | kinetic |
| ≥1 | structural |
| else | non_reaction |

**Special case for ghost tables**: every ghost table (MinerU detected
`type=table` but produced no HTML body, only a cropped image) defaults
to `kinetic_table_ghost` regardless of caption — the user's instruction
was explicit: *if MinerU has no CSV, vision must read it*.

## Layout

```
_image_benchmark/
├── README.md         ← this file
└── benchmark.json    ← machine-readable
    ├── summary       ← totals by category and per paper
    └── items[]       ← per-image record (see schema below)
```

### items[] schema

```json
{
  "id": "<paper_path>/<table_id_or_figure_id>",
  "paper": "<paper_path>",
  "kind": "table" | "figure",
  "category": "kinetic_table_with_csv" | "kinetic_table_ghost"
              | "kinetic_figure" | "structural_table"
              | "structural_figure" | "non_reaction",
  "ghost": true | false,
  "page_idx": int,
  "caption": "<original caption text from MinerU>",
  "image_path_rel": "images/<hash>.jpg",
  "image_path_abs": "/full/path/to/image.jpg",
  "csv_preview_chars": int,
  "ground_truth_csv": "<CSV string if mineru_csv>",
  "ground_truth_source": "mineru_csv" | "vision_required" | "n/a",
  "score": int,
  "score_matches": ["hard:..." or "soft:..." or "struct:..."]
}
```

## Summary (current run)

| metric | count |
|---|---:|
| total items | 526 |
| **kinetic_table_with_csv** (MinerU has CSV ground truth) | **44** |
| **kinetic_table_ghost** (table image, no HTML — vision needed) | **52** |
| **kinetic_figure** (scientific plot with kinetic data) | **102** |
| structural_figure | 59 |
| structural_table (low-priority) | 28 |
| non_reaction (skip) | 241 |

| ground truth source | count |
|---|---:|
| mineru_csv (zero-cost ground truth) | 44 |
| vision_required (needs OCR/interpretation) | 213 |
| n/a (skipped) | 269 |

## Suggested workflow for the v9 vision benchmark

### Tier 1 — Self-verifying (44 items)
The 44 `kinetic_table_with_csv` items are the **gold standard**.
Use them to evaluate vision OCR accuracy: feed the image into the
vision agent, parse its output as CSV, diff against `ground_truth_csv`.
Any deviation is a vision failure.

### Tier 2 — Ghost tables (52 items)
MinerU recognized the layout as a table but couldn't extract HTML.
These are the **single highest-yield vision targets** — every ghost
table likely has tabular kinetic data MinerU's OCR just missed.
Manual annotation (or careful vision OCR + spot-check) gives these
clean ground truth.

### Tier 3 — Kinetic figures (102 items)
Real scientific figures: Michaelis-Menten plots, activity bar charts,
pH dependence curves. Vision agent must interpret + extract numerical
values. No CSV ground truth; rely on cross-replica agreement.

### Tier 4 — Structural items (87 items)
Crystal structures, active-site closeups. Useful context but typically
not numerical extraction. Lower priority.

## Top-coverage papers (kinetic-only count)

| paper | kinetic items | with_csv | needs_vision |
|---|---:|---:|---:|
| risso_2020 (main) | 7 | 3 | 7 |
| rothlisberger_2008 (main) | 6 | 2 | 4 |
| zarifi_2025 (main) | 6 | 1 | 5 |
| bhattacharya_2022 (main) | 5 | 4 | 4 |
| listov_2025 (main) | varies | varies | varies |
| (full list in `summary.by_paper` of benchmark.json) | | | |

(See `benchmark.json:summary.by_paper` for all 42 paper dirs.)

## Next steps (not yet executed)

1. **Sample CSV diff** — pick a few `kinetic_table_with_csv` items, run
   vision agent on the image, compare against `ground_truth_csv`. This
   tells us how reliable vision is on already-OCR'd tables, and
   establishes the baseline accuracy ceiling.
2. **Triage 52 ghost tables** — view a few to confirm they're worth
   the effort (some might be metadata tables like "amino-acid sequence
   list" that aren't kinetics). Annotate the high-priority ones.
3. **Score 102 kinetic figures** — establish a smaller curated set
   (e.g., 20 with explicit numeric data) for vision evaluation.

## Files

- `benchmark.json` — full dataset (526 items, ~250 KB)
- `README.md` — this file
