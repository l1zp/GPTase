"""Build a compact outline from a MinerU ``content_list.json``.

MinerU emits a per-PDF JSON whose entries are already typed
(``text`` / ``image`` / ``table`` / ``discarded``) with bbox, page index,
and — for text — heading level. We turn that into a Python-side outline
with sections, tables, and figures, all carrying small unique IDs that
the LLM can reference when emitting relevance judgments.

This module is loaded by ``hooks.py`` via importlib (same pattern as
``enzyme-variant-normalizer/normalizer.py``) so it has no dependency on
``gptase`` internals and stays unit-testable in isolation.
"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class OutlineItem:
    """One row in the structured outline we hand to the LLM."""

    id: int
    kind: str  # "section" | "table" | "figure"
    title: Optional[str] = None  # for sections
    caption: Optional[str] = None  # for tables / figures
    page_idx: Optional[int] = None
    section_id: Optional[int] = None  # parent section, for tables / figures
    body_chars: int = 0  # body length under a section
    body_preview: str = ""  # for sections — first ~200 chars of body text
    # Downstream-only payload (not part of the LLM-facing render)
    img_path: Optional[str] = None
    table_body: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_PREVIEW_CHARS = 240


def _truncate(text: str, n: int = 240) -> str:
    text = text.strip()
    return text[:n] + ("..." if len(text) > n else "")


def build_outline(content_list_path: Path) -> List[OutlineItem]:
    """Parse a MinerU ``content_list.json`` into a list of ``OutlineItem``s.

    Headings (``text_level`` set) become sections; tables and figures
    are attached to whichever section is currently open. Discarded items
    (page headers, footers, page numbers) are filtered out entirely.
    """
    items = json.loads(Path(content_list_path).read_text(encoding="utf-8"))
    outline: List[OutlineItem] = []
    next_id = 0
    current_section_id: Optional[int] = None

    for it in items:
        kind = it.get("type")
        if kind == "discarded":
            continue

        if kind == "text":
            level = it.get("text_level")
            text = (it.get("text") or "").strip()
            if level:
                section = OutlineItem(
                    id=next_id,
                    kind="section",
                    title=text,
                    page_idx=it.get("page_idx"),
                )
                outline.append(section)
                current_section_id = next_id
                next_id += 1
            else:
                if current_section_id is not None:
                    for o in outline:
                        if o.id == current_section_id:
                            o.body_chars += len(text)
                            # Grow the preview only until it hits the cap.
                            if len(o.body_preview) < _PREVIEW_CHARS:
                                sep = " " if o.body_preview else ""
                                o.body_preview = (o.body_preview + sep
                                                  + text)[:_PREVIEW_CHARS]
                            break
                else:
                    # Body text before any heading — open a synthetic section
                    section = OutlineItem(
                        id=next_id,
                        kind="section",
                        title="(prologue)",
                        page_idx=it.get("page_idx"),
                        body_chars=len(text),
                        body_preview=text[:_PREVIEW_CHARS],
                    )
                    outline.append(section)
                    current_section_id = next_id
                    next_id += 1
            continue

        if kind == "table":
            cap_list = it.get("table_caption") or []
            outline.append(
                OutlineItem(
                    id=next_id,
                    kind="table",
                    caption=_truncate(cap_list[0] if cap_list else ""),
                    page_idx=it.get("page_idx"),
                    section_id=current_section_id,
                    img_path=it.get("img_path"),
                    table_body=it.get("table_body"),
                ))
            next_id += 1
            continue

        if kind == "image":
            cap_list = it.get("image_caption") or []
            outline.append(
                OutlineItem(
                    id=next_id,
                    kind="figure",
                    caption=_truncate(cap_list[0] if cap_list else ""),
                    page_idx=it.get("page_idx"),
                    section_id=current_section_id,
                    img_path=it.get("img_path"),
                ))
            next_id += 1

    return outline


def render_outline_for_llm(outline: List[OutlineItem]) -> str:
    """Compact text rendering for the LLM prompt.

    Each item is one block; sections get a body-preview line so the LLM
    has actual content cues (not just a heading) when judging relevance.
    """
    lines: List[str] = []
    for o in outline:
        if o.kind == "section":
            lines.append(
                f"[{o.id}] SECTION (p.{o.page_idx}, ~{o.body_chars}c): {o.title}")
            if o.body_preview:
                lines.append(f"      body: {o.body_preview}")
        elif o.kind == "table":
            cap = o.caption or "(no caption)"
            lines.append(
                f"[{o.id}] TABLE   (p.{o.page_idx}, sec {o.section_id}): {cap}")
        elif o.kind == "figure":
            cap = o.caption or "(no caption)"
            lines.append(
                f"[{o.id}] FIGURE  (p.{o.page_idx}, sec {o.section_id}): {cap}")
    return "\n".join(lines)


def find_content_list_for(doc_path: Path) -> Optional[Path]:
    """Locate the MinerU content_list.json sibling of a paper body file.

    ``doc_path`` may be either the body .md file itself or its
    containing directory. We look for ``*_content_list.json`` in the
    same directory as the .md file.
    """
    doc_path = Path(doc_path).expanduser()
    if doc_path.is_file():
        parent = doc_path.parent
    else:
        parent = doc_path
    matches = sorted(parent.glob("*_content_list.json"))
    return matches[0] if matches else None
