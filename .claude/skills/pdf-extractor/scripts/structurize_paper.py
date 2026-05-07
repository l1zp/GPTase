"""Structurize MinerU's content_list.json into paper_data.json buckets.

For one paper directory, produces a `paper_data.json` next to the
existing artifacts that flattens MinerU's per-block content list into
five typed buckets ready for downstream agents:

    sections / tables / figures / equations / metadata

The output schema is stable and downstream-friendly:
- Each item gets a stable string id (s_1, t_1, f_1, e_1) so downstream
  agents can reference items by id rather than array index.
- Tables include a pre-parsed `csv_preview` so prose extractors can
  cross-validate their HTML reading against canonical CSV without
  needing to call any LLM tool.
- Ghost tables (table items without HTML body, only a cropped image)
  are simultaneously listed in `tables[]` (with `ghost=true`) and
  `figures[]` (with `from_ghost_table=true`) so the figure-vision path
  can OCR them.

Reuses `_html_table_to_csv` from gptase.agents.enzyme_variant_normalizer
to avoid duplicating regex-based HTML parsing.

Usage:
    python structurize_paper.py <paper_dir> [--dry-run]
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

# Reuse the byte-exact HTML->CSV converter from the normalizer module.
# The module is dependency-free aside from stdlib + urllib, so importing
# it from a script context works without pulling the wider gptase stack.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from gptase.agents.enzyme_variant_normalizer import _html_table_to_csv  # noqa: E402


def find_content_list(paper_dir: Path) -> Path:
    matches = list(paper_dir.glob("*_content_list.json"))
    if not matches:
        raise FileNotFoundError(f"no *_content_list.json in {paper_dir}")
    if len(matches) > 1:
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def _clean_text(value: str) -> str:
    return (value or "").strip()


def _pick_caption(captions) -> str:
    """MinerU emits caption as a list (may be empty); pick first non-blank."""
    if not isinstance(captions, list):
        return ""
    for c in captions:
        text = _clean_text(str(c))
        if text:
            return text
    return ""


def structurize(paper_dir: Path) -> dict:
    """Build paper_data.json buckets from a MinerU paper directory."""
    cl_path = find_content_list(paper_dir)
    items = json.loads(cl_path.read_text(encoding="utf-8"))

    sections: list = []
    tables: list = []
    figures: list = []
    equations: list = []

    # State tracker: which section is "currently open" so subsequent
    # text/table/figure items get attributed to it.
    current_section: dict | None = None

    def open_section(title: str, page_idx) -> dict:
        sec_id = f"s_{len(sections) + 1}"
        sec = {
            "section_id": sec_id,
            "title": title,
            "page_idx": page_idx,
            "body_text": "",
            "table_ids": [],
            "figure_ids": [],
        }
        sections.append(sec)
        return sec

    # Always start with an implicit "Front Matter" section so leading text
    # (title, author list, abstract before any heading) has a home.
    current_section = open_section("Front Matter", 0)

    body_chunks: dict = {current_section["section_id"]: []}

    for item in items:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        page_idx = item.get("page_idx")

        if item_type == "discarded":
            continue

        if item_type == "text":
            text = _clean_text(item.get("text", ""))
            if not text:
                continue
            # text_level=1 means a section heading. MinerU also occasionally
            # emits text_level=2/3 for sub-headings; we treat any non-null
            # text_level as a heading boundary.
            level = item.get("text_level")
            if level is not None:
                current_section = open_section(text, page_idx)
                body_chunks.setdefault(current_section["section_id"], [])
            else:
                body_chunks.setdefault(current_section["section_id"], []).append(text)
            continue

        if item_type == "table":
            html = item.get("table_body") or ""
            img_path = item.get("img_path") or ""
            caption = _pick_caption(item.get("table_caption"))
            footnote = _pick_caption(item.get("table_footnote"))
            csv_preview = _html_table_to_csv(html) if html else ""
            ghost = not bool(html)
            tbl_id = f"t_{len(tables) + 1}"
            tables.append({
                "table_id": tbl_id,
                "html": html,
                "caption": caption,
                "footnote": footnote,
                "img_path": img_path,
                "page_idx": page_idx,
                "csv_preview": csv_preview,
                "ghost": ghost,
            })
            current_section["table_ids"].append(tbl_id)
            # Mirror ghost tables into the figures bucket so vision path
            # can OCR them. Use a distinct figure id so the two routes do
            # not collide downstream.
            if ghost and img_path:
                fig_id = f"f_{len(figures) + 1}"
                figures.append({
                    "figure_id": fig_id,
                    "img_path": img_path,
                    "caption": caption or f"(ghost table, page {page_idx})",
                    "page_idx": page_idx,
                    "from_ghost_table": True,
                    "linked_table_id": tbl_id,
                })
                current_section["figure_ids"].append(fig_id)
            continue

        if item_type == "image":
            img_path = item.get("img_path") or ""
            if not img_path:
                continue
            caption = _pick_caption(item.get("image_caption"))
            footnote = _pick_caption(item.get("image_footnote"))
            fig_id = f"f_{len(figures) + 1}"
            figures.append({
                "figure_id": fig_id,
                "img_path": img_path,
                "caption": caption,
                "footnote": footnote,
                "page_idx": page_idx,
                "from_ghost_table": False,
            })
            current_section["figure_ids"].append(fig_id)
            continue

        if item_type == "equation":
            latex = item.get("text") or ""
            if not latex:
                continue
            eq_id = f"e_{len(equations) + 1}"
            equations.append({
                "eq_id": eq_id,
                "latex": latex,
                "text_format": item.get("text_format", "latex"),
                "page_idx": page_idx,
            })
            continue

        # unknown type - log it via the metadata bucket but don't crash
        # so future MinerU schema additions don't silently break us.

    # Flush body_text per section.
    for sec in sections:
        chunks = body_chunks.get(sec["section_id"], [])
        sec["body_text"] = "\n\n".join(chunks)

    metadata = {
        "source_content_list": cl_path.name,
        "total_items": len(items),
        "section_count": len(sections),
        "table_count": len(tables),
        "table_ghost_count": sum(1 for t in tables if t["ghost"]),
        "figure_count": len(figures),
        "equation_count": len(equations),
    }

    return {
        "source_file": "main.md",
        "sections": sections,
        "tables": tables,
        "figures": figures,
        "equations": equations,
        "metadata": metadata,
    }


def write_paper_data(paper_dir: Path, *, dry_run: bool = False) -> dict:
    payload = structurize(paper_dir)
    if not dry_run:
        out = paper_dir / "paper_data.json"
        out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        payload["_written_to"] = str(out)
    return payload


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: structurize_paper.py <paper_dir> [--dry-run]")
        sys.exit(1)
    paper_dir = Path(sys.argv[1]).resolve()
    dry = "--dry-run" in sys.argv[2:]
    result = write_paper_data(paper_dir, dry_run=dry)
    summary = {
        k: v
        for k, v in result.items() if k in ("source_file", "metadata", "_written_to")
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
