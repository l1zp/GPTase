"""pre_run hook for enzyme-kinetics-table-extractor.

Validates ``(document_path, item_id)``, locates the sibling MinerU
``content_list.json``, resolves the table payload via ``payload.py``,
and INJECTS the table HTML + caption + footnote + parent section
heading into ``ctx.prompt`` BEFORE the LLM runs. The LLM never reads
the markdown — it only emits canonical reaction rows from the
injected table.

Failure modes (all short-circuit before any LLM call):
- ``document_path`` or ``item_id`` missing from the prompt envelope.
- ``document_path`` does not resolve to a readable .md file.
- No ``*_content_list.json`` sibling exists.
- ``item_id`` does not exist in the outline OR resolves to a non-table.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

from gptase.agents.hooks import HookContext

# ---------------------------------------------------------------------------
# Load sibling payload.py
# ---------------------------------------------------------------------------

_MODULE_NAME = "_ektex_payload"
_spec = importlib.util.spec_from_file_location(_MODULE_NAME,
                                               Path(__file__).parent / "payload.py")
assert _spec is not None and _spec.loader is not None
_payload_mod = importlib.util.module_from_spec(_spec)
sys.modules[_MODULE_NAME] = _payload_mod
_spec.loader.exec_module(_payload_mod)
resolve_table_payload = _payload_mod.resolve_table_payload
render_table_for_llm = _payload_mod.render_table_for_llm

# ---------------------------------------------------------------------------
# Prompt parsing — anchor on Input Data: / Task: markers (mirrors content-tagger)
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


def _get_inputs(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a dict with document_path / item_id from a parsed JSON object."""
    if isinstance(obj.get("document_path"), str) and "item_id" in obj:
        return obj
    inputs = obj.get("inputs")
    if isinstance(inputs, dict):
        if isinstance(inputs.get("document_path"), str) and "item_id" in inputs:
            return inputs
    desc = obj.get("description")
    if isinstance(desc, str):
        brace = desc.find("{")
        if brace != -1:
            inner = _parse_balanced_json_at(desc, brace)
            if inner is not None:
                return _get_inputs(inner)
    return None


def _extract_pair(prompt_text: str) -> Optional[Dict[str, Any]]:
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
        pair = _get_inputs(obj)
        if pair is not None:
            return pair
    # Fallback: walk all balanced JSON objects, return last with both keys
    last = None
    cursor = 0
    while True:
        brace = prompt_text.find("{", cursor)
        if brace == -1:
            break
        obj = _parse_balanced_json_at(prompt_text, brace)
        if obj is not None:
            pair = _get_inputs(obj)
            if pair is not None:
                last = pair
        cursor = brace + 1
    return last


# ---------------------------------------------------------------------------
# Path resolution + hook entry
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


def _error_result(message: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "error": message,
        "data": {
            "content": ""
        },
    }


def pre_run(ctx: HookContext) -> Optional[Dict[str, Any]]:
    """Validate inputs, build table payload, inject into ctx.prompt."""
    prompt_text = _extract_text(ctx.prompt)
    pair = _extract_pair(prompt_text)
    if pair is None:
        return _error_result(
            "enzyme-kinetics-table-extractor pre_run: could not find both "
            "`document_path` and `item_id` in the input.")
    doc_path = pair["document_path"]
    item_id = pair["item_id"]
    if not isinstance(item_id, int):
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            return _error_result(f"enzyme-kinetics-table-extractor pre_run: item_id "
                                 f"{item_id!r} is not an integer.")

    resolved = _resolve_doc(doc_path)
    if resolved is None:
        return _error_result(f"enzyme-kinetics-table-extractor pre_run: document_path "
                             f"'{doc_path}' does not resolve to a readable .md file.")

    try:
        payload = resolve_table_payload(str(resolved), item_id)
    except (FileNotFoundError, IndexError, ValueError) as exc:
        return _error_result(
            f"enzyme-kinetics-table-extractor pre_run: {type(exc).__name__}: {exc}")

    injection = "\n\n" + render_table_for_llm(payload) + "\n"
    if isinstance(ctx.prompt, str):
        ctx.prompt = ctx.prompt + injection
    else:
        ctx.prompt = list(ctx.prompt) + [{"type": "text", "text": injection}]

    ctx.extras["resolved_document_path"] = str(resolved)
    ctx.extras["item_id"] = item_id
    ctx.extras["table_caption"] = payload.caption
    ctx.extras["table_body_chars"] = len(payload.table_body_html)

    return None
