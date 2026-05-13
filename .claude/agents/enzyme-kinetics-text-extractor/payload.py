"""Resolve a single section payload by (document_path, item_id).

For Phase 3 of the kinetics pipeline. Re-walks ``content_list.json``
directly so we get the FULL body text under a heading — not the
240-char truncated preview that ``outline.py`` carries. Also collects
captions of any tables / figures that fall under the same heading so
prose like "as shown in Table 1" can be resolved by the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SectionPayload:
    item_id: int
    page_idx: Optional[int]
    heading: str
    body_text: str  # full body, no truncation
    child_captions: List[str] = field(default_factory=list)
    content_list_index: int = -1


def _content_list_for(doc_path: Path) -> Optional[Path]:
    parent = doc_path.parent if doc_path.is_file() else doc_path
    matches = sorted(parent.glob("*_content_list.json"))
    return matches[0] if matches else None


def _walk_for_item(items: List[Dict[str, Any]], target_id: int) -> Optional[int]:
    """Mirrors outline.py:build_outline id assignment (incl. prologue edge)."""
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


def resolve_section_payload(doc_path: str, item_id: int) -> SectionPayload:
    """Locate the section at item_id and return heading + full body + child captions.

    Raises:
        FileNotFoundError: no content_list.json sibling.
        IndexError: item_id not in outline.
        ValueError: item is not a section (heading) — could be a synthetic
            prologue section (text body before any heading), which IS valid.
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
    is_heading = entry.get("type") == "text" and entry.get("text_level")
    is_prologue_body = (entry.get("type") == "text" and not entry.get("text_level"))
    if not (is_heading or is_prologue_body):
        raise ValueError(
            f"item_id {item_id} resolves to type={entry.get('type')!r}, expected "
            "'text' (section heading or prologue body)")

    if is_heading:
        heading = (entry.get("text") or "").strip()
        heading_level = entry.get("text_level")
        body_start = ci_idx + 1
    else:
        # Synthetic prologue section — the body STARTS at this item.
        heading = "(prologue)"
        heading_level = None
        body_start = ci_idx

    # Walk forward collecting body text + child captions, stop at next heading.
    body_parts: List[str] = []
    child_captions: List[str] = []
    for j in range(body_start, len(items)):
        it = items[j]
        kind = it.get("type")
        if kind == "discarded":
            continue
        if kind == "text":
            if it.get("text_level"):
                # Stop at the next heading regardless of level — we want
                # just the immediate body before the next section divider.
                # (More aggressive: stop only at same-or-higher level.
                # Conservative is safer for hallucination control.)
                break
            text = (it.get("text") or "").strip()
            if text:
                body_parts.append(text)
        elif kind == "table":
            cap_list = it.get("table_caption") or []
            if cap_list:
                child_captions.append(f"[TABLE p.{it.get('page_idx')}] "
                                      + cap_list[0].strip())
        elif kind == "image":
            cap_list = it.get("image_caption") or []
            if cap_list:
                child_captions.append(f"[FIGURE p.{it.get('page_idx')}] "
                                      + cap_list[0].strip())

    body_text = "\n\n".join(body_parts)

    return SectionPayload(
        item_id=item_id,
        page_idx=entry.get("page_idx"),
        heading=heading,
        body_text=body_text,
        child_captions=child_captions,
        content_list_index=ci_idx,
    )


def render_section_for_llm(payload: SectionPayload) -> str:
    """Compose the prompt-injection block."""
    lines: List[str] = []
    lines.append("## Resolved section payload\n")
    lines.append(f"- item_id: {payload.item_id}")
    lines.append(f"- page_idx: {payload.page_idx}")
    lines.append(f"- heading: {payload.heading}")
    lines.append(f"- body_chars: {len(payload.body_text)}")
    lines.append("")
    if payload.child_captions:
        lines.append("## Child captions (tables / figures inside this section)\n")
        for c in payload.child_captions:
            lines.append(f"- {c}")
        lines.append("")
    lines.append("## Body text (verbatim from MinerU content_list.json)\n")
    lines.append("```text")
    lines.append(payload.body_text if payload.body_text else "(empty body)")
    lines.append("```")
    return "\n".join(lines)
