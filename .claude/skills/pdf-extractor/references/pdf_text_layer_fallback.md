# PDF Text Layer Fallback

When MinerU's HTML/CSV extraction garbles a table — splits cells across
random `colspan`/`rowspan` grids, swaps rows, or drops content entirely —
**check if the source PDF has a text layer** before resorting to vision
OCR or hand transcription.

## When to reach for this

MinerU's layout model interprets PDFs visually. It usually wins on
clean grid tables, but it fails predictably on:

- Tables with very long single-cell content (DNA / amino-acid
  sequences, long molecule SMILES, paragraph-style notes embedded in
  cells)
- Multi-page tables split across page breaks
- Tables where the column widths vary dramatically (mixed kinetic
  values + structured prose)

In every case where MinerU stumbles, **the PDF text layer often has
the data laid out cleanly** — because most modern publishers embed
selectable text via PDF fonts, not via raster scans. PyMuPDF reads
that text directly, byte-for-byte, no OCR, no vision.

## When NOT to use this

- **Scanned / image-only PDFs** — no text layer to extract. Use
  vision OCR (the existing `vision-image-analyzer` agent path) or
  enable MinerU's `is_ocr=True`.
- **Tables encoded as embedded images** in an otherwise-text PDF.
  PyMuPDF returns an empty string for those regions.
- **When you only need the high-level structure** that MinerU
  already gives you. Re-extracting via PyMuPDF means re-implementing
  the table boundary detection.

## How

```python
import fitz  # PyMuPDF

pdf = fitz.open("path/to/paper.pdf")
print(f"pages: {pdf.page_count}")

# Find the page that holds the table you care about
for i in range(pdf.page_count):
    txt = pdf[i].get_text()
    if "Codon-optimized" in txt:           # caption fragment
        target_page = i
        break

raw = pdf[target_page].get_text()
```

`get_text()` returns the page's text as a single string with newlines
between text runs. Reading order roughly follows the visual layout but
isn't perfectly reliable for multi-column pages.

To split a table into rows, anchor on **stable markers** that appear
once per row — typically the row's identifier in the first column:

```python
import re

ENZYMES = ["HG3", "HG3.3b", "HG3.7", "HG3.14", "HG3.17", "HG4"]
# Match longer names first so HG3 doesn't eat HG3.3b
name_pat = "|".join(re.escape(e) for e in sorted(ENZYMES, key=len, reverse=True))
matches = list(re.finditer(rf"\b({name_pat})\b\s*\n", raw))

rows = {}
for i, m in enumerate(matches):
    name = m.group(1)
    start = m.end()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
    chunk = raw[start:end]
    # Filter to the alphabet of the value column (DNA, protein, numbers)
    seq = "".join(re.findall(r"[ACGT]", chunk))
    rows[name] = seq
```

The trick that makes this robust: only keep characters from the
expected alphabet (`[ACGT]` for DNA, `[A-IK-NP-TVWY]` for
single-letter amino acids, `[\d.,e+\-±]` for numerical kinetics).
Whitespace, page numbers, footnotes, and stray symbols all get
discarded automatically.

## Caveat: superscripts vanish in PDF text layer

PyMuPDF's `get_text()` follows the visual reading order *but it
flattens font-size changes*. Scientific notation rendered as
`1.5 × 10⁴` (with the `4` as a smaller superscript text run) becomes
the plain string `1.5x104` after extraction — the boundary between
mantissa and exponent is lost. This is a property of how the PDF
encodes the page, not a PyMuPDF bug; MinerU inherits the same loss
because its layout model also reads the text stream.

Detection is straightforward — the corpus-wide pattern
`\d+x10\d+` shows up only in scientific notation contexts. Fix:

```python
import re
def fix_superscript(value: str) -> str:
    """1.5x104 -> 1.5×10^4, (6.0±0.2)x104 -> (6.0±0.2)×10^4.

    Targets the `x10<digit>` substring directly so the mantissa shape
    (parenthesized, signed, prefixed with ~, etc.) does not matter.
    Single-digit exponent is assumed because kinetics rarely exceeds
    10^9; longer trailing digits stay attached to the next column.
    """
    return re.sub(r"[x×]\s*10(\d)", r"×10^\1", value)
```

Apply per-cell after extracting the table and before writing the
ground-truth CSV. Example fixes seen in the corpus:

| Raw PDF text | After heuristic |
|---|---|
| `1.5x104` | `1.5×10^4` |
| `~2.5x105` | `~2.5×10^5` |
| `(6.0±0.2)x104` | `(6.0±0.2)×10^4` |
| `(0.57±0.02)x106` | `(0.57±0.02)×10^6` |
| `2.46x107` | `2.46×10^7` |

Watch out for two adjacent column values getting glued by MinerU's
HTML pass when the superscript is lost: in `khersonsky_2012` Table
S11, MinerU emitted `"1.2x10","16"` for what should have been
`"1.2×10^5"` (kcat/kuncat) + `"16"` (# mutations) — the mantissa was
dropped entirely because `5` looked like noise sandwiched between
two columns. When this happens, hand-correct the column alignment in
the override file rather than trusting MinerU's column boundaries.

## Real-world recovery: broom_2020 SI

The pdf-extractor pipeline ran into MinerU's worst-case behavior on
two tables in `broom_2020_ensemble_enzyme_design/SI_*MOESM1_ESM`:

| Table | MinerU output | After PyMuPDF |
|---|---|---|
| Supp. Table 1 (amino-acid sequences, 6 enzymes) | His-tag suffix `QDLQQGSIEGRGHHHHHH` was placed at the *next* row's head (off-by-one row alignment) | Each row gets its full 318/324 aa with the His-tag at the correct end |
| Supp. Table 7 (codon-optimized DNA, 6 × ~957 bp) | 105 `<td>` cells with random `colspan=11`/`rowspan=4` partitions; sequences scrambled across cells, HG3.3b's marker disappears, HG4 captures only 93 bp | All six 957 bp sequences recovered byte-perfect from the text layer |

The recovery script lives at
`papers/_image_benchmark/build_overrides_broom.py` (one-shot) and
writes both corrected CSVs into
`papers/_image_benchmark/manual_overrides.json` so the
`build_self_verify_html.py` viewer renders the fixed ground truth
with a "manual override" badge.

## Real-world recovery: khersonsky_2012 Table S11

Different failure mode — a kinetics summary table where every
`kcat/kuncat` cell looked like `1.5x104` instead of `1.5×10^4`. PDF
text layer had the same flattened form (superscript lost during
encoding), so PyMuPDF alone wasn't enough — needed the
`fix_superscript` heuristic above. Plus a column-alignment patch for
the Designed KE70 row where MinerU dropped the exponent digit `5`
entirely and shifted the next column. Recovery script:
`papers/_image_benchmark/build_overrides_khersonsky.py`.

## Generalization

Any time the v9 pipeline downstream spots a table where the MinerU
csv_preview is obviously broken (missing rows, extra empty cells,
sequence cross-contamination), the repair pattern is:

1. Locate the source PDF (`papers/pdfs/<paper>/...`)
2. Find the relevant page via caption keyword search
3. Scan the row markers for the anchor column
4. Filter on the value column's alphabet
5. Save the recovered CSV under `manual_overrides.json` with a
   `notes` entry documenting why MinerU failed

Do not edit `paper_data.json` or `benchmark.json` by hand — those are
regenerated. The override file is the canonical place for human
corrections.
