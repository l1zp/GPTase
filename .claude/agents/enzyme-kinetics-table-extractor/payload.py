"""Resolve a single MinerU table payload by (document_path, item_id).

Mirrors the id-assignment logic of
``enzyme-kinetics-content-tagger/outline.py:build_outline`` so that an
``item_id`` produced by Step 2 maps unambiguously back to one
``content_list.json`` entry. The hook then hands that entry's caption,
table_body HTML, and parent section heading to the LLM — no Read tool
calls, no markdown navigation needed.

Falls back gracefully when ``paper_data.json`` (the pdf-extractor
post-processing artifact, present in only ~half the corpus) is absent;
``content_list.json`` is universal.

Also exposes a deterministic ``html_table_to_grid`` parser that turns
MinerU's <table> HTML into a 2-D list of strings — fed alongside the
raw HTML in the LLM prompt so the model doesn't have to do its own
structural parsing (which is the dominant source of reasoning-loop
timeouts on complex tables like khersonsky_2012 Table 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from html.parser import HTMLParser
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TablePayload:
    item_id: int
    page_idx: Optional[int]
    caption: str
    footnote: str
    table_body_html: str
    img_path: Optional[str]
    parent_section_heading: Optional[str]
    csv_preview: Optional[str] = None
    # Diagnostic only — not part of the LLM prompt
    content_list_index: int = -1


def _content_list_for(doc_path: Path) -> Optional[Path]:
    parent = doc_path.parent if doc_path.is_file() else doc_path
    matches = sorted(parent.glob("*_content_list.json"))
    return matches[0] if matches else None


def _walk_for_item(items: List[Dict[str, Any]], target_id: int) -> Optional[int]:
    """Re-do outline.py's id assignment, return the content_list index for target_id.

    Mirrors ``outline.build_outline`` exactly:
    - Skip ``discarded``.
    - ``text`` with ``text_level`` (heading) → gets an id.
    - ``text`` without text_level (body) → does NOT get its own id, BUT
      if no section is open yet, outline.py opens a synthetic
      "(prologue)" section that DOES consume an id. That synthetic
      section maps to the FIRST body text item.
    - ``table`` / ``image`` → always get an id.
    """
    next_id = 0
    section_open = False
    for ci_idx, it in enumerate(items):
        kind = it.get("type")
        if kind == "discarded":
            continue
        if kind == "text":
            if it.get("text_level"):
                if next_id == target_id:
                    return ci_idx
                next_id += 1
                section_open = True
            else:
                # body text — no id unless this opens the synthetic prologue
                if not section_open:
                    if next_id == target_id:
                        return ci_idx
                    next_id += 1
                    section_open = True
            continue
        if kind in ("table", "image"):
            if next_id == target_id:
                return ci_idx
            next_id += 1
    return None


def _find_parent_section_heading(items: List[Dict[str, Any]],
                                 ci_idx: int) -> Optional[str]:
    """Walk backward from ci_idx to find the nearest preceding heading text."""
    for i in range(ci_idx - 1, -1, -1):
        it = items[i]
        if it.get("type") == "text" and it.get("text_level"):
            return (it.get("text") or "").strip()
    return None


def _maybe_paper_data_table_csv(parent: Path, table_ordinal: int) -> Optional[str]:
    """Return csv_preview for the Nth table in paper_data.json, or None.

    paper_data.json is opt-in (only ~42 dirs in the corpus). When
    present, its ``tables`` list is in document order, so the Nth table
    in our outline maps to the Nth entry. Strictly an enrichment.
    """
    pd_path = parent / "paper_data.json"
    if not pd_path.is_file():
        return None
    try:
        pd = json.loads(pd_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    tables = pd.get("tables") if isinstance(pd, dict) else None
    if not isinstance(tables, list):
        return None
    if table_ordinal < 0 or table_ordinal >= len(tables):
        return None
    entry = tables[table_ordinal]
    if not isinstance(entry, dict):
        return None
    csv_preview = entry.get("csv_preview")
    return csv_preview if isinstance(csv_preview, str) and csv_preview.strip() else None


def resolve_table_payload(doc_path: str, item_id: int) -> TablePayload:
    """Locate the table at item_id and return its full payload.

    Args:
        doc_path: Absolute path to the body markdown (or its directory).
        item_id: The ``id`` from Step 2's sections.X.json items array.

    Raises:
        FileNotFoundError: when no content_list.json sibling is found.
        IndexError: when item_id does not exist in the outline.
        ValueError: when the resolved item is not a table.
    """
    p = Path(doc_path).expanduser()
    cl_path = _content_list_for(p)
    if cl_path is None:
        raise FileNotFoundError(f"No *_content_list.json sibling for {p}")
    items: List[Dict[str, Any]] = json.loads(cl_path.read_text(encoding="utf-8"))

    ci_idx = _walk_for_item(items, item_id)
    if ci_idx is None:
        raise IndexError(f"item_id {item_id} not found in outline of {cl_path.name}")
    entry = items[ci_idx]
    if entry.get("type") != "table":
        raise ValueError(
            f"item_id {item_id} resolves to type={entry.get('type')!r}, expected 'table'"
        )

    table_caption_list = entry.get("table_caption") or []
    table_footnote_list = entry.get("table_footnote") or []
    caption = (table_caption_list[0] if table_caption_list else "").strip()
    footnote = " ".join(s.strip() for s in table_footnote_list).strip()
    body_html = entry.get("table_body") or ""
    img_path = entry.get("img_path")

    parent_heading = _find_parent_section_heading(items, ci_idx)

    # Compute table ordinal (Nth table in document order) for paper_data.json lookup
    table_ordinal = sum(1 for it in items[:ci_idx]
                        if it.get("type") == "table" and it.get("type") != "discarded")
    csv_preview = _maybe_paper_data_table_csv(cl_path.parent, table_ordinal)

    return TablePayload(
        item_id=item_id,
        page_idx=entry.get("page_idx"),
        caption=caption,
        footnote=footnote,
        table_body_html=body_html,
        img_path=img_path,
        parent_section_heading=parent_heading,
        csv_preview=csv_preview,
        content_list_index=ci_idx,
    )


class _TableGridParser(HTMLParser):
    """Stdlib HTML parser that flattens <table> rows × cells, expanding colspan.

    Rowspan is rare in MinerU output; we annotate cells that declare
    rowspan but do not propagate them to subsequent rows. Nested tables
    are NOT supported (would mangle the flat row structure) — we only
    look at the outermost <tr>/<td>/<th> chain.
    """

    def __init__(self) -> None:
        super().__init__()
        self.rows: List[List[str]] = []
        self._row: Optional[List[str]] = None
        self._cell: Optional[List[str]] = None
        self._colspan: int = 1
        self._depth_table: int = 0

    def handle_starttag(self, tag: str, attrs):
        attrs_d = dict(attrs)
        if tag == "table":
            self._depth_table += 1
            return
        if tag == "tr" and self._depth_table >= 1:
            self._row = []
            return
        if tag in ("td", "th") and self._row is not None:
            self._cell = []
            try:
                self._colspan = int(attrs_d.get("colspan") or "1")
            except ValueError:
                self._colspan = 1
            return

    def handle_endtag(self, tag: str):
        if tag == "table":
            self._depth_table = max(0, self._depth_table - 1)
            return
        if tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            return
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            text = " ".join("".join(self._cell).split()).strip()
            for _ in range(max(self._colspan, 1)):
                self._row.append(text)
            self._cell = None
            self._colspan = 1
            return

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def html_table_to_grid(html: str) -> List[List[str]]:
    """Parse MinerU <table> HTML into a 2-D list of cell strings.

    Cells with ``colspan="N"`` are replicated N times so column indices
    stay aligned across header / data rows. Empty input → empty list.
    """
    if not html or "<table" not in html:
        return []
    parser = _TableGridParser()
    parser.feed(html)
    parser.close()
    return parser.rows


def render_grid_as_markdown(grid: List[List[str]]) -> str:
    """Render a 2-D grid as a pipe-delimited markdown-style table.

    No padding for visual alignment — LLMs don't care. Rectangularizes
    by padding short rows with empty cells so column indices are
    unambiguous.
    """
    if not grid:
        return "(empty grid)"
    width = max(len(r) for r in grid)
    out: List[str] = []
    for i, row in enumerate(grid):
        padded = row + [""] * (width - len(row))
        out.append("| " + " | ".join(padded) + " |")
        if i == 0:
            out.append("| " + " | ".join(["---"] * width) + " |")
    return "\n".join(out)


def render_table_for_llm(payload: TablePayload) -> str:
    """Compose the prompt-injection block from a TablePayload.

    Layout (LLM reads top-to-bottom):
    1. Provenance header (item_id / page / caption / footnote / parent section)
    2. **Cleaned grid** — deterministic Python parse of the HTML, the
       authoritative source for row × column structure
    3. Optional csv_preview from paper_data.json (when present, ~half
       the corpus) — independent sanity reference
    4. Raw MinerU HTML — fallback when grid parser drops something
       unusual (rowspan, nested cells, multi-line cells)
    """
    lines: List[str] = []
    lines.append("## Resolved table payload\n")
    lines.append(f"- item_id: {payload.item_id}")
    lines.append(f"- page_idx: {payload.page_idx}")
    if payload.parent_section_heading:
        lines.append(f"- parent_section: {payload.parent_section_heading}")
    else:
        lines.append("- parent_section: (none — table appears before any heading)")
    lines.append(f"- caption: {payload.caption or '(no caption)'}")
    if payload.footnote:
        lines.append(f"- footnote: {payload.footnote}")

    grid = html_table_to_grid(payload.table_body_html or "")
    lines.append("")
    lines.append(
        "## Cleaned grid (deterministic parse — AUTHORITATIVE for structure)\n")
    lines.append(
        f"Rows × max-cols: {len(grid)} × {max((len(r) for r in grid), default=0)}. "
        "Columns are aligned (colspan expanded). When this conflicts with the raw "
        "HTML below, trust this grid for row count, column count, and which "
        "header column a cell belongs to.")
    lines.append("")
    lines.append("```")
    lines.append(render_grid_as_markdown(grid))
    lines.append("```")

    if payload.csv_preview:
        lines.append("")
        lines.append("## CSV preview (paper_data.json reference)\n")
        lines.append("```csv")
        lines.append(payload.csv_preview)
        lines.append("```")

    lines.append("")
    lines.append(
        "## Raw MinerU HTML (fallback for compound cells / footnote markers)\n")
    lines.append("```html")
    lines.append(payload.table_body_html or "(empty)")
    lines.append("```")
    return "\n".join(lines)
