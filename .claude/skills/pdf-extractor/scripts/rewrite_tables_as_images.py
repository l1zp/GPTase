"""Replace inline `<table>...</table>` HTML in MinerU's main.md with image refs.

For each MinerU paper directory it expects:
  paper_dir/
    main.md
    images/
    *_content_list.json     <- emits the canonical (table_body, img_path) pairs

The canonical mapping comes from `content_list.json`. We do exact string
replacement of `table_body` -> `![Table N](images/<hash>.jpg)`. If the HTML
in main.md doesn't match `table_body` byte-for-byte we fall back to a
fuzzy match on the first/last table tags.

Side effect: writes `tables_index.json` to the paper directory, mapping
`table_<N>` -> stable physical identifiers (page_idx, bbox, caption,
img_path). Downstream consumers should use this rather than re-parse
content_list.json.

Usage:
    python rewrite_tables_as_images.py <paper_dir> [--dry-run]
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys


def find_content_list(paper_dir: Path) -> Path:
    matches = list(paper_dir.glob("*_content_list.json"))
    if not matches:
        raise FileNotFoundError(f"no *_content_list.json in {paper_dir}")
    if len(matches) > 1:
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def rewrite(paper_dir: Path, *, dry_run: bool = False) -> dict:
    main_md = paper_dir / "main.md"
    if not main_md.exists():
        raise FileNotFoundError(main_md)
    cl_path = find_content_list(paper_dir)

    md = main_md.read_text(encoding="utf-8")
    items = json.loads(cl_path.read_text(encoding="utf-8"))

    tables = [x for x in items if x.get("type") == "table"]
    report = {
        "paper": paper_dir.name,
        "tables_total": len(tables),
        "replaced": 0,
        "missing_img": 0,
        "html_not_found": 0,
        "table_details": [],
    }
    tables_index: dict = {}

    for idx, t in enumerate(tables, start=1):
        body = t.get("table_body", "")
        img = t.get("img_path", "")
        caption = (t.get("table_caption") or [""])[0] if t.get("table_caption") else ""
        details = {
            "idx": idx,
            "img_path": img,
            "body_len": len(body),
            "page_idx": t.get("page_idx"),
            "status": None,
        }

        # Always emit a sidecar entry for every table, even if rewrite skips it.
        tables_index[f"table_{idx}"] = {
            "img_path": img,
            "page_idx": t.get("page_idx"),
            "bbox": t.get("bbox", []),
            "caption": caption,
            "footnote": t.get("table_footnote") or [],
            "body_html_chars": len(body),
        }

        if not img:
            details["status"] = "no_img_path"
            report["missing_img"] += 1
            report["table_details"].append(details)
            continue

        replacement = f"![Table {idx}]({img})"

        if body in md:
            md = md.replace(body, replacement, 1)
            details["status"] = "exact_match"
            report["replaced"] += 1
        else:
            # Fuzzy fallback: locate the table block by its first 80 / last 40 chars.
            head = re.escape(body[:80])
            tail = re.escape(body[-40:])
            pattern = re.compile(head + r".*?" + tail, re.DOTALL)
            m = pattern.search(md)
            if m:
                md = md[:m.start()] + replacement + md[m.end():]
                details["status"] = "fuzzy_match"
                report["replaced"] += 1
            else:
                details["status"] = "html_not_found"
                report["html_not_found"] += 1

        report["table_details"].append(details)

    if not dry_run:
        backup = main_md.with_suffix(".md.pre_rewrite")
        if not backup.exists():
            backup.write_text(main_md.read_text(encoding="utf-8"), encoding="utf-8")
        main_md.write_text(md, encoding="utf-8")
        sidecar = paper_dir / "tables_index.json"
        sidecar.write_text(
            json.dumps(tables_index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        report["sidecar"] = str(sidecar)

    report["new_main_md_chars"] = len(md)
    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: rewrite_tables_as_images.py <paper_dir> [--dry-run]")
        sys.exit(1)
    paper_dir = Path(sys.argv[1]).resolve()
    dry = "--dry-run" in sys.argv[2:]
    r = rewrite(paper_dir, dry_run=dry)
    print(json.dumps(r, indent=2, ensure_ascii=False))
