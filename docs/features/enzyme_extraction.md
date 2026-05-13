# Enzyme Kinetics Extraction Pipeline

A multi-step pipeline for harvesting Michaelis-Menten parameters
(`kcat`, `Km`, `kcat/Km`, `Tm`) and full-length protein sequences from
a corpus of designed-enzyme papers. The pipeline is **driven by a
Python script**, not a Coordinator plan — each item (table / figure /
section) is dispatched to a specialized agent and results are
aggregated and normalized per paper.

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
                       enzyme-variant-normalizer  ← Step 4
                       (deterministic merge +
                        vision-confirmed dedup)
                                  │
                                  ▼
              papers/extractions/<paper>/kinetics.json
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

## Performance

| Stage | Calls | Wall-clock (4 workers) |
|---|---|---|
| Step 1 screener | 68 papers | ~3 min |
| Step 2 content-tagger | 68 files | ~14 min |
| Step 3 table + figure + text | 244 calls (58 + 123 + 63) | ~5 min |
| **Total** | 380 LLM calls | **~22 min** |

Subsequent reruns hit the per-call artifact cache and complete in
under 1 min (driver only re-aggregates and re-normalizes).

## See Also

- [`scripts/run_kinetics_extraction.py`](../../scripts/run_kinetics_extraction.py) — the driver entry point
- [`.claude/agents/enzyme-kinetics-*/`](../../.claude/agents/) — the five specialized agents
- [`.claude/agents/enzyme-variant-normalizer/normalizer.py`](../../.claude/agents/enzyme-variant-normalizer/normalizer.py) — Step 4 deterministic merge
