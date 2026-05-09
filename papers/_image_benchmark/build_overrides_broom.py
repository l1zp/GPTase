"""Generate manual_overrides.json entries for broom_2020 SI rows 11 & 12.

Pulls clean sequences from the PDF text layer (PyMuPDF) and writes both
override entries into papers/_image_benchmark/manual_overrides.json.
"""
import csv
import io
import json
from pathlib import Path
import re

import fitz

ROOT = Path("/Users/ryanxu/CodeBase/GPTase")
PDF = ROOT / "papers/pdfs/broom_2020_ensemble_enzyme_design/SI_41467_2020_18619_MOESM1_ESM.pdf"
OVERRIDES = ROOT / "papers/_image_benchmark/manual_overrides.json"

ENZYMES = ["HG3", "HG3.3b", "HG3.7", "HG3.14", "HG3.17", "HG4"]
MUT_COUNTS = {
    "HG3": "–",
    "HG3.3b": "6",
    "HG3.7": "7",
    "HG3.14": "12",
    "HG3.17": "17",
    "HG4": "8"
}


def extract_table(page_idx: int, alphabet_re: str, header_keyword: str,
                  pdf: fitz.Document) -> dict:
    txt = pdf[page_idx].get_text()
    after_hdr = txt.split(header_keyword, 1)[1] if header_keyword in txt else txt
    name_pat = "|".join(re.escape(e) for e in sorted(ENZYMES, key=len, reverse=True))
    matches = list(re.finditer(rf"\b({name_pat})\b\s*\n", after_hdr))
    out = {}
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(after_hdr)
        chunk = after_hdr[start:end]
        seq = "".join(re.findall(alphabet_re, chunk))
        out[name] = seq
    return out


def to_csv(headers: list, rows: list) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL)
    w.writerow(headers)
    for r in rows:
        w.writerow(r)
    return buf.getvalue().rstrip()


def main() -> None:
    pdf = fitz.open(PDF)
    page_aa = next(i for i in range(pdf.page_count)
                   if "Amino-acid sequences" in pdf[i].get_text())
    page_dna = next(i for i in range(pdf.page_count)
                    if "Codon-optimized" in pdf[i].get_text())
    print(f"AA seq page = {page_aa}, DNA page = {page_dna}")

    aa = extract_table(page_aa, r"[A-IK-NP-TVWY]", "Sequencea", pdf)
    if not aa:
        aa = extract_table(page_aa, r"[A-IK-NP-TVWY]", "Sequence", pdf)
    # HG4 grabs trailing characters from a following paragraph; trim at the
    # His-tag terminator HHHHHH (always present in this corpus).
    for e, s in aa.items():
        m = re.search(r"H{6}", s)
        if m:
            aa[e] = s[:m.end()]

    dna = extract_table(page_dna, r"[ACGT]", "DNA sequence", pdf)

    # Build CSVs
    csv_t1 = to_csv(
        ["Enzyme", "# mutations from HG3", "Sequence"],
        [[e, MUT_COUNTS[e], aa.get(e, "")] for e in ENZYMES],
    )
    csv_t7 = to_csv(
        ["Enzyme", "DNA sequence"],
        [[e, dna.get(e, "")] for e in ENZYMES],
    )

    # Load existing overrides if any, then add/replace these two
    if OVERRIDES.exists():
        overrides = json.loads(OVERRIDES.read_text())
    else:
        overrides = {}

    paper_prefix = "broom_2020_ensemble_enzyme_design/SI_41467_2020_18619_MOESM1_ESM"
    overrides[f"{paper_prefix}/t_1"] = {
        "ground_truth_csv":
        csv_t1,
        "source":
        "manual: extracted from PDF text layer (PyMuPDF) on broom_2020 SI Table 1",
        "notes":
        "MinerU's csv_preview placed each His-tag tail at the *next* row's head; PDF extraction has correct row boundaries.",
    }
    overrides[f"{paper_prefix}/t_7"] = {
        "ground_truth_csv":
        csv_t7,
        "source":
        "manual: extracted from PDF text layer (PyMuPDF) on broom_2020 SI Table 7",
        "notes":
        "MinerU's HTML cells were severely scrambled (105 cells with rowspan/colspan grid). PDF text layer recovers exact codon-optimized sequences.",
    }

    OVERRIDES.write_text(json.dumps(overrides, indent=2, ensure_ascii=False))
    print(f"\nwrote {OVERRIDES}")
    print(f"  entries: {len(overrides)}")
    print()
    print("=== Row 11 (t_1) preview ===")
    print(csv_t1[:400])
    print("...")
    print()
    print("=== Row 12 (t_7) preview ===")
    print(csv_t7[:400])
    print("...")


if __name__ == "__main__":
    main()
