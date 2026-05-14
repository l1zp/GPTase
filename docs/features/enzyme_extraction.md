# Enzyme Kinetics Extraction Pipeline

A multi-step pipeline for harvesting Michaelis-Menten parameters
(`kcat`, `Km`, `kcat/Km`, `Tm`) and full-length protein sequences from
a corpus of designed-enzyme papers. The pipeline is **driven by a
Python script**, not a Coordinator plan — each item (table / figure /
section) is dispatched to a specialized agent, results are aggregated
and normalized per paper, and the final output is a flat CSV
(`_summary.kinetics_variants.csv`) carrying sequence + mutations +
kinetics for every variant across the corpus.

## Architecture

```
                 papers/markdowns/<paper>/main/full.md
                 papers/markdowns/<paper>/SI/.../full.md
                                  │
                                  ▼
              enzyme-kinetics-screener     ← Step 1
              (per-paper TRUE/FALSE)         decides which 34/68 papers
                                  │          carry measured kinetic data
                                  ▼
              papers/extractions/<paper>/screener.json
                                  │
                                  ▼
              enzyme-kinetics-content-tagger ← Step 2
              (per-item relevance tag)        tags 1760 outline items
                                  │           → 244 TRUE
                                  ▼
              papers/extractions/<paper>/sections.{main,si.X}.json
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼     ← Step 3
  enzyme-kinetics-          enzyme-kinetics-          enzyme-kinetics-
  table-extractor           figure-extractor          text-extractor
  (per-table LLM)           (per-figure vision)       (per-section LLM)
        │                         │                         │
        └─────────────────────────┼─────────────────────────┘
                                  ▼
                       enzyme-scaffold-mapper     ← Step 3.5
                       (per-paper LLM:                 binds variant_names →
                        scaffold name + PDB)           scaffold + PDB id;
                                  │                    fallback via
                                  │                    scaffold_registry.json
                                  ▼
                       enzyme-variant-normalizer  ← Step 4
                       (deterministic merge +
                        vision-confirmed dedup +
                        RCSB FASTA fetch)
                                  │
                                  ▼
              papers/extractions/<paper>/kinetics.json
                                  │
                                  ▼
              _flatten_paper_to_csv_rows  ← Step 5
              (one row per variant)
                                  │
        ┌─────────────────────────┴─────────────────────────┐
        ▼                                                   ▼
  papers/extractions/<paper>/kinetics.csv            papers/extractions/
  (per-paper flat table)                             _summary.kinetics_variants.csv
                                                     (corpus-wide aggregator)
```

Each agent runs **once per item** (one table → one LLM call, one
figure → one vision call, one section → one LLM call). This is more
expensive than a single-shot per-paper extraction but isolates
failures: a corrupt figure can't poison the whole paper.

## The Driver

The orchestrator is **not** a Coordinator plan — it's a plain Python
script that handles concurrency, caching, and aggregation:

```bash
# Full corpus run (table + figure + text path)
python scripts/run_kinetics_extraction.py --enable-figures --enable-text

# Canary on a single paper
python scripts/run_kinetics_extraction.py \
    --only blomberg_2013_precision_kemp_eliminase \
    --enable-figures --enable-text

# Force re-LLM (ignore per-call artifact cache)
python scripts/run_kinetics_extraction.py --force \
    --enable-figures --enable-text

# Tune concurrency / per-call timeout
python scripts/run_kinetics_extraction.py \
    --workers 6 --timeout 480 \
    --enable-figures --enable-text
```

Flags:

| Flag | Default | Purpose |
|---|---|---|
| `--only <paper> [...]` | all TRUE papers | Restrict to listed paper directories |
| `--workers N` | 4 | Concurrency cap (`asyncio.Semaphore`) |
| `--timeout N` | 360 | Per-call wall-clock ceiling (seconds) |
| `--force` | off | Re-run even when `.kinetics_workdir/<artifact>.json` exists |
| `--enable-figures` | off | Phase 2 — dispatch figures to vision extractor |
| `--enable-text` | off | Phase 3 — dispatch sections to text extractor |
| `--disable-scaffold-mapper` | off | Step 3.5 — skip the per-paper scaffold-mapper LLM call (debug only) |
| `--skip-preflight` | off | Skip the LLM endpoint health check before launching the batch |

Per-call results are cached at
`papers/extractions/<paper>/.kinetics_workdir/{table,section,figure}__<src_tag>__NNN.json`
so the driver can be re-run incrementally — only failing items get
re-LLMed.

## The Per-Item Agents

### `enzyme-kinetics-screener` (Step 1)

A per-paper TRUE/FALSE filter. Reads the full main markdown and
returns `{has_kinetic_data: bool, reason: str}`. Tightened prompt
removes the "single isolated rate" gray zone; a `pre_run` hook
short-circuits on missing files. A/B-tested across Doubao-Pro and
DeepSeek-V4-Flash (98.4% inter-model agreement on the 68-paper
corpus).

### `enzyme-kinetics-content-tagger` (Step 2)

Operates on the MinerU outline (sections / tables / figures). For
each item, returns `is_relevant: bool` + a `reason` string. The
relevance contract covers two distinct content kinds:

1. **Kinetic measurement** — `kcat / Km / Vmax / kobs` columns in
   tables, Michaelis-Menten saturation / pH-rate / time-course curves
   in figures, headings like `Kinetic analysis` / `Activity assay`.
2. **Protein sequences** — sections whose heading is `Amino acid
   sequences`, `Designed sequences`, FASTA-style `>HG3`, or whose
   body preview contains a contiguous run of ≥ 30 uppercase
   one-letter AA codes including at least one non-ATCG residue
   (the four letters `ACGT` are also valid DNA — strict gating
   prevents `>HG3.R1` DNA sections from being tagged TRUE).

The agent never sees the full body — only the 240-char outline
preview that `outline.py` builds from the MinerU `content_list.json`.

### `enzyme-kinetics-table-extractor` (Step 3)

Per-table LLM call. The pre_run hook deterministically pre-parses
the MinerU `<table>` HTML into a cleaned 2D grid (expanding
`colspan` / `rowspan` and dropping nested `<thead>` chrome), then
injects BOTH the raw HTML and the cleaned grid into the prompt so
the LLM can cross-check. Output: canonical `reactions[]` + (usually
empty) `protein_sequences[]`. The exponent-recovery rule (MinerU
strips `× 10^N` from cells) is hard-coded in the prompt.

### `enzyme-kinetics-figure-extractor` (Step 3)

Per-figure vision call (Doubao-Seed-2.0-pro vision). The agent
classifies the figure into a `figure_kind` taxonomy
(`mm_saturation`, `ph_rate_profile`, `time_course`,
`bar_chart_kcat`, `bar_chart_relative_activity`,
`inhibition_curve`, `scatter_kcat_vs_km`, `kinetic_table_image`,
`structure`, `scheme`, `other`) so the normalizer can decide
whether the figure's reactions[] should merge with table rows or
just inform variant-name dedup.

### `enzyme-kinetics-text-extractor` (Step 3)

Per-section LLM call. The hook resolves
`(document_path, item_id)` → full section body (not the 240-char
outline preview), then injects the body plus captions of any
nested tables / figures. The prompt enforces a hard
literal-quotation rule: a reaction row may only be emitted if its
numeric value AND unit appear verbatim in body_text. Hallucinated
rows are caught post-call by a driver-side validator that handles
four real-corpus quirks:

| Quirk | Validator behavior |
|---|---|
| Units glued into value: `"1700 ± 230 s⁻¹"` | Extract leading numeric + every numeric token |
| Nested dict: `{value: 1700, unit: 's⁻¹', uncertainty: 230}` | `_extract_numbers_from_any` recursively unwraps |
| MinerU spaced digits: `"1 7 0 0"` → `1700` | `_normalize_for_validator` iteratively collapses `\d\s+\d` |
| Scientific notation: `kcat/Km=430000` vs body `"4.3·10⁵"` | `_scientific_mantissas` generates mantissa candidates |

Dropped rows are persisted under
`.kinetics_workdir/<artifact>.dropped.json` for audit.

This agent also harvests **full-length protein sequences** from SI
methods text — runs of ≥ 50 uppercase AA codes with a name label.
This is the primary recovery path for `paper_sequences[]`.

### `enzyme-scaffold-mapper` (Step 3.5)

Per-paper LLM call (one per paper, after Step 3 finishes). Sole job:
bind each `variant_name` extracted by Step 3 to the scaffold protein
that variant was constructed from, and pick the right *source* for
the PDB id. Three legitimate output shapes per variant:

| `scaffold_name` | `pdb_id` | `pdb_id_source` | When |
|---|---|---|---|
| set | set | `paper_quote` | LLM saw the PDB id verbatim in a tagged Methods/design section |
| set | null → filled by driver | `registry_hint` | LLM identified the scaffold by name (e.g. `Mb(*)` → "myoglobin"), driver looks up `scaffold_registry.json` |
| null | null | null | Truly unmappable (no family pattern, no tagged evidence) |

Hook (`payload.py`) consumes Step 2's
`sections.{main,si.X}.json` artifacts, filters items where
`is_scaffold_related: true`, and loads only those bodies — keeping
the LLM context to ~3-8K tokens. When the tagger has not yet been
re-run with the scaffold-aware prompt, the LLM gracefully degrades
to variant-name-only inference + the `available_scaffolds` registry
list.

Output is cached to
`papers/extractions/<paper>/.kinetics_workdir/scaffold_mapper.json`
and passed to the normalizer via a new `scaffold_mapping` field
(peer to `text_extraction_data`).

The driver post-processes the LLM output: every `pdb_id_source:
"registry_hint"` entry has its `pdb_id` filled in by looking
`scaffold_name.lower()` up in `scaffold_registry.json`. Misses keep
`pdb_id: null` and degrade to unresolved.

### `scaffold_registry.json`

A small static JSON
(`.claude/agents/enzyme-scaffold-mapper/scaffold_registry.json`)
mapping famous-scaffold name aliases to canonical PDB ids. **Stores
only `name → 4-char PDB id`** — never sequences (those always come
from the RCSB FASTA fetch in the normalizer, so there is no risk of
drift). Initial 10 entries (29 name aliases) cover the dominant
Kemp / catalysis scaffolds:

| Family | Aliases | Canonical PDB |
|---|---|---|
| Sperm whale myoglobin | `myoglobin`, `Mb`, `swMb`, `sperm whale myoglobin` | `1MBN` |
| AlleyCat / calmodulin | `AlleyCat`, `alleycat`, `calmodulin` | `2KZ2` |
| KE07 design | `KE07`, `KE07 design`, `KE-07` | `2RKX` |
| KE59 design | `KE59`, `KE59 design`, `KE-59` | `3B5L` |
| KE70 design | `KE70`, `KE70 design`, `KE-70` | `3NPX` |
| HG3 design | `HG3`, `HG3 design` | `3NYD` |
| KSI | `KSI`, `ketosteroid isomerase`, `ksi` | `1OH0` |
| P450 BM3 | `P450 BM3`, `cytochrome P450 BM3`, `BM3`, `CYP102A1` | `1BU7` |
| Cytochrome c | `cytochrome c`, `cyt c`, `cytochrome-c` | `1HRC` |
| Human serum albumin | `albumin`, `human serum albumin`, `HSA` | `1AO6` |

Adding a new scaffold is a pure data change — append an `entries[]`
record, no code edit needed.

### `enzyme-variant-normalizer` (Step 4)

Deterministic Python (no LLM). Hook-driven — the driver calls it
programmatically via `importlib`, no framework startup tax.
Reconciles per-call extractions into stable canonical variants:

- Collects rows from `text_extraction_data` (the per-call agent
  outputs), `vision_extraction_data` (legacy), plus its own HTML
  parse of `*_content_list.json` (covers tables the LLM
  extractors missed).
- Merges by `variant_name` (case-insensitive), accumulates
  `evidence.sources[]`.
- Resolves `scaffold_pdb_id` → fetches full sequence via the RCSB
  API → applies `canonical_mutations` to build `variant_sequence`.
- **Accepts an optional `scaffold_mapping` kwarg** (Step 3.5 output):
  its `variant_to_scaffold[]` is overlaid onto the legacy
  `_build_document_context` regex parser, so the LLM-derived map
  takes priority while the regex tier is preserved as a safety net
  for Röthlisberger-style explicit design tables.
- Applies **vision-confirmed footnote-letter dedup** before merge
  (see below).

## `kinetics.json` Output Schema

Each paper produces one `papers/extractions/<paper>/kinetics.json`:

```json
{
  "paper_id": "blomberg_2013_precision_kemp_eliminase",
  "main_document_path": "papers/markdowns/.../main/full.md",
  "si_document_paths": ["papers/markdowns/.../SI/.../full.md"],

  "paper_sequences": [
    {
      "design_name": "HG3",
      "sequence": "MAEAAQSVDQ...",
      "length": 300,
      "scaffold_pdb_id": "",
      "num_design_mutations": 0,
      "sources": [
        {"kind": "section", "source_file": "sections.si.X.json", "item_id": 8}
      ]
    }
  ],

  "scaffold_mapping": {
    "paper_id": "blomberg_2013_precision_kemp_eliminase",
    "scaffolds": [
      {"scaffold_name": "HG3", "pdb_id": "3NYD",
       "source_quote": "designed onto the HG3 scaffold (PDB 3NYD)"}
    ],
    "variant_to_scaffold": [
      {"variant_name": "HG3.17", "scaffold_name": "HG3",
       "pdb_id": "3NYD", "pdb_id_source": "registry_hint",
       "confidence": "medium",
       "rationale": "Variant name prefix HG3 matches registry; scaffold mention in Methods"}
    ]
  },

  "vision_dedup_audit": [
    {
      "source": "html_si_t_1_p0",
      "original": "HG3.3bh",
      "rewritten": "HG3.3b",
      "evidence": "vision-confirms-dedup"
    }
  ],

  "unresolved_footnote_candidates": [
    {
      "source": "html_main_table_1_p2",
      "original": "L99A/M102Qt",
      "candidate_base": "L99A/M102Q",
      "trailing": "t",
      "evidence": "no-vision-evidence"
    }
  ],

  "raw_extractions": {
    "tables": [
      {
        "item_id": 0, "source_file": "sections.si.X.json",
        "status": "ok", "duration_s": 187.3,
        "result": { "reactions": [...], "protein_sequences": [...] }
      }
    ],
    "sections": [...],
    "figures": [...]
  },

  "normalized": {
    "normalized_variants": [
      {
        "variant_name": "HG3.17",
        "paper_asserted_variant_name": "HG3.17",
        "canonical_mutations": ["E101A", "K222M", ...],
        "scaffold_pdb_id": "1A53",
        "full_sequence": "PRYLKGW...",
        "variant_sequence": "PRYLKGW...",
        "kinetics": {"kcat": 1.06, "Km": 0.013, "kcat_over_Km": 79000, ...},
        "evidence": {"sources": [...]},
        "normalization_status": "resolved"
      }
    ],
    "normalization_summary": {
      "variant_count": 28,
      "sequence_count": 24,
      "unresolved_count": 4
    }
  },

  "stats": {
    "n_table_calls": 2,
    "n_section_calls": 1,
    "n_figure_calls": 2,
    "n_failed_calls": 0,
    "n_skipped": 0,
    "n_paper_sequences": 5,
    "n_vision_dedup": 1,
    "n_unresolved_footnote_candidates": 1,
    "elapsed_s": 63.6
  }
}
```

## Audit Features

### `paper_sequences[]`

Aggregates protein sequences emitted by **any** extractor (table /
section / figure), deduplicated by `(design_name, sequence)` with
full source-attribution chain. Distinct from
`normalized_variants[].variant_sequence`, which the normalizer
builds by `scaffold_pdb_id → RCSB API → apply_mutations`.
`paper_sequences` is the **paper-asserted truth**; the normalizer
sequence is the **reconstructed truth**. They should agree; when
they don't, paper-asserted wins because the authors literally
typed it.

### `vision_dedup_audit[]`

Each row where the normalizer rewrote a variant_name because the
figure-extractor's roster confirmed it was a footnote-letter
artifact:

- `vision-confirms-dedup` — `<base>` in `figure_variant_names` AND
  `<base><letter>` is NOT → row's `variant_name` rewritten to
  `<base>`, `source_context.footnote_letter_stripped` records the
  letter.

### `unresolved_footnote_candidates[]`

`<base><letter>` shapes that **look** like footnote artifacts but
have insufficient vision evidence:

- `vision-rejects-dedup` — both forms appear in figures → they're
  distinct variants (e.g. HG3.3 vs HG3.3b). Left unchanged.
- `no-vision-evidence` — no figure data to gate. Surfaced for
  human review (covers cases like `merski_2012`'s `*Ht/*Et/*Qt`
  where figures don't display the table-only variants).

## Step 5 — Flat CSV export

Most downstream consumers (notebooks, ML training pipelines,
spreadsheet inspection) want **one row per variant** with the
columns that matter for design analysis: identity, mutations,
sequence, kinetic parameters. The driver auto-produces this flat
projection alongside `kinetics.json`:

| Output | Path | Scope |
|---|---|---|
| **Per-paper** | `papers/extractions/<paper>/kinetics.csv` | One row per normalized variant in that paper |
| **Corpus-wide** | `papers/extractions/_summary.kinetics_variants.csv` | Union across all papers, one row per (paper, variant) |

### Column schema

| Column | Description |
|---|---|
| `paper_id` | Folder name under `papers/extractions/` |
| `variant_name` | Canonical name (post vision-dedup) |
| `enzyme_name`, `aliases` | Free-form labels; aliases pipe-separated |
| `canonical_mutations` | Pipe-separated `WT_pos_to` codes (e.g. `E101A\|K222M`) |
| `num_canonical_mutations` | Length of the above |
| `sequence` | Best available AA sequence — see `sequence_source` priority below |
| `sequence_source` | `paper_asserted` > `pdb_reconstructed` > `scaffold_only` > `none` |
| `sequence_length` | Length of the sequence string |
| `scaffold_pdb_id` | If the normalizer matched to a PDB entry |
| `reaction_name`, `substrates`, `products` | From the canonical reaction; multi-valued lists pipe-separated |
| `kcat`, `kcat_unit` | Raw numeric + the unit string the extractor reported |
| `Km`, `Km_unit` | |
| `kcat_over_Km`, `kcat_over_Km_unit` | |
| `Tm`, `Tm_unit` | Thermal denaturation, when paired with activity |
| `normalization_status` | `resolved` / `partially_resolved` / `unresolved` |
| `n_issues` | Count of normalizer `issues[]` entries |
| `evidence_sources` | Pipe-separated source ids (`text_replica_*`, `html_si_*`, `vision_*`) |

### Sequence priority

The `sequence` column picks the **most authoritative source**.
`_pick_sequence` consults the `paper_sequences[]` index by both
exact `variant_name` AND the base-name (mutation parenthesis
stripped, via `normalizer._variant_base_name`), so e.g. paper-
asserted "HG3.17" sequence matches canonical row "HG3.17 (H201A)".

1. **`paper_asserted`** — `variant_name` (or its base-name) matched
   a `design_name` in `paper_sequences[]`. The sequence the authors
   literally typed into the paper.
2. **`pdb_reconstructed`** — normalizer fetched the scaffold via the
   RCSB API and applied `canonical_mutations`. Computed truth. Now
   substantially more common because Step 3.5's scaffold-mapper
   populates `scaffold_pdb_id` for variants whose names follow a
   recognised family pattern (`Mb(*)`, `AlleyCat*`, `KE07*`, etc.)
   even when the paper doesn't include an explicit design table.
3. **`scaffold_only`** — scaffold sequence with no mutations applied
   (typically when `canonical_mutations` is empty).
4. **`none`** — no scaffold matched, no paper sequence found.

Pipe (`|`) is used as the multi-value separator inside cells so the
CSV can be re-imported with a standard `csv` reader (commas inside
mutation lists would otherwise need quoting).

Full-corpus stats (latest run, 2026-05-14, with Step 3.5 enabled):
**555 rows, 255 with sequence (45.9% coverage; 227 PDB-
reconstructed, 28 paper-asserted)**, 34 papers covered. Up from
14.3% (87/607) before Step 3.5 — a 3.2× improvement driven by
registry-tier resolution of famous-scaffold families.

The remaining gap is dominated by papers whose variants have no
recognisable family-pattern (e.g. de-novo numbered designs in
`listov_2025`, `risso_2020`) and whose scaffold isn't in the
registry yet. Adding new entries to `scaffold_registry.json` is a
data-only change — no code edit needed.

## Performance

| Stage | Calls | Wall-clock (4 workers) |
|---|---|---|
| Step 1 screener | 68 papers | ~3 min |
| Step 2 content-tagger | 68 files | ~14 min |
| Step 3 table + figure + text | 244 calls (58 + 123 + 63) | ~5 min |
| Step 3.5 scaffold-mapper | 34 papers (one LLM each) | ~5-10 min |
| Step 4 + 5 normalize + CSV export | 34 papers (deterministic) | < 1 min |
| **Total** | 414 LLM calls | **~27 min** |

Latest table-only-with-Step-3.5 full re-run: 1631s (27 min) for 34
papers, 59 LLM calls (no figures/text), 555 normalized variants.

Subsequent reruns hit the per-call artifact cache and complete in
under 1 min (driver only re-aggregates, re-normalizes, and re-emits
CSVs). Scaffold-mapper output is cached at
`.kinetics_workdir/scaffold_mapper.json` and bypassed unless
`--force` is passed; the registry-resolution step is always re-run
(deterministic JSON lookup).

## LLM endpoint preflight

Both `scripts/run_kinetics_extraction.py` and
`scripts/run_content_tagger.py` automatically probe the configured
LLM endpoint via `Model.health_check()` before launching the batch:

```bash
[OK] preflight: status=ok model=Doubao-Seed-2.0-pro latency=7.46s
Step 3 driver: 34 papers (workers=4, figures=OFF, text=OFF)
```

A failed preflight returns exit code 2 and aborts the batch — this
catches expired API keys / endpoint outages before the script burns
hours retrying. Bypass with `--skip-preflight` when needed.

The same probe is exposed as a standalone CLI:

```bash
gptase health-check                      # default config
gptase health-check --agent foo          # per-agent config
gptase health-check --json               # machine-readable output
```

Returns exit 0 on `ok`, non-zero on any failure mode
(`auth_failed`, `rate_limited`, `server_error`, `timeout`,
`network_error`, `other_error`).

## See Also

- [`scripts/run_kinetics_extraction.py`](../../scripts/run_kinetics_extraction.py) — the driver entry point
- [`scripts/run_content_tagger.py`](../../scripts/run_content_tagger.py) — Step 2 batch driver (re-run after tagger prompt changes)
- [`.claude/agents/enzyme-kinetics-*/`](../../.claude/agents/) — the per-item extractors
- [`.claude/agents/enzyme-scaffold-mapper/`](../../.claude/agents/enzyme-scaffold-mapper/) — Step 3.5 LLM agent + `scaffold_registry.json`
- [`.claude/agents/enzyme-variant-normalizer/normalizer.py`](../../.claude/agents/enzyme-variant-normalizer/normalizer.py) — Step 4 deterministic merge
- [`gptase health-check`](../../gptase/main.py) — endpoint probe (also called inline by the drivers)
