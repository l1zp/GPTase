"""pre_run hook for enzyme-kinetics-content-tagger.

Validates document_path, locates the sibling MinerU
``*_content_list.json``, builds a compact outline, and INJECTS that
outline plus a structured header (resolved path / source / SI filename)
into ``ctx.prompt`` BEFORE the LLM runs. The LLM never sees the raw
markdown — it only judges the outline items by their [id] tags.

Failure modes (all short-circuit before any LLM call):
- ``document_path`` missing from the prompt envelope.
- ``document_path`` does not resolve to an existing .md file under the
  conventional MinerU layouts (``main/full.md``, ``main/main.md``,
  ``full.md``, ``main.md``).
- No ``*_content_list.json`` sibling exists for the resolved .md file.

Sibling ``outline.py`` is loaded via importlib (same pattern as
``enzyme-variant-normalizer/normalizer.py``) so this hook stays
self-contained.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

from gptase.agents.hooks import HookContext

# ---------------------------------------------------------------------------
# Load sibling outline.py
# ---------------------------------------------------------------------------

_MODULE_NAME = "_ekct_outline"
_spec = importlib.util.spec_from_file_location(_MODULE_NAME,
                                               Path(__file__).parent / "outline.py")
assert _spec is not None and _spec.loader is not None
_outline_mod = importlib.util.module_from_spec(_spec)
# Required on Python 3.12+ for dataclass to find its module via sys.modules.
sys.modules[_MODULE_NAME] = _outline_mod
_spec.loader.exec_module(_outline_mod)
build_outline = _outline_mod.build_outline
render_outline_for_llm = _outline_mod.render_outline_for_llm
find_content_list_for = _outline_mod.find_content_list_for

# ---------------------------------------------------------------------------
# Prompt parsing — anchor on Input Data: / Task: markers so memory-injected
# document_paths from prior runs do not confuse us.
# ---------------------------------------------------------------------------


def _extract_text(prompt: Union[str, List[Dict[str, Any]]]) -> str:
    if isinstance(prompt, str):
        return prompt
    parts: List[str] = []
    for entry in prompt or []:
        if isinstance(entry, dict) and entry.get("type") == "text":
            parts.append(entry.get("text", ""))
    return "\n".join(parts)


def _parse_balanced_json_at(text: str, start: int) -> Optional[Dict[str, Any]]:
    if start < 0 or start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _get_document_path(obj: Dict[str, Any]) -> Optional[str]:
    if isinstance(obj.get("document_path"), str):
        return obj["document_path"]
    inputs = obj.get("inputs")
    if isinstance(inputs, dict) and isinstance(inputs.get("document_path"), str):
        return inputs["document_path"]
    desc = obj.get("description")
    if isinstance(desc, str):
        brace = desc.find("{")
        if brace != -1:
            inner = _parse_balanced_json_at(desc, brace)
            if inner is not None:
                return _get_document_path(inner)
    return None


def _extract_document_path(prompt_text: str) -> Optional[str]:
    for marker in ("Input Data:", "Task:"):
        idx = prompt_text.rfind(marker)
        if idx == -1:
            continue
        brace = prompt_text.find("{", idx)
        if brace == -1:
            continue
        obj = _parse_balanced_json_at(prompt_text, brace)
        if obj is None:
            continue
        dp = _get_document_path(obj)
        if dp is not None:
            return dp
    # Fallback: last balanced JSON anywhere
    last_dp: Optional[str] = None
    cursor = 0
    while True:
        brace = prompt_text.find("{", cursor)
        if brace == -1:
            break
        obj = _parse_balanced_json_at(prompt_text, brace)
        if obj is not None:
            dp = _get_document_path(obj)
            if dp is not None:
                last_dp = dp
        cursor = brace + 1
    return last_dp


# ---------------------------------------------------------------------------
# Path resolution + source detection
# ---------------------------------------------------------------------------


def _resolve_doc(path_str: str) -> Optional[Path]:
    p = Path(path_str).expanduser()
    if p.suffix.lower() == ".md" and p.is_file():
        return p
    if p.is_dir():
        for candidate in (p / "main" / "full.md", p / "main" / "main.md", p / "full.md",
                          p / "main.md"):
            if candidate.is_file():
                return candidate
    return None


def _detect_source(resolved: Path) -> tuple[str, str]:
    """Return (source, si_filename). source is "main" or "si"."""
    parts = resolved.parts
    for i, part in enumerate(parts):
        if part == "SI":
            # Look one level deeper for the SI directory name
            if i + 1 < len(parts):
                return "si", parts[i + 1]
            return "si", ""
        if part.startswith("SI_") or part.startswith("si_"):
            return "si", part
    return "main", ""


# ---------------------------------------------------------------------------
# Hook entry
# ---------------------------------------------------------------------------


def _error_result(message: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "error": message,
        "data": {
            "content": ""
        },
    }


_INJECT_HEADER_TMPL = """

## Resolved document context

- resolved_document_path: {resolved}
- source: {source}
- si_filename: {si_filename}

## Outline (auto-built from MinerU content_list.json)

Each line is one outline item with a unique [id]. Judge each one's relevance
to enzyme kinetic measurements. Your output must include one entry per [id].

```
{outline_text}
```
"""


def pre_run(ctx: HookContext) -> Optional[Dict[str, Any]]:
    """Validate inputs, build outline, inject into ctx.prompt."""
    prompt_text = _extract_text(ctx.prompt)
    doc_path = _extract_document_path(prompt_text)
    if doc_path is None:
        return _error_result("enzyme-kinetics-content-tagger pre_run: could not find a "
                             "`document_path` value in the input.")
    resolved = _resolve_doc(doc_path)
    if resolved is None:
        return _error_result(
            f"enzyme-kinetics-content-tagger pre_run: document_path "
            f"'{doc_path}' does not resolve to a readable .md file. Tried it "
            f"directly and `main/full.md` / `main/main.md` / `full.md` / "
            f"`main.md` under it.")

    content_list = find_content_list_for(resolved)
    if content_list is None:
        return _error_result(f"enzyme-kinetics-content-tagger pre_run: no MinerU "
                             f"`*_content_list.json` sibling found next to {resolved}. "
                             f"This agent depends on MinerU pre-structured output.")

    try:
        outline_items = build_outline(content_list)
    except Exception as exc:
        return _error_result(f"enzyme-kinetics-content-tagger pre_run: failed to parse "
                             f"{content_list}: {exc}")

    if not outline_items:
        return _error_result(
            f"enzyme-kinetics-content-tagger pre_run: outline from "
            f"{content_list} is empty after filtering discarded items.")

    source, si_filename = _detect_source(resolved)
    outline_text = render_outline_for_llm(outline_items)

    injection = _INJECT_HEADER_TMPL.format(
        resolved=str(resolved),
        source=source,
        si_filename=si_filename or "",
        outline_text=outline_text,
    )

    # Append injection to ctx.prompt so the LLM sees the original task
    # plus the structured outline.
    if isinstance(ctx.prompt, str):
        ctx.prompt = ctx.prompt + injection
    else:
        # Multimodal — append a text block. (We never get images here in
        # practice, but be robust.)
        ctx.prompt = list(ctx.prompt) + [{"type": "text", "text": injection}]

    # Stash for any post_run that wants it later.
    ctx.extras["resolved_document_path"] = str(resolved)
    ctx.extras["source"] = source
    ctx.extras["si_filename"] = si_filename
    ctx.extras["outline_item_count"] = len(outline_items)

    return None  # let the LLM run with the enriched prompt
