"""Resolve a single figure payload (img_path + caption + context) by item_id.

Mirrors the table-extractor's payload.py but for ``image`` kind items.
The driver / hook still has to load the actual image bytes for the
LLM (via ``Task.image_paths`` → framework's multimodal embedding) —
this module's job is the metadata side.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FigurePayload:
    item_id: int
    page_idx: Optional[int]
    caption: str
    footnote: str
    img_path_rel: Optional[str]  # relative to markdown dir
    img_path_abs: Optional[Path]  # resolved absolute path, or None if file missing
    parent_section_heading: Optional[str]
    content_list_index: int = -1


def _content_list_for(doc_path: Path) -> Optional[Path]:
    parent = doc_path.parent if doc_path.is_file() else doc_path
    matches = sorted(parent.glob("*_content_list.json"))
    return matches[0] if matches else None


def _walk_for_item(items: List[Dict[str, Any]], target_id: int) -> Optional[int]:
    """Mirrors enzyme-kinetics-content-tagger/outline.py:build_outline id assignment.

    Same edge case as table-extractor's payload.py: when body text
    precedes any heading, outline.py opens a synthetic prologue section
    that consumes id=0.
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
    for i in range(ci_idx - 1, -1, -1):
        it = items[i]
        if it.get("type") == "text" and it.get("text_level"):
            return (it.get("text") or "").strip()
    return None


def resolve_figure_payload(doc_path: str, item_id: int) -> FigurePayload:
    """Locate the figure at item_id and return its full payload.

    Raises:
        FileNotFoundError: when no content_list.json sibling is found.
        IndexError: when item_id does not exist in the outline.
        ValueError: when the resolved item is not an image.
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
    if entry.get("type") != "image":
        raise ValueError(
            f"item_id {item_id} resolves to type={entry.get('type')!r}, expected 'image'"
        )

    caption_list = entry.get("image_caption") or []
    footnote_list = entry.get("image_footnote") or []
    caption = (caption_list[0] if caption_list else "").strip()
    footnote = " ".join(s.strip() for s in footnote_list).strip()
    img_path_rel = entry.get("img_path")

    img_path_abs: Optional[Path] = None
    if img_path_rel:
        candidate = (cl_path.parent / img_path_rel).resolve()
        if candidate.is_file():
            img_path_abs = candidate

    parent_heading = _find_parent_section_heading(items, ci_idx)

    return FigurePayload(
        item_id=item_id,
        page_idx=entry.get("page_idx"),
        caption=caption,
        footnote=footnote,
        img_path_rel=img_path_rel,
        img_path_abs=img_path_abs,
        parent_section_heading=parent_heading,
        content_list_index=ci_idx,
    )


def render_figure_metadata_for_llm(payload: FigurePayload) -> str:
    """Compose the prompt-injection metadata block (image bytes embedded separately).

    The image content arrives as multimodal data through the framework's
    ``Task.image_paths`` plumbing; this text block names the figure and
    constrains the LLM's interpretation.
    """
    lines: List[str] = []
    lines.append("## Resolved figure context\n")
    lines.append(f"- item_id: {payload.item_id}")
    lines.append(f"- page_idx: {payload.page_idx}")
    if payload.parent_section_heading:
        lines.append(f"- parent_section: {payload.parent_section_heading}")
    else:
        lines.append("- parent_section: (none)")
    lines.append(f"- caption: {payload.caption or '(no caption)'}")
    if payload.footnote:
        lines.append(f"- footnote: {payload.footnote}")
    lines.append("")
    lines.append("The image of this figure is embedded directly in this prompt as "
                 "multimodal content. Analyze the image — do NOT try to read any "
                 "file from disk.")
    return "\n".join(lines)
