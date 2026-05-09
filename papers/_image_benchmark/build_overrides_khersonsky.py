"""Generate manual_overrides.json entry for khersonsky_2012 SI Table S11.

Same pattern as build_overrides_broom.py but addressing a different
MinerU failure mode: scientific notation like `1.5×10^4` is encoded in
the PDF text layer as adjacent digits `1.5x104` (the superscript is a
separate text run rendered at smaller font but PyMuPDF concatenates it
as plain digits, losing the exponent boundary). MinerU's HTML
extraction inherits the loss AND additionally mis-aligns the last two
columns for the Designed KE70 row.

We pull the PDF text layer, apply a superscript-recovery heuristic
(`\\d+x10\\d+` -> `<mantissa>×10^<exponent>`, single-digit exponent),
hand-align the irregular Evolved KE59 sub-rows (4 substrates), and
write the cleaned CSV into manual_overrides.json.
"""
import json
from pathlib import Path
import re

import fitz

ROOT = Path("/Users/ryanxu/CodeBase/GPTase")
PDF = ROOT / "papers/pdfs/khersonsky_2012_bridging_gaps_kemp_ke59/SI_1121063109_Appendix.pdf"
OVERRIDES = ROOT / "papers/_image_benchmark/manual_overrides.json"


def fix_superscript(value: str) -> str:
    """`1.5x104` -> `1.5×10^4`, `(6.0±0.2)x104` -> `(6.0±0.2)×10^4`.

    Single-digit exponent assumed (kinetics papers rarely exceed 10^9).
    Targets the `x10<digit>` / `×10<digit>` substring directly so any
    mantissa (parenthesized, with ± uncertainty, prefixed with ~)
    works without hand-coding each form.
    """
    return re.sub(r"[x×]\s*10(\d)", r"×10^\1", value)


# Hand-aligned table content read from PDF page 43 (Table S11).
# Format: (variant, substrate, kcat_over_Km, fold_improvement, kcat_over_kuncat, n_mutations)
ROWS = [
    # Designed KE07
    ("Designed KE07", "5-nitrobenzisoxazole (4.1)", "12.2±0.1", "", "1.5x104", "13"),
    # Evolved KE07
    ("Evolved KE07 R7 10/11G", "5-nitrobenzisoxazole (4.1)", "2590±300", "~210",
     "1.2x106", "20"),
    # Designed KE59
    ("Designed KE59", "5-nitrobenzisoxazole (4.1)", ">160", "", "~2.5x105", "10"),
    # Evolved KE59 R13 3/11H — 4 substrate sub-rows
    ("Evolved KE59 R13 3/11H", "5-nitrobenzisoxazole (4.1)", "(6.0±0.2)x104", "~380",
     "0.8x107", "31 (9 consensus mutations)"),
    ("Evolved KE59 R13 3/11H", "5,7-dichloro-benzisoxazole (4.3)", "(0.57±0.02)x106",
     "~100", "2.46x107", ""),
    ("Evolved KE59 R13 3/11H", "6-chlorobenzisoxazole (6.1)", "2150±40", "~430",
     "1.92x107", ""),
    ("Evolved KE59 R13 3/11H", "5-fluorobenzisoxazole (6.8)", "315±32", ">2000",
     "0.7x107", ""),
    # Designed KE70 — MinerU mis-aligned this row, putting "1.2x10" + "16" as
    # separate columns (i.e. it dropped the superscript "5" entirely). The
    # truth is kcat/kuncat = 1.2×10^5, # mutations = 16.
    ("Designed KE70", "5-nitrobenzisoxazole (4.1)", "126±4", "", "1.2x105", "16"),
    # Evolved KE70
    ("Evolved KE70 R6 6/10A", "5-nitrobenzisoxazole (4.1)", "(5.5±0.5)x104", "435",
     "4.6x106", "19 (two insertions)"),
]

HEADERS = [
    "variant", "Substrate (pKa of the salicylonitrile)", "kcat/KM (s⁻¹ M⁻¹)",
    "fold improvement in catalytic efficiency", "kcat/kuncat",
    "# mutations relative to native template"
]


def to_csv(headers, rows) -> str:
    import csv as csv_mod
    import io
    buf = io.StringIO()
    w = csv_mod.writer(buf, quoting=csv_mod.QUOTE_ALL)
    w.writerow(headers)
    for r in rows:
        # apply superscript fix per cell
        w.writerow([fix_superscript(c) for c in r])
    return buf.getvalue().rstrip()


def main() -> None:
    pdf = fitz.open(PDF)
    # Cross-check that page 43 still contains Table S11 (sanity)
    assert "Table S11" in pdf[43].get_text(), "Table S11 not on expected page"

    csv_str = to_csv(HEADERS, ROWS)

    overrides = (json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {})
    paper_prefix = "khersonsky_2012_bridging_gaps_kemp_ke59/SI_1121063109_Appendix"
    overrides[f"{paper_prefix}/t_17"] = {
        "ground_truth_csv":
        csv_str,
        "source":
        "manual: PDF text layer (PyMuPDF) + superscript recovery + column-alignment fix",
        "notes": ("MinerU lost superscripts (1.5×10⁴ rendered as `1.5x104` "
                  "in PDF text layer because superscript is a separate "
                  "text run); also mis-aligned Designed KE70's kcat/kuncat "
                  "column with the # mutations column."),
    }

    OVERRIDES.write_text(json.dumps(overrides, indent=2, ensure_ascii=False))
    print(f"wrote {OVERRIDES} ({len(overrides)} entries)")
    print()
    print("=== preview (first 600 chars) ===")
    print(csv_str[:600])
    print()
    print("=== row count: " + str(len(ROWS)) + " data rows ===")


if __name__ == "__main__":
    main()
