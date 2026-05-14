"""Resolve the paper-level scaffold-mapping payload.

Step 3.5 of the kinetics pipeline. Consumes Step 2's
``sections.{main,si.X}.json`` artifacts, filters items where
``is_scaffold_related: true``, and loads their body via the existing
per-extractor payload helpers — so all "what counts as scaffold-related
context" judgement lives in the tagger, not here.

This module never calls an LLM. It is invoked from ``hooks.py`` (pre_run)
to build the prompt injection block for ``enzyme-scaffold-mapper``.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional

_BASE = Path("/Users/ryanxu/CodeBase/GPTase")
_AGENTS_DIR = _BASE / ".claude/agents"
_EXTRACTIONS_DIR = _BASE / "papers/extractions"
_REGISTRY_PATH = _AGENTS_DIR / "enzyme-scaffold-mapper/scaffold_registry.json"

# PDB ID regex — 4-char alphanumeric, first char is a digit 1-9
# (real PDB IDs always start with a digit; this avoids matching English
# words like "DATA", "TIME", etc. that would slip past [A-Z0-9]{4}).
_PDB_RE = re.compile(r"\b[1-9][A-Za-z0-9]{3}\b")
# Allow-list helper for "PDB id: XXXX" style. Stronger context anchor.
_PDB_ANCHORED_RE = re.compile(r"\bPDB[\s:]*(?:ID[\s:]*)?[\"'`]?([1-9][A-Za-z0-9]{3})",
                              re.IGNORECASE)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


@dataclass
class ScaffoldTaggedItem:
    source_file: str
    item_id: int
    kind: str
    heading_or_caption: str
    body_text: str
    page_idx: Optional[int]
    reason: str = ""


@dataclass
class PdbCandidate:
    pdb_id: str
    context: str
    source_item_id: int
    source_file: str


@dataclass
class ScaffoldMapperPayload:
    paper_id: str
    document_path: str
    variant_names: List[str]
    scaffold_tagged_items: List[ScaffoldTaggedItem] = field(default_factory=list)
    pdb_candidates: List[PdbCandidate] = field(default_factory=list)
    available_scaffolds: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Lazy importers — re-use sibling extractor payload helpers
# ---------------------------------------------------------------------------


def _load_module(module_name: str, file_path: Path):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _section_resolver():
    return _load_module(
        "_esm_text_payload",
        _AGENTS_DIR / "enzyme-kinetics-text-extractor/payload.py",
    )


def _table_resolver():
    return _load_module(
        "_esm_table_payload",
        _AGENTS_DIR / "enzyme-kinetics-table-extractor/payload.py",
    )


def _outline_module():
    return _load_module(
        "_esm_outline",
        _AGENTS_DIR / "enzyme-kinetics-content-tagger/outline.py",
    )


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _resolve_paper_id(document_path: str) -> Optional[str]:
    """Derive the paper_id (extractions dir name) from a markdown path.

    Accepts either the main markdown file or its parent directories.
    Typical inputs:
      /…/papers/markdowns/<paper>/main/main.md
      /…/papers/markdowns/<paper>/main/full.md
      /…/papers/markdowns/<paper>/main
      /…/papers/markdowns/<paper>
    """
    p = Path(document_path).expanduser().resolve()
    parts = p.parts
    # Find the "markdowns" anchor, take the next segment.
    for i, part in enumerate(parts):
        if part == "markdowns" and i + 1 < len(parts):
            return parts[i + 1]
    # Fallback: walk up looking for a sibling extractions dir match.
    for ancestor in [p] + list(p.parents):
        cand = _EXTRACTIONS_DIR / ancestor.name
        if cand.is_dir():
            return ancestor.name
    return None


def _resolve_main_md(document_path: str) -> Optional[Path]:
    p = Path(document_path).expanduser()
    if p.is_file() and p.suffix.lower() == ".md":
        return p
    if p.is_dir():
        for candidate in (p / "main" / "full.md", p / "main" / "main.md", p / "full.md",
                          p / "main.md"):
            if candidate.is_file():
                return candidate
    return None


def _si_md_for_source(paper_id: str, source_file: str) -> Optional[Path]:
    """Locate the SI markdown for a sections.si.X.json source_file.

    sections.si.SI_<name>.json → papers/markdowns/<paper>/SI/SI_<name>/full.md
    (or main.md, or sometimes the same SI_<name>.md naming).
    """
    if source_file == "main":
        return None
    if not source_file.startswith("si."):
        return None
    si_subdir_name = source_file[len("si."):]
    si_dir = _BASE / "papers/markdowns" / paper_id / "SI" / si_subdir_name
    if not si_dir.is_dir():
        return None
    for candidate in (si_dir / "full.md", si_dir / "main.md",
                      si_dir / f"{si_subdir_name}.md"):
        if candidate.is_file():
            return candidate
    # Fallback: first .md anywhere in this SI subdir.
    mds = sorted(si_dir.rglob("*.md"))
    return mds[0] if mds else None


# ---------------------------------------------------------------------------
# sections.*.json reader + scaffold-filter
# ---------------------------------------------------------------------------


def _load_sections_files(paper_id: str) -> List[Dict[str, Any]]:
    """Load every sections.*.json for a paper. Returns the parsed dicts."""
    paper_extraction_dir = _EXTRACTIONS_DIR / paper_id
    out: List[Dict[str, Any]] = []
    if not paper_extraction_dir.is_dir():
        return out
    for sf in sorted(paper_extraction_dir.glob("sections.*.json")):
        # Skip backup files like sections.main.json.before_seq_prompt
        if sf.suffix not in (".json", ".JSON"):
            continue
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        # Embed the source_file token (matching the kinetics driver's key)
        source_file = _source_token_from_filename(sf.name)
        if source_file is None:
            continue
        data["_source_file"] = source_file
        data["_sections_path"] = str(sf)
        out.append(data)
    return out


def _source_token_from_filename(name: str) -> Optional[str]:
    """sections.main.json → 'main'; sections.si.SI_foo.json → 'si.SI_foo'."""
    if not name.startswith("sections.") or not name.endswith(".json"):
        return None
    inner = name[len("sections."):-len(".json")]
    return inner


# ---------------------------------------------------------------------------
# Body loaders (per-kind)
# ---------------------------------------------------------------------------


def _figure_caption(main_md: Path, item_id: int) -> Optional[str]:
    """Look up a figure caption via outline.build_outline (no full body)."""
    om = _outline_module()
    cl = om.find_content_list_for(main_md.parent)
    if cl is None:
        return None
    try:
        outline = om.build_outline(cl)
    except Exception:
        return None
    for o in outline:
        if o.id == item_id and o.kind == "figure":
            return (o.caption or "").strip()
    return None


def _load_section_body(md_path: Path, item_id: int) -> Optional[ScaffoldTaggedItem]:
    sr = _section_resolver()
    try:
        sp = sr.resolve_section_payload(str(md_path), item_id)
    except (FileNotFoundError, IndexError, ValueError):
        return None
    return ScaffoldTaggedItem(
        source_file="",  # filled by caller
        item_id=item_id,
        kind="section",
        heading_or_caption=sp.heading,
        body_text=sp.body_text,
        page_idx=sp.page_idx,
    )


def _load_table_body(md_path: Path, item_id: int) -> Optional[ScaffoldTaggedItem]:
    tr = _table_resolver()
    try:
        tp = tr.resolve_table_payload(str(md_path), item_id)
    except (FileNotFoundError, IndexError, ValueError):
        return None
    # Compose body = caption + footnote + table_body html (compact text view).
    body_parts: List[str] = []
    if tp.caption:
        body_parts.append(f"Caption: {tp.caption}")
    if tp.footnote:
        body_parts.append(f"Footnote: {tp.footnote}")
    if tp.parent_section_heading:
        body_parts.append(f"Parent section: {tp.parent_section_heading}")
    if tp.table_body_html:
        body_parts.append("Table body (HTML):")
        body_parts.append(tp.table_body_html)
    return ScaffoldTaggedItem(
        source_file="",
        item_id=item_id,
        kind="table",
        heading_or_caption=tp.caption,
        body_text="\n".join(body_parts),
        page_idx=tp.page_idx,
    )


def _load_figure_caption(md_path: Path, item_id: int) -> Optional[ScaffoldTaggedItem]:
    cap = _figure_caption(md_path, item_id)
    if cap is None:
        return None
    return ScaffoldTaggedItem(
        source_file="",
        item_id=item_id,
        kind="figure",
        heading_or_caption=cap,
        body_text=f"(figure) {cap}",
        page_idx=None,
    )


# ---------------------------------------------------------------------------
# Regex PDB scan
# ---------------------------------------------------------------------------


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    return _SENTENCE_BOUNDARY.split(text)


def _context_around(text: str, span_start: int, span_end: int, window: int = 2) -> str:
    """Return the matched sentence + `window` sentences each side, joined."""
    sentences = _split_sentences(text)
    if not sentences:
        return ""
    # Compute char offsets per sentence.
    char_idx = 0
    sentence_starts: List[int] = []
    for s in sentences:
        sentence_starts.append(char_idx)
        char_idx += len(s) + 1  # +1 for the boundary whitespace
    # Find which sentence the span falls into.
    hit = 0
    for i, start in enumerate(sentence_starts):
        if start <= span_start:
            hit = i
        else:
            break
    lo = max(0, hit - window)
    hi = min(len(sentences), hit + window + 1)
    return " ".join(sentences[lo:hi]).strip()


def _scan_pdb_in_text(text: str, source_item_id: int, source_file: str,
                      out: List[PdbCandidate], seen: set) -> None:
    if not text:
        return
    for m in _PDB_RE.finditer(text):
        cand = m.group(0).upper()
        if cand in seen:
            continue
        # Strict-ish filter: skip common 4-char English words that survive the
        # leading-digit check (none should; but covers "8888", trivial digits).
        if cand.isdigit():
            continue
        # Anchored regex confirms PDB-context; if absent, still accept but the
        # LLM will judge usefulness from context.
        ctx = _context_around(text, m.start(), m.end())
        out.append(
            PdbCandidate(pdb_id=cand,
                         context=ctx,
                         source_item_id=source_item_id,
                         source_file=source_file))
        seen.add(cand)


# ---------------------------------------------------------------------------
# Registry loader
# ---------------------------------------------------------------------------


def _load_registry_names() -> List[str]:
    if not _REGISTRY_PATH.is_file():
        return []
    try:
        data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    names: List[str] = []
    seen: set = set()
    for entry in data.get("entries") or []:
        for n in entry.get("names") or []:
            if isinstance(n, str) and n.strip() and n not in seen:
                names.append(n)
                seen.add(n)
    return names


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def resolve_paper_payload(
        document_path: str,
        si_document_path: Optional[str] = None,
        variant_names: Optional[List[str]] = None) -> ScaffoldMapperPayload:
    """Build the per-paper scaffold-mapping payload.

    Args:
        document_path: main paper markdown (or its parent dir).
        si_document_path: ignored — multiple SI files are auto-discovered.
        variant_names: variant_names extracted by Step 3; passed through.

    Returns:
        ScaffoldMapperPayload with scaffold_tagged_items, pdb_candidates,
        available_scaffolds.
    """
    paper_id = _resolve_paper_id(document_path)
    if paper_id is None:
        return ScaffoldMapperPayload(
            paper_id="",
            document_path=document_path,
            variant_names=variant_names or [],
            notes=[
                f"Could not resolve paper_id from document_path={document_path!r}; "
                "expected path under .../papers/markdowns/<paper>/..."
            ],
        )
    main_md = _resolve_main_md(document_path)
    payload = ScaffoldMapperPayload(
        paper_id=paper_id,
        document_path=str(main_md) if main_md else document_path,
        variant_names=list(variant_names or []),
        available_scaffolds=_load_registry_names(),
    )

    sections_docs = _load_sections_files(paper_id)
    if not sections_docs:
        payload.notes.append(
            f"No sections.*.json found in {_EXTRACTIONS_DIR / paper_id}; "
            "tagger Step 2 has not run for this paper.")
        return payload

    pdb_seen: set = set()

    for doc in sections_docs:
        source_file = doc["_source_file"]
        items = doc.get("items") or []
        # Locate the markdown the item_ids refer to.
        if source_file == "main":
            md_path = main_md
        else:
            md_path = _si_md_for_source(paper_id, source_file)
        if md_path is None:
            payload.notes.append(
                f"Skipping source_file={source_file!r}: markdown not found.")
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            if not item.get("is_scaffold_related"):
                continue
            item_id = item.get("id")
            if not isinstance(item_id, int):
                continue
            kind = (item.get("kind") or "").lower()
            # The tagger emits items with `kind` derived from outline; but
            # older sections.*.json predating the kind field also exist.
            # Detect via outline when missing.
            if not kind:
                kind = _detect_kind(md_path, item_id)
            loaded: Optional[ScaffoldTaggedItem] = None
            if kind == "section":
                loaded = _load_section_body(md_path, item_id)
            elif kind == "table":
                loaded = _load_table_body(md_path, item_id)
            elif kind == "figure":
                loaded = _load_figure_caption(md_path, item_id)
            else:
                # Unknown kind — try section first then table.
                loaded = (_load_section_body(md_path, item_id)
                          or _load_table_body(md_path, item_id)
                          or _load_figure_caption(md_path, item_id))
            if loaded is None:
                payload.notes.append(f"Failed to load body for {source_file}#{item_id} "
                                     f"(kind={kind})")
                continue
            loaded.source_file = source_file
            loaded.reason = str(item.get("reason") or "")
            payload.scaffold_tagged_items.append(loaded)
            _scan_pdb_in_text(loaded.body_text, item_id, source_file,
                              payload.pdb_candidates, pdb_seen)

    return payload


def _detect_kind(md_path: Path, item_id: int) -> str:
    """Quick kind probe via outline (used when tagger didn't emit `kind`)."""
    om = _outline_module()
    cl = om.find_content_list_for(md_path.parent)
    if cl is None:
        return ""
    try:
        outline = om.build_outline(cl)
    except Exception:
        return ""
    for o in outline:
        if o.id == item_id:
            return (o.kind or "").lower()
    return ""


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------


def render_paper_for_llm(payload: ScaffoldMapperPayload,
                         *,
                         body_char_budget: int = 2500) -> str:
    """Compose the prompt-injection block for the LLM.

    `body_char_budget` truncates over-long section bodies (each item gets
    at most this many chars). Tables and figures pass through unchanged
    since their bodies are typically caption + footnote.
    """
    lines: List[str] = []
    lines.append("## Scaffold-mapping payload\n")
    lines.append(f"- paper_id: {payload.paper_id}")
    lines.append(f"- document_path: {payload.document_path}")
    lines.append(f"- variant_count: {len(payload.variant_names)}")
    lines.append(f"- scaffold_tagged_items: {len(payload.scaffold_tagged_items)}")
    lines.append(f"- pdb_candidates: {len(payload.pdb_candidates)}")
    lines.append(f"- registry_scaffold_names: {len(payload.available_scaffolds)}")
    if payload.notes:
        lines.append("")
        lines.append("### Diagnostic notes")
        for n in payload.notes:
            lines.append(f"- {n}")
    lines.append("")

    lines.append("## variant_names (from Step 3 extractors)\n")
    if payload.variant_names:
        lines.append("```")
        for vn in payload.variant_names:
            lines.append(vn)
        lines.append("```")
    else:
        lines.append("(empty — no variants reached Step 3.5)")
    lines.append("")

    lines.append("## available_scaffolds (registry name index — driver will "
                 "fill PDB from these names)\n")
    if payload.available_scaffolds:
        lines.append("```")
        for n in payload.available_scaffolds:
            lines.append(f"- {n}")
        lines.append("```")
    else:
        lines.append("(registry empty)")
    lines.append("")

    lines.append(
        "## pdb_candidates (verbatim PDB IDs grepped from tagged items "
        "— ONLY these may appear as `pdb_id` with `pdb_id_source: paper_quote`)\n")
    if payload.pdb_candidates:
        for c in payload.pdb_candidates:
            lines.append(f"- **{c.pdb_id}** (from {c.source_file}#{c.source_item_id}): "
                         f"{c.context[:400]}")
    else:
        lines.append("(no PDB IDs found in tagged items)")
    lines.append("")

    lines.append("## scaffold_tagged_items (Step 2 said is_scaffold_related=true)\n")
    if not payload.scaffold_tagged_items:
        lines.append("(empty — tagger marked nothing as scaffold-related; "
                     "emit registry_hint or null mappings only)")
    for it in payload.scaffold_tagged_items:
        lines.append(f"### [{it.source_file}#{it.item_id}] {it.kind.upper()} — "
                     f"{it.heading_or_caption[:120]}")
        if it.reason:
            lines.append(f"_tagger reason: {it.reason}_")
        lines.append("")
        body = it.body_text or ""
        if len(body) > body_char_budget and it.kind == "section":
            body = body[:body_char_budget] + f"\n…[truncated; full body was {len(it.body_text)} chars]"
        lines.append("```text")
        lines.append(body or "(empty body)")
        lines.append("```")
        lines.append("")
    return "\n".join(lines)
